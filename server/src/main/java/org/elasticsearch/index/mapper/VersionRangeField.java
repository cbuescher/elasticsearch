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

package org.elasticsearch.index.mapper;

import org.apache.lucene.document.Field;
import org.apache.lucene.document.FieldType;
import org.apache.lucene.util.BytesRef;

public class VersionRangeField extends Field {

    // public static final int BYTES = 16;

    private static final FieldType TYPE;
    static {
      TYPE = new FieldType();
     // TYPE.setDimensions(2, BYTES);
      TYPE.freeze();
    }

    public VersionRangeField(String name, final BytesRef min, final BytesRef max) {
      super(name, TYPE);
      //setRangeValues(min, max);
    }

//    /**
//     * Change (or set) the min/max values of the field.
//     * @param min range min value
//     * @param max range max value
//     */
//    public void setRangeValues(BytesRef min, BytesRef max) {
//      final byte[] bytes;
//      if (fieldsData == null) {
//        bytes = new byte[BYTES*2];
//        fieldsData = new BytesRef(bytes);
//      } else {
//        bytes = ((BytesRef)fieldsData).bytes;
//      }
//      encode(min, max, bytes);
//    }
//
//    /** encode the min/max range into the provided byte array */
//    private static void encode(final BytesRef min, final BytesRef max, final byte[] bytes) {
//      // encode min and max value (consistent w/ InetAddressPoint encoding)
//      // ensure min is lt max
//      if (FutureArrays.compareUnsigned(min.bytes, 0, BYTES, max.bytes, 0, BYTES) > 0) {
//        throw new IllegalArgumentException("min value cannot be greater than max value for InetAddressRange field");
//      }
//      System.arraycopy(min.bytes, 0, bytes, 0, BYTES);
//      System.arraycopy(max.bytes, 0, bytes, BYTES, BYTES);
//    }

}
