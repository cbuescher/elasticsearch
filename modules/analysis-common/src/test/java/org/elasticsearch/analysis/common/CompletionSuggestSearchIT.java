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
package org.elasticsearch.analysis.common;

import com.carrotsearch.randomizedtesting.generators.RandomStrings;

import org.apache.lucene.util.LuceneTestCase.SuppressCodecs;
import org.elasticsearch.action.search.SearchResponse;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.plugins.Plugin;
import org.elasticsearch.search.suggest.Suggest.Suggestion.Entry.Option;
import org.elasticsearch.search.suggest.SuggestBuilder;
import org.elasticsearch.search.suggest.SuggestBuilders;
import org.elasticsearch.search.suggest.completion.CompletionSuggestionBuilder;
import org.elasticsearch.test.ESSingleNodeTestCase;

import java.io.IOException;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

import static org.elasticsearch.common.xcontent.XContentFactory.jsonBuilder;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertAcked;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertAllSuccessful;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.notNullValue;

@SuppressCodecs("*") // requires custom completion format
public class CompletionSuggestSearchIT extends ESSingleNodeTestCase {
    private final String INDEX = RandomStrings.randomAsciiOfLength(random(), 10).toLowerCase(Locale.ROOT);
    private final String FIELD = RandomStrings.randomAsciiOfLength(random(), 10).toLowerCase(Locale.ROOT);
    private final String TYPE = "_doc";

    @Override
    protected Collection<Class<? extends Plugin>> getPlugins() {
        return Collections.singleton(CommonAnalysisPlugin.class);
    }

    public void testNoMissingOptions() throws Exception {
        Settings.Builder settingsBuilder = Settings.builder()
                .put("index.number_of_shards", 1)
                .put("index.analysis.filter.my_synonym.type", "synonym")
                .putList("index.analysis.filter.my_synonym.synonyms",
                        "meyer => meyer, m",
                        "mueller => mueller, m",
                        "mann => mann, m",
                        "meier => meier, m",
                        "murnau => murnau, m",
                        "munch => munch, m",
                        "myerz = myerz, m",
                        "mohn => mohn, m",
                        "mahler => mahler, m")
                .putList("index.analysis.analyzer.my_analyzer.filter", "my_synonym")
                .put("index.analysis.analyzer.my_analyzer.tokenizer", "whitespace");

        createIndexAndMappingAndSettings(settingsBuilder.build());

        String[] names = new String[] { "anna meyer", "anna mueller", "anna mann", "anna murnau", "anna munch", "anna myerz", "anna mohn",
                "anna mahler", "anna meier" };

        for (int i=0; i < names.length; i++) {
            client().prepareIndex(INDEX, TYPE, Integer.toString(i + 1)).setSource(jsonBuilder()
                    .startObject()
                    .field("title", names[i])
                    .startObject(FIELD)
                    .startArray("input").value(names[i]).endArray()
                    .field("weight", i + 1)
                    .endObject()
                    .endObject()
            ).get();
        }

        client().admin().indices().prepareRefresh(INDEX).get();

//        CompletionSuggestionBuilder suggestionBuilder = SuggestBuilders.completionSuggestion(FIELD).prefix("anna").size(20);
//        SearchResponse searchResponse = client().prepareSearch(INDEX)
//                .suggest(new SuggestBuilder().addSuggestion("test-suggest", suggestionBuilder)).get();
//
//        assertAllSuccessful(searchResponse);
//        assertThat(searchResponse.getSuggest().getSuggestion("test-suggest"), is(notNullValue()));
//        List<? extends Option> options = searchResponse.getSuggest().getSuggestion("test-suggest").getEntries().get(0).getOptions();
//        assertEquals(names.length, options.size());
//
//        double[] scores = options.stream().mapToDouble(Option::getScore).toArray();
        double[] expectedScores =  new double[] { 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0 };
//        for (int i = 0; i < 9; i++) {
//            assertEquals(expectedScores[i], scores[i], 0.0000001);
//        }

        for (int size = 1; size <= 9; size++) {
        CompletionSuggestionBuilder suggestionBuilder = SuggestBuilders.completionSuggestion(FIELD).prefix("anna").size(size);
        SearchResponse searchResponse = client().prepareSearch(INDEX)
                .suggest(new SuggestBuilder().addSuggestion("test-suggest", suggestionBuilder)).get();

        assertAllSuccessful(searchResponse);
        assertThat(searchResponse.getSuggest().getSuggestion("test-suggest"), is(notNullValue()));
        List<? extends Option> options = searchResponse.getSuggest().getSuggestion("test-suggest").getEntries().get(0).getOptions();
        assertEquals(size, options.size());


        double[] scores = options.stream().mapToDouble(Option::getScore).toArray();
        System.out.println(Arrays.toString(scores));
        for (int i = 0; i < size; i++) {
            assertEquals(expectedScores[i], scores[i], 0.0000001);
        }
        }

    }

    private void createIndexAndMappingAndSettings(Settings settings) throws IOException {
        XContentBuilder mapping = jsonBuilder().startObject()
                .startObject("properties")
                .startObject("title")
                    .field("type", "keyword")
                .endObject()
                .startObject(FIELD)
                .field("type", "completion")
                .field("analyzer", "my_analyzer");

        mapping = mapping.endObject()
                .endObject()
                .endObject();

        assertAcked(client().admin().indices().prepareCreate(INDEX)
                .setSettings(Settings.builder().put(settings))
                .addMapping("_doc", mapping)
                .get());
    }

}
