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

package org.elasticsearch.search.internal;

import org.elasticsearch.common.bytes.BytesReference;
import org.elasticsearch.common.io.stream.BytesStreamOutput;
import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.xcontent.ToXContent;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentFactory;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.common.xcontent.XContentType;
import org.elasticsearch.common.xcontent.json.JsonXContent;
import org.elasticsearch.test.ESTestCase;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

import static org.elasticsearch.test.EqualsHashCodeTestUtils.checkEqualsAndHashCode;

public class SearchSortValuesTests extends ESTestCase {

    public static SearchSortValues createTestItem() {
        List<Supplier<Object>> valueSuppliers = new ArrayList<>();
        // this should reflect all values that are allowed to go through the transport layer
        valueSuppliers.add(() -> null);
        valueSuppliers.add(() -> randomInt());
        valueSuppliers.add(() -> randomLong());
        valueSuppliers.add(() -> randomDouble());
        valueSuppliers.add(() -> randomFloat());
        valueSuppliers.add(() -> randomByte());
        valueSuppliers.add(() -> randomShort());
        valueSuppliers.add(() -> randomBoolean());
        valueSuppliers.add(() -> frequently() ? randomAsciiOfLengthBetween(1, 30) : randomRealisticUnicodeOfCodepointLength(30));

        int size = randomInt(20);
        Object[] values = new Object[size];
        for (int i = 0; i < size; i++) {
            Supplier<Object> supplier = randomFrom(valueSuppliers);
            values[i] = supplier.get();
        }
        return new SearchSortValues(values);
    }

    public void testFromXContent() throws IOException {
        SearchSortValues sortValues = createTestItem();
        XContentType xcontentType = randomFrom(XContentType.values());
        XContentBuilder builder = XContentFactory.contentBuilder(xcontentType);
        if (randomBoolean()) {
            builder.prettyPrint();
        }
        builder.startObject(); // we need to wrap xContent output in proper object to create a parser for it
        builder = sortValues.toXContent(builder, ToXContent.EMPTY_PARAMS);
        builder.endObject();

        XContentParser parser = createParser(builder);
        parser.nextToken(); // skip to the elements field name token, fromXContent advances from there if called from ourside
        parser.nextToken();
        if (sortValues.sortValues().length > 0) {
            SearchSortValues parsed = SearchSortValues.fromXContent(parser);

            assertEquivalent(builder.bytes(), toXContent(parsed,  xcontentType), xcontentType);
            parser.nextToken();
        }
        assertEquals(XContentParser.Token.END_OBJECT, parser.currentToken());
        assertNull(parser.nextToken());
    }

    public void testToXContent() throws IOException {
        SearchSortValues sortValues = new SearchSortValues(new Object[]{ 1, "foo", 3.0});
        XContentBuilder builder = JsonXContent.contentBuilder();
        builder.startObject();
        sortValues.toXContent(builder, ToXContent.EMPTY_PARAMS);
        builder.endObject();
        assertEquals("{\"sort\":[1,\"foo\",3.0]}", builder.string());
    }

    /**
     * Test equality and hashCode properties
     */
    public void testEqualsAndHashcode() {
        checkEqualsAndHashCode(createTestItem(), SearchSortValuesTests::copy, SearchSortValuesTests::mutate);
    }

    public void testSerialization() throws IOException {
        SearchSortValues sortValues = createTestItem();
        try (BytesStreamOutput output = new BytesStreamOutput()) {
            sortValues.writeTo(output);
            try (StreamInput in = output.bytes().streamInput()) {
                SearchSortValues deserializedCopy = new SearchSortValues(in);
                assertEquals(sortValues, deserializedCopy);
                assertEquals(sortValues.hashCode(), deserializedCopy.hashCode());
                assertNotSame(sortValues, deserializedCopy);
            }
        }
    }

    private static SearchSortValues mutate(SearchSortValues original) {
        Object[] sortValues = original.sortValues();
        if (sortValues.length == 0) {
            return new SearchSortValues(new Object[] { 1 });
        }
        return new SearchSortValues(Arrays.copyOf(sortValues, sortValues.length + 1));
    }

    private static SearchSortValues copy(SearchSortValues original) {
        return new SearchSortValues(Arrays.copyOf(original.sortValues(), original.sortValues().length));
    }

    /**
     * Asserts that the provided {@link BytesReference}s hold the same content.
     * The comparison is done between the map representation of the provided
     * objects.
     */
    // TODO move this to a common place
    public static void assertEquivalent(BytesReference expected, BytesReference actual, XContentType xContentType) throws IOException {
        // we tried comparing byte per byte, but that didn't fly for a couple of
        // reasons:
        // 1) whenever anything goes through a map while parsing, ordering is
        // not preserved, which is perfectly ok
        // 2) Jackson SMILE parser parses floats as double, which then get
        // printed out as double (with double precision)
        try (XContentParser actualParser = xContentType.xContent().createParser(actual)) {
            Map<String, Object> actualMap = actualParser.map();
            try (XContentParser expectedParser = xContentType.xContent().createParser(expected)) {
                Map<String, Object> expectedMap = expectedParser.map();
                assertEquals(expectedMap, actualMap);
            }
        }
    }

    /**
     * Returns the bytes that represent the XContent output of the provided
     * {@link ToXContent} object, using the provided {@link XContentType}. Wraps
     * the output into a new anonymous object depending on the value of the
     * wrapInObject argument.
     */
    // TODO move this to a common place
    private static BytesReference toXContent(ToXContent toXContent, XContentType xContentType) throws IOException {
        try (XContentBuilder builder = XContentBuilder.builder(xContentType.xContent())) {
            builder.startObject();
            toXContent.toXContent(builder, ToXContent.EMPTY_PARAMS);
            builder.endObject();
            return builder.bytes();
        }
    }
}
