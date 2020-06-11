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
import java.util.regex.Pattern;

/**
 * Encodes a version string to a {@link BytesRef} while ensuring an ordering that makes sense for
 * software versions.
 *
 * Version strings are considered to consist of three parts in this order:
 * <ul>
 *  <li> a numeric major.minor.patch part starting the version string (e.g. 1.2.3)
 *  <li> an optional "pre-release" part that starts with a `-` character and can consist of several alpha-numerical sections
 *  separated by dots (e.g. "-alpha.2.3")
 *  <li> an optional "build" part that starts with a `+` character. This will simply be treated as a prefix with no guaranteed ordering,
 *  (although the ordering should be alphabetical in most cases).
 * </ul>
 *
 * In the default mode (@link {@link AlphanumSortMode#SEMVER}, the version string is encoded such that the ordering works like the following:
 * <ul>
 *  <li> Major, minor, and patch versions are always compared numerically
 *  <li> pre-release version have lower precedence than a normal version. (e.g 1.0.0-alpha < 1.0.0)
 *  <li> the precedence for pre-release versions with same main version is calculated comparing each dot separated identifier from
 *  left to right. Identifiers consisting of only digits are compared numerically and identifiers with letters or hyphens are compared
 *  lexically in ASCII sort order. Numeric identifiers always have lower precedence than non-numeric identifiers.
 * </ul>
 *
 * The sorting for the main version part in {@link AlphanumSortMode#HONOUR_NUMERALS} is the same except that in the pre-release part,
 * mixed alpha-numerical identifiers are compared grouping all consecutive digits and treating them as a number with numerical ordering.
 * For example, "alpha2" would sort _before" "alpha11" in this mode.
 */
public class VersionEncoder {

    private static final byte LHS_FINISHED_BYTE = (byte) 0;
    private static final char DOT_SEPARATOR = '.';
    private static final byte DOT_SEPARATOR_BYTE = (byte) DOT_SEPARATOR;
    private static final char PRERELESE_SEPARATOR = '-';
    private static final byte PRERELESE_SEPARATOR_BYTE = (byte) PRERELESE_SEPARATOR;
    private static final char BUILD_SEPARATOR = '+';
    private static final byte BUILD_SEPARATOR_BYTE = (byte) BUILD_SEPARATOR;
    private static final char NO_PRERELESE_SEPARATOR = '@';
    private static final byte NO_PRERELESE_SEPARATOR_BYTE = (byte) NO_PRERELESE_SEPARATOR;


    // Regex to test version validity: \d+(\.\d+)*(-[\-\dA-Za-z]+){0,1}(\.[-\dA-Za-z]+)*(\+[\.\-\dA-Za-z]+)?
    private static Pattern LEGAL_VERSION_PATTERN = Pattern.compile(
        "\\d+(\\.\\d+)*(-[\\-\\dA-Za-z]+){0,1}(\\.[\\-\\dA-Za-z]+)*(\\+[\\.\\-\\dA-Za-z]+)?"
    );

    /**
     * Defines how version parts consisting of both alphabetical and numerical characters are ordered
     */
    public enum AlphanumSortMode {
        /**
         * strict semver precedence treats everything alphabetically, e.g. "rc11" &lt; "rc2"
         */
        SEMVER
        {
            @Override
            public void encode(String part, BytesRefBuilder result) {
                result.append((byte) 2); // mark as alphanumeric
                result.append(new BytesRef(part));
                result.append(DOT_SEPARATOR_BYTE);
            }

            @Override
            public int decode(byte[] input, StringBuilder result, int pos) {
                int last = pos;
                while (input[last] != DOT_SEPARATOR_BYTE) {
                    last++;
                }
                result.append(new BytesRef(Arrays.copyOfRange(input, pos, last)).utf8ToString());
                result.append(DOT_SEPARATOR);
                return last + 1;
            }
        },
        /**
         * This mode will order mixed strings so that the numeric parts are treated with numeric ordering,
         * e.g. "rc2" &lt; "rc11", "alpha523" &lt; "alpha1234"
         */
        HONOUR_NUMERALS
        {
            @Override
            public void encode(String part, BytesRefBuilder result) {
                result.append((byte) 2); // mark as alphanumeric
                int pos = 0;
                while (pos < part.length()) {
                    if (Character.isDigit(part.charAt(pos))) {
                        // found beginning of number block, so get its length
                        int start = pos;
                        BytesRefBuilder number = new BytesRefBuilder();
                        while (pos < part.length() && Character.isDigit(part.charAt(pos))) {
                            number.append((byte) part.charAt(pos));
                            pos++;
                        }
                        int length = pos - start;
                        result.append((byte) 3); // mark that the following is a length byte for later decoding
                        result.append((byte) length);
                        result.append(number);
                    } else {
                        result.append((byte) part.charAt(pos));
                        pos++;
                    }
                }
                result.append(DOT_SEPARATOR_BYTE);
            }

            @Override
            public int decode(byte[] input, StringBuilder result, int pos) {
                while (input[pos] != DOT_SEPARATOR_BYTE) {
                    if (input[pos] != 3) {
                        result.append((char) input[pos++]);
                    } else {
                        // skip also length byte
                        pos +=2;
                    }
                }
                result.append(DOT_SEPARATOR);
                pos++;
                return pos;
            }
        };

