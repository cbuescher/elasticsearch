/*
 * Licensed to Elasticsearch under one or more contributor
 * license agreements. See the NOTICE file distributed with
 * this work for additional information regarding copyright
 * ownership. Elasticsearch licenses this file to you under
 * the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.elasticsearch.search.fetch.subphase;

import org.apache.lucene.index.LeafReaderContext;
import org.apache.lucene.util.automaton.CharacterRunAutomaton;
import org.elasticsearch.common.Nullable;
import org.elasticsearch.common.document.DocumentField;
import org.elasticsearch.common.regex.Regex;
import org.elasticsearch.index.mapper.MappedFieldType;
import org.elasticsearch.index.mapper.NestedValueFetcher;
import org.elasticsearch.index.mapper.ObjectMapper;
import org.elasticsearch.index.mapper.ValueFetcher;
import org.elasticsearch.index.query.SearchExecutionContext;
import org.elasticsearch.search.lookup.SourceLookup;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * A helper class to {@link FetchFieldsPhase} that's initialized with a list of field patterns to fetch.
 * Then given a specific document, it can retrieve the corresponding fields from the document's source.
 */
public class FieldFetcher {

    public static FieldFetcher create(SearchExecutionContext context,
        Collection<FieldAndFormat> fieldAndFormats) {
        List<String> nestedMappingPaths = context.hasNested()
            ? context.nestedMappings().stream().map(ObjectMapper::name).collect(Collectors.toList())
            : Collections.emptyList();
        return create(context, fieldAndFormats, nestedMappingPaths);
    }

    private static FieldFetcher create(SearchExecutionContext context,
        Collection<FieldAndFormat> fieldAndFormats, List<String> nestedMappingsInScope) {

        // sort nestedMappingsInScope by length so we can find the shortest prefix for other fields quicker later
        if (nestedMappingsInScope.isEmpty() == false) {
            Collections.sort(nestedMappingsInScope, Comparator.comparing(String::length));
        }

        // Using a LinkedHashMap so fields are returned in the order requested.
        // We won't formally guarantee this but but its good for readability of the response
        Map<String, FieldContext> fieldContexts = new LinkedHashMap<>();
        List<String> unmappedFetchPattern = new ArrayList<>();

        Map<String, List<FieldAndFormat>> fieldsInsideNested = new HashMap<>();
        for (FieldAndFormat fieldAndFormat : fieldAndFormats) {
            String fieldPattern = fieldAndFormat.field;
            if (fieldAndFormat.includeUnmapped != null && fieldAndFormat.includeUnmapped) {
                unmappedFetchPattern.add(fieldAndFormat.field);
            }

            Collection<String> concreteFields = context.simpleMatchToIndexNames(fieldPattern);
            for (String field : concreteFields) {
                MappedFieldType ft = context.getFieldType(field);
                if (ft == null || context.isMetadataField(field)) {
                    continue;
                }
                String nestedParentPath = null;
                if (nestedMappingsInScope.isEmpty() == false) {
                    // try to find the shortest nested parent path for this field


                    for (String nestedFieldPath : nestedMappingsInScope) {
                        if (field.startsWith(nestedFieldPath)) {
                            nestedParentPath = nestedFieldPath;
                            break;
                        }
                    }
                }
                if (nestedParentPath == null) {
                    ValueFetcher valueFetcher = ft.valueFetcher(context, fieldAndFormat.format);
                    fieldContexts.put(field, new FieldContext(field, valueFetcher));
                } else {
                    // this concrete field is a subfield of a nested field. Add its pattern to the list of nested fields to process later
                    fieldsInsideNested.computeIfAbsent(nestedParentPath, k -> new ArrayList<>()).add(fieldAndFormat);
                }
            }
        }

        // create a new nested value fetcher for patterns under nested field
        for (String nestedFieldPath : fieldsInsideNested.keySet()) {
            // We construct a field fetcher that only sees field patterns that match something beneath a nested field path.
            // We also need to remove this nested field path and everything beneath it from the list of available nested fields before
            // creating this internal field fetcher to avoid infinite loops on this recursion
            List<String> narrowedScopeNestedMappings = nestedMappingsInScope.stream()
                .filter(s -> s.startsWith(nestedFieldPath) && (s.equals(nestedFieldPath) == false))
                .collect(Collectors.toList());

            FieldFetcher nestedSubFieldFetcher = FieldFetcher.create(
                context,
                fieldsInsideNested.get(nestedFieldPath),
                narrowedScopeNestedMappings
            );

            // add a special ValueFetcher that filters source and collects its subfields
            fieldContexts.put(
                nestedFieldPath,
                new FieldContext(nestedFieldPath, new NestedValueFetcher(nestedFieldPath, nestedSubFieldFetcher))
            );
        }

        CharacterRunAutomaton unmappedFieldsFetchAutomaton = null;
        if (unmappedFetchPattern.isEmpty() == false) {
            unmappedFieldsFetchAutomaton = new CharacterRunAutomaton(
                Regex.simpleMatchToAutomaton(unmappedFetchPattern.toArray(new String[unmappedFetchPattern.size()]))
            );
        }
        return new FieldFetcher(fieldContexts, unmappedFieldsFetchAutomaton, fieldsInsideNested.keySet());
    }

