/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the "Elastic License
 * 2.0", the "GNU Affero General Public License v3.0 only", and the "Server Side
 * Public License v 1"; you may not use this file except in compliance with, at
 * your election, the "Elastic License 2.0", the "GNU Affero General Public
 * License v3.0 only", or the "Server Side Public License, v 1".
 */

package org.elasticsearch.aggregations.bucket;

import com.carrotsearch.randomizedtesting.annotations.Repeat;

import com.carrotsearch.randomizedtesting.annotations.Seed;
import org.elasticsearch.action.DocWriteRequest;
import org.elasticsearch.action.index.IndexRequestBuilder;
import org.elasticsearch.action.search.SearchPhaseExecutionException;
import org.elasticsearch.aggregations.AggregationIntegTestCase;
import org.elasticsearch.common.breaker.CircuitBreakingException;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.search.aggregations.bucket.composite.TermsValuesSourceBuilder;
import org.elasticsearch.test.ESIntegTestCase;
import org.elasticsearch.xcontent.XContentBuilder;
import org.elasticsearch.xcontent.XContentFactory;
import org.hamcrest.core.Every;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.IntStream;
import java.util.stream.LongStream;

import static org.elasticsearch.indices.breaker.HierarchyCircuitBreakerService.REQUEST_CIRCUIT_BREAKER_LIMIT_SETTING;
import static org.elasticsearch.indices.breaker.HierarchyCircuitBreakerService.REQUEST_CIRCUIT_BREAKER_TYPE_SETTING;
import static org.elasticsearch.indices.breaker.HierarchyCircuitBreakerService.TOTAL_CIRCUIT_BREAKER_LIMIT_SETTING;
import static org.elasticsearch.indices.breaker.HierarchyCircuitBreakerService.USE_REAL_MEMORY_USAGE_SETTING;
import static org.elasticsearch.search.aggregations.AggregationBuilders.composite;
import static org.elasticsearch.search.aggregations.AggregationBuilders.topHits;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertAcked;
import static org.hamcrest.Matchers.instanceOf;

@ESIntegTestCase.ClusterScope(numDataNodes = 3)
@Seed("E5524FB23B3BF049:709C06F1EF843BB9")
public class AggregationsCircuitBreakingIT extends AggregationIntegTestCase {
    @Override
    protected Settings nodeSettings(int nodeOrdinal, Settings otherSettings) {
        return Settings.builder()
                .put(super.nodeSettings(nodeOrdinal, otherSettings))
                .put(REQUEST_CIRCUIT_BREAKER_TYPE_SETTING.getKey(), "memory")
                .build();
    }

    private void createIndex() throws IOException {
        XContentBuilder mappingBuilder = XContentFactory.jsonBuilder();
        mappingBuilder.startObject();
        mappingBuilder.startObject("properties");
        {
            mappingBuilder.startObject("integer");
            mappingBuilder.field("type", "integer");
            mappingBuilder.endObject();
        }
        {
            mappingBuilder.startObject("long");
            mappingBuilder.field("type", "long");
            mappingBuilder.endObject();
        }

        mappingBuilder.endObject(); // properties
        mappingBuilder.endObject();

        assertAcked(
                prepareCreate("index").setSettings(Settings.builder().put("index.number_of_shards", randomIntBetween(1, 10)).build())
                        .setMapping(mappingBuilder)
        );

        int minimumCombinations = 10_000_000; // To fill the 65k buckets in the composite agg, times the 100 top_hits count
        int docCount = randomIntBetween(100, 10000); // 100 at least to fill the top_hits agg
        int integerFieldMvCount = randomIntBetween(100, (int) Math.ceil((double) minimumCombinations / docCount));
        int longFieldMvCount = (int) Math.ceil((double) minimumCombinations / docCount / integerFieldMvCount);

        List<IndexRequestBuilder> docs = new ArrayList<>();
        for (int i = 0; i < docCount; i++) {
            XContentBuilder docSource = XContentFactory.jsonBuilder();
            docSource.startObject();
            final int docNumber = i;
            List<Integer> integerValues = IntStream.range(0, integerFieldMvCount).map(x -> docNumber + x * 100).boxed().toList();
            List<Long> longValues = LongStream.range(0, longFieldMvCount).map(x -> docNumber + x * 100).boxed().toList();
            docSource.field("integer", integerValues);
            docSource.field("long", longValues);
            docSource.endObject();

            docs.add(prepareIndex("index").setOpType(DocWriteRequest.OpType.CREATE).setSource(docSource));
        }
        indexRandom(true, false, docs);
    }

    public void testCBTrippingOnBigComposite() throws IOException {
        createIndex();

        updateClusterSettings(
                Settings.builder()
                        .put(TOTAL_CIRCUIT_BREAKER_LIMIT_SETTING.getKey(), "100MB")
                        .put(REQUEST_CIRCUIT_BREAKER_LIMIT_SETTING.getKey(), "10MB")
                        .put(USE_REAL_MEMORY_USAGE_SETTING.getKey(), true)
        );

        var searchRequestBuilder = prepareSearch("index").setSize(0)
                .addAggregation(
                        composite(
                                "composite",
                                List.of(new TermsValuesSourceBuilder("integer").field("integer"), new TermsValuesSourceBuilder("long").field("long"))
                        ).size(65536).subAggregation(
                                topHits("top_hits").size(100)
                        )
                );

        try {
            searchRequestBuilder.get();

            fail("Expected the breaker to trip");
        } catch (SearchPhaseExecutionException e) {
            assertThat(List.of(e.guessRootCauses()), Every.everyItem(instanceOf(CircuitBreakingException.class)));
        } finally {
            updateClusterSettings(
                    Settings.builder()
                            .putNull(TOTAL_CIRCUIT_BREAKER_LIMIT_SETTING.getKey())
                            .putNull(REQUEST_CIRCUIT_BREAKER_LIMIT_SETTING.getKey())
                            .putNull(USE_REAL_MEMORY_USAGE_SETTING.getKey())
            );
        }
    }
}