        public abstract void encode(String part, BytesRefBuilder result);
        public abstract int decode(byte[] input, StringBuilder result, int pos);
    }

    /**
     * TODOs
     * - add more validation on input string
     * - add build part that is ignored in sorting
     */
    public static BytesRef encodeVersion(String versionString, AlphanumSortMode mode) {
        System.out.println("encoding: " + versionString);
        if (legalVersionString(versionString) == false) {
            throw new IllegalArgumentException("Illegal version string: " + versionString);
        }
        // strip "build" suffix
        int buildSuffixStart = versionString.indexOf(BUILD_SEPARATOR);
        String buildSuffixPart = null;
        if (buildSuffixStart > 0) {
           buildSuffixPart = versionString.substring(buildSuffixStart);
           versionString = versionString.substring(0, buildSuffixStart);
        }

        // split LHS (dot separated versions) and pre-release part
        String[] mainParts = versionString.split("-");
        String[] lhsVersions = mainParts[0].split("\\.");
        BytesRefBuilder brb = new BytesRefBuilder();
        for (String versionPart : lhsVersions) {
            encodeVersionPartNumeric(versionPart, brb, false);
        }
        brb.append(LHS_FINISHED_BYTE);
        // encode whether version has pre-release parts
        if (mainParts.length == 2) {
            brb.append(PRERELESE_SEPARATOR_BYTE);  // versions with pre-release part sort before ones without
            String[] preReleaseParts = mainParts[1].split("\\.");
            for (String preReleasePart : preReleaseParts) {
                boolean isNumeric = preReleasePart.chars().allMatch(x -> Character.isDigit(x));
                if (isNumeric) {
                    encodeVersionPartNumeric(preReleasePart, brb, true);
                } else {
                    mode.encode(preReleasePart, brb);
                }
            }
        } else {
            brb.append(NO_PRERELESE_SEPARATOR_BYTE);
        }
        // append build part at the end
        if (buildSuffixPart != null) {
            brb.append(new BytesRef(buildSuffixPart));
        }
        System.out.println("encoding: " + brb.get());
        return brb.get();
    }

    static boolean legalVersionString(String versionString) {
        return LEGAL_VERSION_PATTERN.matcher(versionString).matches();
    }

    /**
     * @param part the version string to encode
     * @param result the builder for the result
     * @param addMarker needed on rhs where ids can be numeric or alphanumeric
     */
    private static void encodeVersionPartNumeric(String part, BytesRefBuilder result, boolean addMarker) {
        if (addMarker) {
            result.append((byte) 1); // mark as numeric
        }
        result.append((byte) part.length());
        result.append(new BytesRef(part));
        result.append(DOT_SEPARATOR_BYTE);
    }

    private static int decodeVersionPartNumeric(byte[] input, StringBuilder result, int pos) {
        int partLength = input[pos++];
        result.append(new BytesRef(Arrays.copyOfRange(input, pos, pos + partLength)).utf8ToString());
        result.append(DOT_SEPARATOR);
        return pos + partLength + 1;
    }

    public static String decodeVersion(BytesRef version, AlphanumSortMode mode) {
        System.out.println("decoding: " + version);
        int pos = 0;
        byte[] bytes = version.bytes;
        StringBuilder sb = new StringBuilder();
        while (bytes[pos] != LHS_FINISHED_BYTE) {
            pos = decodeVersionPartNumeric(bytes, sb, pos);
        }
        sb.deleteCharAt(sb.length() - 1); // delete last dot
        pos++;
        // decode whether version has pre-release part
        byte preReleaseFlag = bytes[pos++];
        if (preReleaseFlag == PRERELESE_SEPARATOR_BYTE) {
            sb.append(PRERELESE_SEPARATOR);
            while (pos < version.length && bytes[pos] != BUILD_SEPARATOR_BYTE) {
                  byte isNumeric = bytes[pos++];
                  if (isNumeric == 1) {
                      pos = decodeVersionPartNumeric(bytes, sb, pos);
                  } else {
                      pos = mode.decode(bytes, sb, pos);
                  }
            }
            sb.deleteCharAt(sb.length() - 1);
        }
        if (pos < version.length && bytes[pos] == BUILD_SEPARATOR_BYTE) {
            sb.append(new BytesRef(Arrays.copyOfRange(version.bytes, pos, version.length)).utf8ToString());
        }
        System.out.println(sb.toString());
        return sb.toString();
    }

}
