/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License
 * 2.0; you may not use this file except in compliance with the Elastic License
 * 2.0.
 */
package org.elasticsearch.xpack.deprecation;


import com.carrotsearch.hppc.cursors.ObjectCursor;

import org.elasticsearch.Version;
import org.elasticsearch.cluster.metadata.IndexMetadata;
import org.elasticsearch.cluster.metadata.MappingMetadata;
import org.elasticsearch.common.joda.JodaDeprecationPatterns;
import org.elasticsearch.common.settings.Setting;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.index.IndexModule;
import org.elasticsearch.index.IndexSettings;
import org.elasticsearch.index.IndexingSlowLog;
import org.elasticsearch.xpack.core.deprecation.DeprecationIssue;
import org.elasticsearch.index.SearchSlowLog;
import org.elasticsearch.index.SlowLogLevel;
import org.elasticsearch.index.mapper.LegacyGeoShapeFieldMapper;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.BiConsumer;
import java.util.function.BiFunction;
import java.util.function.Function;
import java.util.stream.Collectors;

import static org.elasticsearch.xpack.cluster.routing.allocation.DataTierAllocationDecider.INDEX_ROUTING_EXCLUDE_SETTING;
import static org.elasticsearch.xpack.cluster.routing.allocation.DataTierAllocationDecider.INDEX_ROUTING_INCLUDE_SETTING;
import static org.elasticsearch.xpack.cluster.routing.allocation.DataTierAllocationDecider.INDEX_ROUTING_REQUIRE_SETTING;


/**
 * Index-specific deprecation checks
 */
public class IndexDeprecationChecks {

    private static void fieldLevelMappingIssue(IndexMetadata indexMetadata, BiConsumer<MappingMetadata, Map<String, Object>> checker) {
        for (ObjectCursor<MappingMetadata> mappingMetadata : indexMetadata.getMappings().values()) {
            Map<String, Object> sourceAsMap = mappingMetadata.value.sourceAsMap();
            checker.accept(mappingMetadata.value, sourceAsMap);
        }
    }

    /**
     * iterates through the "properties" field of mappings and returns any predicates that match in the
     * form of issue-strings.
     *
     * @param type the document type
     * @param parentMap the mapping to read properties from
     * @param predicate the predicate to check against for issues, issue is returned if predicate evaluates to true
     * @param fieldFormatter a function that takes a type and mapping field entry and returns a formatted field representation
     * @return a list of issues found in fields
     */
    @SuppressWarnings("unchecked")
    static List<String> findInPropertiesRecursively(String type, Map<String, Object> parentMap,
                                                    Function<Map<?,?>, Boolean> predicate,
                                                    BiFunction<String, Map.Entry<?, ?>, String> fieldFormatter) {
        List<String> issues = new ArrayList<>();
        Map<?, ?> properties = (Map<?, ?>) parentMap.get("properties");
        if (properties == null) {
            return issues;
        }
        for (Map.Entry<?, ?> entry : properties.entrySet()) {
            Map<String, Object> valueMap = (Map<String, Object>) entry.getValue();
            if (predicate.apply(valueMap)) {
                issues.add("[" + fieldFormatter.apply(type, entry) + "]");
            }

            Map<?, ?> values = (Map<?, ?>) valueMap.get("fields");
            if (values != null) {
                for (Map.Entry<?, ?> multifieldEntry : values.entrySet()) {
                    Map<String, Object> multifieldValueMap = (Map<String, Object>) multifieldEntry.getValue();
                    if (predicate.apply(multifieldValueMap)) {
                        issues.add("[" + fieldFormatter.apply(type, entry) + ", multifield: " + multifieldEntry.getKey() + "]");
                    }
                    if (multifieldValueMap.containsKey("properties")) {
                        issues.addAll(findInPropertiesRecursively(type, multifieldValueMap, predicate, fieldFormatter));
                    }
                }
            }
            if (valueMap.containsKey("properties")) {
                issues.addAll(findInPropertiesRecursively(type, valueMap, predicate, fieldFormatter));
            }
        }

        return issues;
    }

