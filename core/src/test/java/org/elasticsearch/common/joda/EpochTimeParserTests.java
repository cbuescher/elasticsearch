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

package org.elasticsearch.common.joda;

import org.elasticsearch.test.ESTestCase;
import org.joda.time.DateTimeZone;
import org.joda.time.MutableDateTime;
import org.joda.time.format.DateTimeFormatter;
import org.junit.Test;

public class EpochTimeParserTests extends ESTestCase {

    @Test
    public void testParseIntoTimeZoneException() {
        DateTimeFormatter parser = Joda.forPattern("epoch_millis").parser().withZoneUTC();
        MutableDateTime date = new MutableDateTime(1970, 1, 1, 0, 0, 0, 0, DateTimeZone.UTC);
        assertEquals(8, parser.parseInto(date, "12345678", 0));
        assertEquals(12345678L, date.getMillis());

        parser = Joda.forPattern("epoch_millis").parser().withZone(DateTimeZone.forID("EST"));
        date = new MutableDateTime(1970, 1, 1, 0, 0, 0, 0, DateTimeZone.UTC);
        assertEquals(8, parser.parseInto(date, "12345678", 0));
        assertEquals(12345678L, date.getMillis());
    }

}
