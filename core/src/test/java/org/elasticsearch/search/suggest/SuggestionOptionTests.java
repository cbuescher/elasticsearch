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

package org.elasticsearch.search.suggest;

import org.elasticsearch.common.bytes.BytesReference;
import org.elasticsearch.common.io.stream.BytesStreamOutput;
import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.text.Text;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.common.xcontent.XContentType;
import org.elasticsearch.search.suggest.Suggest.Suggestion.Entry.Option;
import org.elasticsearch.test.ESTestCase;

import java.io.IOException;

import static org.elasticsearch.common.xcontent.XContentHelper.toXContent;
import static org.elasticsearch.common.xcontent.XContentParserUtils.ensureExpectedToken;
import static org.elasticsearch.test.EqualsHashCodeTestUtils.checkEqualsAndHashCode;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertToXContentEquivalent;

public class SuggestionOptionTests extends ESTestCase {

    public static Option createTestItem() {
        Text text = new Text(randomAsciiOfLengthBetween(5, 15));
        float score = randomFloat();
        Text highlighted = randomFrom((Text) null, new Text(randomAsciiOfLengthBetween(5, 15)));
        Boolean collateMatch = randomFrom((Boolean) null, randomBoolean());
        return new Option(text, highlighted, score, collateMatch);
    }

    public void testFromXContent() throws IOException {
        Option option = createTestItem();
        XContentType xContentType = randomFrom(XContentType.values());
        boolean humanReadable = randomBoolean();
        BytesReference originalBytes = toXContent(option, xContentType, humanReadable);
        Option parsed;
        try (XContentParser parser = createParser(xContentType.xContent(), originalBytes)) {
            ensureExpectedToken(XContentParser.Token.START_OBJECT, parser.nextToken(), parser::getTokenLocation);
            parsed = Option.fromXContent(parser);
            assertEquals(XContentParser.Token.END_OBJECT, parser.currentToken());
            assertNull(parser.nextToken());
        }
        assertEquals(option.getText(), parsed.getText());
        assertEquals(option.getHighlighted(), parsed.getHighlighted());
        assertEquals(option.getScore(), parsed.getScore(), Float.MIN_VALUE);
        assertEquals(option.collateMatch(), parsed.collateMatch());
        assertToXContentEquivalent(originalBytes, toXContent(parsed, xContentType, humanReadable), xContentType);
    }

    public void testToXContent() throws IOException {
        Option option = new Option(new Text("someText"), new Text("somethingHighlighted"), 1.3f, true);
        BytesReference xContent = toXContent(option, XContentType.JSON, randomBoolean());
        assertEquals("{\"text\":\"someText\","
                      + "\"highlighted\":\"somethingHighlighted\","
                      + "\"score\":1.3,"
                      + "\"collate_match\":true"
                   + "}"
                   , xContent.utf8ToString());
    }

    public void testEqualsAndHashcode() {
        checkEqualsAndHashCode(createTestItem(), this::copy, this::mutate);
    }

    private Option copy(Option original) throws IOException {
        try (BytesStreamOutput output = new BytesStreamOutput()) {
            original.writeTo(output);
            try (StreamInput in = output.bytes().streamInput()) {
                Option option = new Option();
                option.readFrom(in);
                return option;
            }
        }
    }

    /**
     * change the original in one aspect
     */
    private Option mutate(Option original) {
        Text text = original.getText();
        Text highlighted = original.getHighlighted();
        float score = original.getScore();
        boolean collateMatch = original.collateMatch();
        switch (randomIntBetween(0, 3)) {
            case 0:
                text = new Text(text + "_prefix");
                break;
            case 1:
                highlighted = highlighted == null ? new Text("something") : new Text(highlighted + "_prefix");
                break;
            case 2:
                score = score * 2;
                break;
            case 3:
                collateMatch = collateMatch == false;
                break;
        }
        return new Option(text, highlighted, score, collateMatch);
    }
}