    private final Map<String, FieldContext> fieldContexts;
    private final CharacterRunAutomaton unmappedFieldsFetchAutomaton;
    private final Set<String> excludedNestedPaths;

    private FieldFetcher(
        Map<String, FieldContext> fieldContexts,
        @Nullable CharacterRunAutomaton unmappedFieldsFetchAutomaton,
        Set<String> excludedNestedPaths
    ) {
        this.fieldContexts = fieldContexts;
        this.unmappedFieldsFetchAutomaton = unmappedFieldsFetchAutomaton;
        this.excludedNestedPaths = excludedNestedPaths;
    }

    public Map<String, DocumentField> fetch(SourceLookup sourceLookup, Set<String> ignoredFields) throws IOException {
        Map<String, DocumentField> documentFields = new HashMap<>();
        for (FieldContext context : fieldContexts.values()) {
            String field = context.fieldName;
            if (ignoredFields != null && ignoredFields.contains(field)) {
                continue;
            }

            ValueFetcher valueFetcher = context.valueFetcher;
            List<Object> parsedValues = valueFetcher.fetchValues(sourceLookup, ignoredFields);

            if (parsedValues.isEmpty() == false) {
                documentFields.put(field, new DocumentField(field, parsedValues));
            }
        }
        if (this.unmappedFieldsFetchAutomaton != null) {
            collectUnmapped(documentFields, sourceLookup.loadSourceIfNeeded(), "", 0);
        }
        return documentFields;
    }

    private void collectUnmapped(Map<String, DocumentField> documentFields, Map<String, Object> source, String parentPath, int lastState) {
        for (String key : source.keySet()) {
            Object value = source.get(key);
            String currentPath = parentPath + key;
            if (this.excludedNestedPaths.contains(currentPath)) {
                continue;
            }
            int currentState = step(this.unmappedFieldsFetchAutomaton, key, lastState);
            if (currentState == -1) {
                // current path doesn't match any fields pattern
                continue;
            }
            if (value instanceof Map) {
                // one step deeper into source tree
                collectUnmapped(
                    documentFields,
                    (Map<String, Object>) value,
                    currentPath + ".",
                    step(this.unmappedFieldsFetchAutomaton, ".", currentState)
                );
            } else if (value instanceof List) {
                // iterate through list values
                collectUnmappedList(documentFields, (List<?>) value, currentPath, currentState);
            } else {
                // we have a leaf value
                if (this.unmappedFieldsFetchAutomaton.isAccept(currentState) && this.fieldContexts.containsKey(currentPath) == false) {
                    if (value != null) {
                        DocumentField currentEntry = documentFields.get(currentPath);
                        if (currentEntry == null) {
                            List<Object> list = new ArrayList<>();
                            list.add(value);
                            documentFields.put(currentPath, new DocumentField(currentPath, list));
                        } else {
                            currentEntry.getValues().add(value);
                        }
                    }
                }
            }
        }
    }

    private void collectUnmappedList(Map<String, DocumentField> documentFields, Iterable<?> iterable, String parentPath, int lastState) {
        List<Object> list = new ArrayList<>();
        for (Object value : iterable) {
            if (value instanceof Map) {
                collectUnmapped(
                    documentFields,
                    (Map<String, Object>) value,
                    parentPath + ".",
                    step(this.unmappedFieldsFetchAutomaton, ".", lastState)
                );
            } else if (value instanceof List) {
                // weird case, but can happen for objects with "enabled" : "false"
                collectUnmappedList(documentFields, (List<?>) value, parentPath, lastState);
            } else if (this.unmappedFieldsFetchAutomaton.isAccept(lastState) && this.fieldContexts.containsKey(parentPath) == false) {
                list.add(value);
            }
        }
        if (list.isEmpty() == false) {
            DocumentField currentEntry = documentFields.get(parentPath);
            if (currentEntry == null) {
                documentFields.put(parentPath, new DocumentField(parentPath, list));
            } else {
                currentEntry.getValues().addAll(list);
            }
        }
    }

    private static int step(CharacterRunAutomaton automaton, String key, int state) {
        for (int i = 0; state != -1 && i < key.length(); ++i) {
            state = automaton.step(state, key.charAt(i));
        }
        return state;
    }

    public void setNextReader(LeafReaderContext readerContext) {
        for (FieldContext field : fieldContexts.values()) {
            field.valueFetcher.setNextReader(readerContext);
        }
    }

    private static class FieldContext {
        final String fieldName;
        final ValueFetcher valueFetcher;

        FieldContext(String fieldName,
                     ValueFetcher valueFetcher) {
            this.fieldName = fieldName;
            this.valueFetcher = valueFetcher;
        }
    }
}
