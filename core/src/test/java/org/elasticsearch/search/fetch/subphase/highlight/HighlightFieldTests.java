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

package org.elasticsearch.search.fetch.subphase.highlight;

import org.elasticsearch.common.ParsingException;
import org.elasticsearch.common.io.stream.BytesStreamOutput;
import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.text.Text;
import org.elasticsearch.common.xcontent.ToXContent;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentFactory;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.common.xcontent.XContentType;
import org.elasticsearch.test.ESTestCase;

import java.io.IOException;
import java.util.Arrays;

import static org.elasticsearch.test.EqualsHashCodeTestUtils.checkEqualsAndHashCode;

public class HighlightFieldTests extends ESTestCase {

    public HighlightField createTestItem() {
        String name = frequently() ? randomAsciiOfLengthBetween(1, 20) : randomRealisticUnicodeOfCodepointLengthBetween(1, 20);
        Text[] fragments = null;
        if (frequently()) {
            int size = randomIntBetween(0, 5);
            fragments = new Text[size];
            for (int i = 0; i < size; i++) {
                fragments[i] = new Text(
                        frequently() ? randomAsciiOfLengthBetween(10, 30) : randomRealisticUnicodeOfCodepointLengthBetween(10, 30));
            }
        }
        return new HighlightField(name, fragments);
    }

    public void testFromXContent() throws IOException {
        HighlightField highlightField = createTestItem();
        XContentBuilder builder = XContentFactory.contentBuilder(randomFrom(XContentType.values()));
        if (randomBoolean()) {
            builder.prettyPrint();
        }
        builder.startObject();  // we need to wrap xContent output in proper object to be able to parse it
        builder = highlightField.toXContent(builder, ToXContent.EMPTY_PARAMS);
        builder.endObject();
        XContentParser parser = XContentFactory.xContent(builder.bytes()).createParser(builder.bytes());
        HighlightField parsedField = HighlightField.fromXContent(parser);
        assertEquals(highlightField.getName(), parsedField.getName());
        assertArrayEquals(highlightField.getFragments(), parsedField.getFragments());
        if (highlightField.fragments() != null) {
            assertEquals(XContentParser.Token.END_ARRAY, parser.currentToken());
        }
        assertEquals(XContentParser.Token.END_OBJECT, parser.nextToken());
        assertNull(parser.nextToken());
    }

    public void testFromXContentErrors() throws IOException {
        {
            // only arrays or null value allowed
            final String contentString = "{ \"foo\" : \"bar\"}";
            XContentParser parser = XContentFactory.xContent(contentString).createParser(contentString);
            ParsingException e = expectThrows(ParsingException.class, () -> HighlightField.fromXContent(parser));
            assertEquals("unexpected token type [VALUE_STRING]", e.getMessage());
        }

        {
            // parsing should start on OBJECT_START
            final String contentString = "{ \"foo\" : [\"bar\"] }";
            XContentParser parser = XContentFactory.xContent(contentString).createParser(contentString);
            parser.nextToken();
            expectThrows(AssertionError.class, () -> HighlightField.fromXContent(parser));
        }
    }

    /**
     * Test equality and hashCode properties
     */
    public void testEqualsAndHashcode() {
            checkEqualsAndHashCode(createTestItem(), HighlightFieldTests::copy, HighlightFieldTests::mutate);
    }

    public void testSerialization() throws IOException {
        HighlightField testField = createTestItem();
        try (BytesStreamOutput output = new BytesStreamOutput()) {
            testField.writeTo(output);
            try (StreamInput in = output.bytes().streamInput()) {
                HighlightField deserializedCopy = HighlightField.readHighlightField(in);
                assertEquals(testField, deserializedCopy);
                assertEquals(testField.hashCode(), deserializedCopy.hashCode());
                assertNotSame(testField, deserializedCopy);
            }
        }
    }

    private static HighlightField mutate(HighlightField original) {
        Text[] fragments = original.getFragments();
        if (randomBoolean()) {
            return new HighlightField(original.getName()+"_suffix", fragments);
        } else {
            if (fragments == null) {
                fragments = new Text[]{new Text("field")};
            } else {
                fragments = Arrays.copyOf(fragments, fragments.length + 1);
                fragments[fragments.length - 1] = new Text("something new");
            }
            return new HighlightField(original.getName(), fragments);
        }
    }

    private static HighlightField copy(HighlightField original) {
        return new HighlightField(original.getName(), original.getFragments());
    }

}
