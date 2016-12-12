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

package org.elasticsearch.common.xcontent;

import org.elasticsearch.test.ESTestCase;

import java.io.IOException;

public class SmileFloatTests extends ESTestCase {

    public void testFloatSmileRoundtrip() throws IOException {
        XContentType type = XContentType.SMILE;
        float d = 0.2f;
        XContentBuilder builder = XContentFactory.contentBuilder(type);
        builder.startObject(); // we need to wrap xContent output in proper object to create a parser for it
        builder = builder.field("myfloat", d);
        builder.endObject();

        XContentParser parser = type.xContent().createParser(builder.bytes());
        parser.nextToken(); // skip to the elements field name token, fromXContent advances from there if called from ourside
        parser.nextToken();
        parser.nextToken();
        float parsed = parser.floatValue(); // <- this works
        assertEquals(d, parsed, Float.MIN_VALUE);

        parser = type.xContent().createParser(builder.bytes());
        parser.nextToken(); // skip to the elements field name token, fromXContent advances from there if called from ourside
        parser.nextToken();
        parser.nextToken();
        parsed = parser.numberValue().floatValue(); // <- this works
        assertEquals(d, parsed, Float.MIN_VALUE);

        parser = type.xContent().createParser(builder.bytes());
        parser.nextToken(); // skip to the elements field name token, fromXContent advances from there if called from ourside
        parser.nextToken();
        parser.nextToken();
        Number parsedNumber = parser.numberValue();
        assertTrue(parsedNumber instanceof Double); // <- not true for XContentType.CBOR, there its Float
        assertEquals(d, parsedNumber.floatValue(), Float.MIN_VALUE);
        assertEquals(0.20000000298023224, (double) parsedNumber, Double.MIN_VALUE); // <- not true for XContentType.JSON & YAML
    }


}
