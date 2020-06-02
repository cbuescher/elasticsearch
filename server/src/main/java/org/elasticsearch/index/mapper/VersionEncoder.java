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

import org.apache.lucene.util.BytesRef;
import org.apache.lucene.util.BytesRefBuilder;

import java.util.Arrays;

public class VersionEncoder {

    /**
     * TODOs
     * - add more validation on input string
     * - add build part that is ignored in sorting
     */
    public static BytesRef encodeVersion(String versionString) {
        // System.out.println("encoding: " + versionString);
        // split LHS (dot separated versions) and pre-release part
        String[] mainParts = versionString.split("-");
        String[] lhsVersions = mainParts[0].split("\\.");
        BytesRefBuilder brb = new BytesRefBuilder();
        for (String versionPart : lhsVersions) {
            encodeVersionPartNumeric(versionPart, brb);
        }
        brb.append((byte) 0); // mark lhs finished
        // encode whether version has pre-release parts
        if (mainParts.length == 2) {
            brb.append((byte) 254);  // versions with pre-release part sort before ones without
            String[] preReleaseParts = mainParts[1].split("\\.");
            for (String preReleasePart : preReleaseParts) {
                boolean isNumeric = preReleasePart.chars().allMatch(x -> Character.isDigit(x));
                if (isNumeric) {
                    brb.append((byte) 0); // mark as numeric
                    encodeVersionPartNumeric(preReleasePart, brb);
                } else {
                    brb.append((byte) 1); // mark as alphanumeric
                    brb.append(new BytesRef(preReleasePart));
                    brb.append((byte) 0); // mark end of alphanumeric
                }
            }
        } else {
            brb.append((byte) 255);
        }
        return brb.get();
    }

    private static void encodeVersionPartNumeric(String part, BytesRefBuilder result) {
        result.append((byte) part.length());
        result.append(new BytesRef(part));
    }

    private static int decodeVersionPartNumeric(byte[] input, StringBuilder result, int pos) {
        int partLength = input[pos++];
        result.append(new BytesRef(Arrays.copyOfRange(input, pos, pos + partLength)).utf8ToString());
        return pos + partLength;
    }

    private static int decodeVersionPartAlphanumeric(byte[] input, StringBuilder result, int pos) {
        int last = pos;
        while (input[last] != 0) {
            last++;
        }
        result.append(new BytesRef(Arrays.copyOfRange(input, pos, last)).utf8ToString());
        return last + 1;
    }

    public static String decodeVersion(BytesRef version) {
        // System.out.println("decoding: " + versionBytes);
        int pos = 0;
        byte[] bytes = version.bytes;
        StringBuilder sb = new StringBuilder();
        while (bytes[pos] != 0) {
            pos = decodeVersionPartNumeric(bytes, sb, pos);
            sb.append(".");
        }
        sb.deleteCharAt(sb.length() - 1);
        pos++;
        // decode whether version has pre-release part
        int preReleaseFlag = bytes[pos++];
        if (preReleaseFlag == (byte) 254) {
            sb.append("-");
            while (pos < version.length) {
                  int isNumeric = bytes[pos++];
                  if (isNumeric == 0) {
                      pos = decodeVersionPartNumeric(bytes, sb, pos);
                  } else {
                      pos = decodeVersionPartAlphanumeric(bytes, sb, pos);
                  }
                  sb.append(".");
             }
            sb.deleteCharAt(sb.length() - 1);
        }
        return sb.toString();
    }

}
