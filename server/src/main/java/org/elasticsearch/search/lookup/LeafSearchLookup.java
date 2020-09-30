/*
 * Licensed to Elasticsearch under one or more contributor
 * license agreements. See the NOTICE file distributed with
 * this work for additional information regarding copyright
 * ownership. Elasticsearch licenses this file to you under
 * the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.elasticsearch.search.lookup;

import org.apache.lucene.index.LeafReaderContext;
import org.elasticsearch.ElasticsearchException;
import org.elasticsearch.common.CheckedBiConsumer;
import org.elasticsearch.common.lucene.index.SequentialStoredFieldsLeafReader;
import org.elasticsearch.index.fieldvisitor.FieldsVisitor;

import java.io.IOException;
import java.util.Map;

/**
 * Per-segment version of {@link SearchLookup}.
 */
public class LeafSearchLookup {

    private final LeafReaderContext ctx;
    private final LeafDocLookup docMap;
    private final SourceLookup sourceLookup;
    private final LeafFieldsLookup fieldsLookup;
    private final Map<String, Object> asMap;
    private final CheckedBiConsumer<Integer, FieldsVisitor, IOException> fieldReader;

    public LeafSearchLookup(LeafReaderContext ctx, LeafDocLookup docMap, SourceLookup sourceLookup, LeafFieldsLookup fieldsLookup) {
        this.ctx = ctx;
        this.docMap = docMap;
        this.sourceLookup = sourceLookup;
        try {
            if (ctx.reader() instanceof SequentialStoredFieldsLeafReader) {
                SequentialStoredFieldsLeafReader lf = (SequentialStoredFieldsLeafReader) ctx.reader();
                fieldReader = lf.getSequentialStoredFieldsReader()::visitDocument;
            } else {
                fieldReader = ctx.reader()::document;
            }
        } catch (Exception e) {
            throw new ElasticsearchException("Error creating LeafSearchLookup", e);
        }
        this.fieldsLookup = fieldsLookup;
        this.asMap = Map.of(
                "doc", docMap,
                "_doc", docMap,
                "_source", sourceLookup,
                "_fields", fieldsLookup);
    }

    public Map<String, Object> asMap() {
        return this.asMap;
    }

    public SourceLookup source() {
        return this.sourceLookup;
    }

    public LeafFieldsLookup fields() {
        return this.fieldsLookup;
    }

    public LeafDocLookup doc() {
        return this.docMap;
    }

    public void setDocument(int docId) {
        docMap.setDocument(docId);
        // TODO not sure that to pass in here as a fieldReader
        sourceLookup.setSegmentAndDocument(ctx, fieldReader, docId);
        fieldsLookup.setDocument(docId);
    }
}