    private static String formatDateField(String type, Map.Entry<?, ?> entry) {
        Map<?,?> value = (Map<?, ?>) entry.getValue();
        return "type: " + type + ", field: " + entry.getKey() +", format: "+ value.get("format") +", suggestion: "
            + JodaDeprecationPatterns.formatSuggestion((String)value.get("format"));
    }

    private static String formatField(String type, Map.Entry<?, ?> entry) {
        return "type: " + type + ", field: " + entry.getKey();
    }

    static DeprecationIssue oldIndicesCheck(IndexMetadata indexMetadata) {
        Version createdWith = indexMetadata.getCreationVersion();
        if (createdWith.before(Version.V_7_0_0)) {
                return new DeprecationIssue(DeprecationIssue.Level.CRITICAL,
                    "Index created before 7.0",
                    "https://www.elastic.co/guide/en/elasticsearch/reference/master/" +
                        "breaking-changes-8.0.html",
                    "This index was created using version: " + createdWith,
                    false, null);
        }
        return null;
    }

    static DeprecationIssue tooManyFieldsCheck(IndexMetadata indexMetadata) {
        if (indexMetadata.getSettings().get(IndexSettings.DEFAULT_FIELD_SETTING.getKey()) == null) {
            AtomicInteger fieldCount = new AtomicInteger(0);

            fieldLevelMappingIssue(indexMetadata, ((mappingMetadata, sourceAsMap) -> {
                fieldCount.addAndGet(countFieldsRecursively(mappingMetadata.type(), sourceAsMap));
            }));

            // We can't get to the setting `indices.query.bool.max_clause_count` from here, so just check the default of that setting.
            // It's also much better practice to set `index.query.default_field` than `indices.query.bool.max_clause_count` - there's a
            // reason we introduced the limit.
            if (fieldCount.get() > 1024) {
                return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                    "Number of fields exceeds automatic field expansion limit",
                    "https://www.elastic.co/guide/en/elasticsearch/reference/7.0/breaking-changes-7.0.html" +
                        "#_limiting_the_number_of_auto_expanded_fields",
                    "This index has [" + fieldCount.get() + "] fields, which exceeds the automatic field expansion limit of 1024 " +
                        "and does not have [" + IndexSettings.DEFAULT_FIELD_SETTING.getKey() + "] set, which may cause queries which use " +
                        "automatic field expansion, such as query_string, simple_query_string, and multi_match to fail if fields are not " +
                        "explicitly specified in the query.", false, null);
            }
        }
        return null;
    }

    static DeprecationIssue deprecatedDateTimeFormat(IndexMetadata indexMetadata) {
        Version createdWith = indexMetadata.getCreationVersion();
        if (createdWith.before(Version.V_7_0_0)) {
            List<String> fields = new ArrayList<>();

            fieldLevelMappingIssue(indexMetadata, ((mappingMetadata, sourceAsMap) -> fields.addAll(
                findInPropertiesRecursively(mappingMetadata.type(), sourceAsMap,
                    IndexDeprecationChecks::isDateFieldWithDeprecatedPattern,
                    IndexDeprecationChecks::formatDateField))));

            if (fields.size() > 0) {
                return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                    "Date field format uses patterns which has changed meaning in 7.0",
                    "https://www.elastic.co/guide/en/elasticsearch/reference/7.0/breaking-changes-7.0.html#breaking_70_java_time_changes",
                    "This index has date fields with deprecated formats: " + fields + ". "
                        + JodaDeprecationPatterns.USE_NEW_FORMAT_SPECIFIERS, false, null);
            }
        }
        return null;
    }

    private static boolean isDateFieldWithDeprecatedPattern(Map<?, ?> property) {
        return "date".equals(property.get("type")) &&
            property.containsKey("format") &&
            JodaDeprecationPatterns.isDeprecatedPattern((String) property.get("format"));
    }

    static DeprecationIssue chainedMultiFieldsCheck(IndexMetadata indexMetadata) {
        List<String> issues = new ArrayList<>();
        fieldLevelMappingIssue(indexMetadata, ((mappingMetadata, sourceAsMap) -> issues.addAll(
            findInPropertiesRecursively(mappingMetadata.type(), sourceAsMap,
                IndexDeprecationChecks::containsChainedMultiFields, IndexDeprecationChecks::formatField))));
        if (issues.size() > 0) {
            return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                "Multi-fields within multi-fields",
                "https://www.elastic.co/guide/en/elasticsearch/reference/7.x/breaking-changes-7.3.html" +
                    "#_defining_multi_fields_within_multi_fields",
                "The names of fields that contain chained multi-fields: " + issues, false, null);
        }
        return null;
    }

    private static boolean containsChainedMultiFields(Map<?, ?> property) {
        if (property.containsKey("fields")) {
            Map<?, ?> fields = (Map<?, ?>) property.get("fields");
            for (Object rawSubField: fields.values()) {
                Map<?, ?> subField = (Map<?, ?>) rawSubField;
                if (subField.containsKey("fields")) {
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * warn about existing explicit "_field_names" settings in existing mappings
     */
    static DeprecationIssue fieldNamesDisabledCheck(IndexMetadata indexMetadata) {
        MappingMetadata mapping = indexMetadata.mapping();
        if ((mapping != null) && ClusterDeprecationChecks.mapContainsFieldNamesDisabled(mapping.getSourceAsMap())) {
            return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                    "Index mapping contains explicit `_field_names` enabling settings.",
                    "https://www.elastic.co/guide/en/elasticsearch/reference/7.15/mapping-field-names-field.html#disable-field-names",
                    "The index mapping contains a deprecated `enabled` setting for `_field_names` that should be removed moving foward.",
                false, null);
        }
        return null;
    }

    private static final Set<String> TYPES_THAT_DONT_COUNT;
    static {
        HashSet<String> typesThatDontCount = new HashSet<>();
        typesThatDontCount.add("binary");
        typesThatDontCount.add("geo_point");
        typesThatDontCount.add("geo_shape");
        TYPES_THAT_DONT_COUNT = Collections.unmodifiableSet(typesThatDontCount);
    }
    /* Counts the number of fields in a mapping, designed to count the as closely as possible to
     * org.elasticsearch.index.search.QueryParserHelper#checkForTooManyFields
     */
    @SuppressWarnings("unchecked")
    static int countFieldsRecursively(String type, Map<String, Object> parentMap) {
        int fields = 0;
        Map<?, ?> properties = (Map<?, ?>) parentMap.get("properties");
        if (properties == null) {
            return fields;
        }
        for (Map.Entry<?, ?> entry : properties.entrySet()) {
            Map<String, Object> valueMap = (Map<String, Object>) entry.getValue();
            if (valueMap.containsKey("type")
                && (valueMap.get("type").equals("object") && valueMap.containsKey("properties") == false) == false
                && (TYPES_THAT_DONT_COUNT.contains(valueMap.get("type")) == false)) {
                fields++;
            }

            Map<?, ?> values = (Map<?, ?>) valueMap.get("fields");
            if (values != null) {
                for (Map.Entry<?, ?> multifieldEntry : values.entrySet()) {
                    Map<String, Object> multifieldValueMap = (Map<String, Object>) multifieldEntry.getValue();
                    if (multifieldValueMap.containsKey("type")
                        && (TYPES_THAT_DONT_COUNT.contains(valueMap.get("type")) == false)) {
                        fields++;
                    }
                    if (multifieldValueMap.containsKey("properties")) {
                        fields += countFieldsRecursively(type, multifieldValueMap);
                    }
                }
            }
            if (valueMap.containsKey("properties")) {
                fields += countFieldsRecursively(type, valueMap);
            }
        }

        return fields;
    }

    static DeprecationIssue translogRetentionSettingCheck(IndexMetadata indexMetadata) {
        final boolean softDeletesEnabled = IndexSettings.INDEX_SOFT_DELETES_SETTING.get(indexMetadata.getSettings());
        if (softDeletesEnabled) {
            if (IndexSettings.INDEX_TRANSLOG_RETENTION_SIZE_SETTING.exists(indexMetadata.getSettings())
                || IndexSettings.INDEX_TRANSLOG_RETENTION_AGE_SETTING.exists(indexMetadata.getSettings())) {
                return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                    "translog retention settings are ignored",
                    "https://www.elastic.co/guide/en/elasticsearch/reference/7.15/index-modules-translog.html" +
                        "#index-modules-translog-retention",
                    "translog retention settings [index.translog.retention.size] and [index.translog.retention.age] are ignored " +
                        "because translog is no longer used in peer recoveries with soft-deletes enabled (default in 7.0 or later)",
                    false, null);
            }
        }
        return null;
    }

    static DeprecationIssue checkIndexDataPath(IndexMetadata indexMetadata) {
        if (IndexMetadata.INDEX_DATA_PATH_SETTING.exists(indexMetadata.getSettings())) {
            final String message = String.format(Locale.ROOT,
                "setting [%s] is deprecated and will be removed in a future version", IndexMetadata.INDEX_DATA_PATH_SETTING.getKey());
            final String url = "https://www.elastic.co/guide/en/elasticsearch/reference/7.13/" +
                "breaking-changes-7.13.html#deprecate-shared-data-path-setting";
            final String details = "Found index data path configured. Discontinue use of this setting.";
            return new DeprecationIssue(DeprecationIssue.Level.CRITICAL, message, url, details, false, null);
        }
        return null;
    }
    static DeprecationIssue indexingSlowLogLevelSettingCheck(IndexMetadata indexMetadata) {
        return slowLogSettingCheck(indexMetadata, IndexingSlowLog.INDEX_INDEXING_SLOWLOG_LEVEL_SETTING);
    }

    static DeprecationIssue searchSlowLogLevelSettingCheck(IndexMetadata indexMetadata) {
        return slowLogSettingCheck(indexMetadata, SearchSlowLog.INDEX_SEARCH_SLOWLOG_LEVEL);
    }

    private static DeprecationIssue slowLogSettingCheck(IndexMetadata indexMetadata, Setting<SlowLogLevel> setting) {
        if (setting.exists(indexMetadata.getSettings())) {
            final String message = String.format(Locale.ROOT,
                "setting [%s] is deprecated and will be removed in a future version", setting.getKey());
            final String url = "https://www.elastic.co/guide/en/elasticsearch/reference/7.15/migrating-7.13.html" +
                "#breaking_713_infra_core_deprecations";

            final String details = String.format(Locale.ROOT, "Found [%s] configured. Discontinue use of this setting. Use thresholds.",
                setting.getKey());
            return new DeprecationIssue(DeprecationIssue.Level.WARNING, message, url, details, false, null);
        }
        return null;
    }

    static DeprecationIssue storeTypeSettingCheck(IndexMetadata indexMetadata) {
        final String storeType = IndexModule.INDEX_STORE_TYPE_SETTING.get(indexMetadata.getSettings());
        if (IndexModule.Type.SIMPLEFS.match(storeType)) {
            return new DeprecationIssue(DeprecationIssue.Level.WARNING,
                "[simplefs] is deprecated and will be removed in future versions",
                "https://www.elastic.co/guide/en/elasticsearch/reference/7.15/index-modules-store.html#file-system",
                "[simplefs] is deprecated and will be removed in 8.0. Use [niofs] or other file systems instead. " +
                    "Elasticsearch 7.15 or later uses [niofs] for the [simplefs] store type " +
                    "as it offers superior or equivalent performance to [simplefs].", false, null);
        }
        return null;
    }

    static DeprecationIssue checkRemovedSetting(final Settings settings,
                                                final Setting<?> removedSetting,
                                                final String url,
                                                DeprecationIssue.Level deprecationLevel) {
        if (removedSetting.exists(settings) == false) {
            return null;
        }
        final String removedSettingKey = removedSetting.getKey();
        final String value = removedSetting.get(settings).toString();
        final String message =
            String.format(Locale.ROOT, "setting [%s] is deprecated and will be removed in the next major version", removedSettingKey);
        final String details =
            String.format(Locale.ROOT, "the setting [%s] is currently set to [%s], remove this setting", removedSettingKey, value);
        return new DeprecationIssue(deprecationLevel, message, url, details, false, null);
    }

    static DeprecationIssue checkIndexRoutingRequireSetting(IndexMetadata indexMetadata) {
        return checkRemovedSetting(indexMetadata.getSettings(),
            INDEX_ROUTING_REQUIRE_SETTING,
            "https://www.elastic.co/guide/en/elasticsearch/reference/7.14/data-tier-shard-filtering.html#data-tier-allocation-filters",
            DeprecationIssue.Level.CRITICAL
        );
    }

    static DeprecationIssue checkIndexRoutingIncludeSetting(IndexMetadata indexMetadata) {
        return checkRemovedSetting(indexMetadata.getSettings(),
            INDEX_ROUTING_INCLUDE_SETTING,
            "https://www.elastic.co/guide/en/elasticsearch/reference/7.14/data-tier-shard-filtering.html#data-tier-allocation-filters",
            DeprecationIssue.Level.CRITICAL
        );
    }

    static DeprecationIssue checkIndexRoutingExcludeSetting(IndexMetadata indexMetadata) {
        return checkRemovedSetting(indexMetadata.getSettings(),
            INDEX_ROUTING_EXCLUDE_SETTING,
            "https://www.elastic.co/guide/en/elasticsearch/reference/7.14/data-tier-shard-filtering.html#data-tier-allocation-filters",
            DeprecationIssue.Level.CRITICAL
        );
    }

    protected static boolean isGeoShapeFieldWithDeprecatedParam(Map<?, ?> property) {
        return LegacyGeoShapeFieldMapper.CONTENT_TYPE.equals(property.get("type")) &&
            LegacyGeoShapeFieldMapper.DEPRECATED_PARAMETERS.stream().anyMatch(deprecatedParameter ->
                property.containsKey(deprecatedParameter)
            );
    }

    protected static String formatDeprecatedGeoShapeParamMessage(String type, Map.Entry<?, ?> entry) {
        String fieldName = entry.getKey().toString();
        Map<?, ?> value = (Map<?, ?>) entry.getValue();
        return LegacyGeoShapeFieldMapper.DEPRECATED_PARAMETERS.stream()
            .filter(deprecatedParameter -> value.containsKey(deprecatedParameter))
            .map(deprecatedParameter -> String.format(Locale.ROOT, "parameter [%s] in field [%s]", deprecatedParameter, fieldName))
            .collect(Collectors.joining("; "));
    }

    @SuppressWarnings("unchecked")
    static DeprecationIssue checkGeoShapeMappings(IndexMetadata indexMetadata) {
        if (indexMetadata == null || indexMetadata.mapping() == null) {
            return null;
        }
        Map<String, Object> sourceAsMap = indexMetadata.mapping().getSourceAsMap();
        List<String> messages = findInPropertiesRecursively(LegacyGeoShapeFieldMapper.CONTENT_TYPE, sourceAsMap,
            IndexDeprecationChecks::isGeoShapeFieldWithDeprecatedParam,
            IndexDeprecationChecks::formatDeprecatedGeoShapeParamMessage);
        if (messages.isEmpty()) {
            return null;
        } else {
            String message = String.format(Locale.ROOT,"mappings for index %s contains deprecated geo_shape properties that must be " +
                "removed", indexMetadata.getIndex().getName());
            String details = String.format(Locale.ROOT,
                "The following geo_shape parameters must be removed from %s: [%s]", indexMetadata.getIndex().getName(),
                messages.stream().collect(Collectors.joining("; ")));
            String url = "https://www.elastic.co/guide/en/elasticsearch/reference/6.6/breaking-changes-6.6.html" +
                "#_deprecated_literal_geo_shape_literal_parameters";
            return new DeprecationIssue(DeprecationIssue.Level.CRITICAL, message, url, details, false, null);
        }
    }
}
