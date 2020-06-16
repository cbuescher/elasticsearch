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
 * In the default mode (@link {@link SortMode#SEMVER}, the version string is encoded such that the ordering works like the following:
 * <ul>
 *  <li> Major, minor, and patch versions are always compared numerically
 *  <li> pre-release version have lower precedence than a normal version. (e.g 1.0.0-alpha < 1.0.0)
 *  <li> the precedence for pre-release versions with same main version is calculated comparing each dot separated identifier from
 *  left to right. Identifiers consisting of only digits are compared numerically and identifiers with letters or hyphens are compared
 *  lexically in ASCII sort order. Numeric identifiers always have lower precedence than non-numeric identifiers.
 * </ul>
 *
 * The sorting for the main version part in {@link SortMode#HONOUR_NUMERALS} is the same except that in the pre-release part,
 * mixed alpha-numerical identifiers are compared grouping all consecutive digits and treating them as a number with numerical ordering.
 * For example, "alpha2" would sort _before" "alpha11" in this mode.
 */
public class VersionEncoder2 {

    private static final byte NUMERIC_MARKER_BYTE = (byte) 0x01;
    private static final char PRERELESE_SEPARATOR = '-';
    private static final byte PRERELESE_SEPARATOR_BYTE = (byte) 0x02;
    private static final byte NO_PRERELESE_SEPARATOR_BYTE = (byte) 0x03;
    private static final String DOT_SEPARATOR_REGEX = "\\.";
    private static final char DOT_SEPARATOR = '.';
    private static final byte DOT_SEPARATOR_BYTE = (byte) 0x04;
    private static final char BUILD_SEPARATOR = '+';
    private static final byte BUILD_SEPARATOR_BYTE = (byte) BUILD_SEPARATOR;

    // Regex to test version validity: \d+(\.\d+)*(-[\-\dA-Za-z]+){0,1}(\.[-\dA-Za-z]+)*(\+[\.\-\dA-Za-z]+)?
    private static Pattern LEGAL_VERSION_PATTERN = Pattern.compile(
        "\\d+(\\.\\d+)*(-[\\-\\dA-Za-z]+){0,1}(\\.[\\-\\dA-Za-z]+)*(\\+[\\.\\-\\dA-Za-z]+)?"
    );

    /**
     * Defines how version parts consisting of both alphabetical and numerical characters are ordered
     */
    public enum SortMode {
        /**
         * strict semver precedence treats everything alphabetically, e.g. "rc11" &lt; "rc2"
         */
        SEMVER
        {
            @Override
            public void encode(String part, BytesRefBuilder result) {
                result.append(new BytesRef(part));
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
                prefixDigitGroupsWithLength(part, result);
            }
        };

        public abstract void encode(String part, BytesRefBuilder result);
    }

    /**
     * Encodes a version string given the given {@link SortMode}.
     * First, the input version string is split into the following parts:
     * <p>
     * mainVersion(-preReleasePart)(+buildId)
     *
     */
    public static BytesRef encodeVersion(String versionString, SortMode mode) {
        System.out.println("encoding: " + versionString);
        if (legalVersionString(versionString) == false) {
            throw new IllegalArgumentException("Illegal version string: " + versionString);
        }
        // extract "build" suffix starting with "+"
        String buildSuffixPart = extractSuffix(versionString, BUILD_SEPARATOR);
        if (buildSuffixPart != null) {
           versionString = versionString.substring(0, versionString.length() - buildSuffixPart.length());
        }

        // extract "pre-release" suffix starting with "-"
        String preReleaseId = extractSuffix(versionString, PRERELESE_SEPARATOR);
        if (preReleaseId != null) {
            versionString = versionString.substring(0, versionString.length() - preReleaseId.length());
        }

        // pad all digit groups in main part with numeric marker and length bytes
        BytesRefBuilder encodedVersion = new BytesRefBuilder();
        prefixDigitGroupsWithLength(versionString, encodedVersion);

        // encode whether version has pre-release parts
        if (preReleaseId != null) {
            encodedVersion.append(PRERELESE_SEPARATOR_BYTE);  // versions with pre-release part sort before ones without
            String[] preReleaseParts = preReleaseId.substring(1).split(DOT_SEPARATOR_REGEX);
            boolean first = true;
            for (String preReleasePart : preReleaseParts) {
                if (first == false) {
                    encodedVersion.append(DOT_SEPARATOR_BYTE);
                }
                boolean isNumeric = preReleasePart.chars().allMatch(x -> Character.isDigit(x));
                if (isNumeric) {
                    prefixDigitGroupsWithLength(preReleasePart, encodedVersion);
                } else {
                    mode.encode(preReleasePart, encodedVersion);
                }
                first = false;
            }
        } else {
            encodedVersion.append(NO_PRERELESE_SEPARATOR_BYTE);
        }

        // append build part at the end
        if (buildSuffixPart != null) {
            encodedVersion.append(new BytesRef(buildSuffixPart));
        }
        System.out.println("encoded: " + encodedVersion.get());
        return encodedVersion.get();
    }

    private static String extractSuffix(String input, char separator) {
        int start = input.indexOf(separator);
        return start > 0 ? input.substring(start) : null;
    }

    private static void prefixDigitGroupsWithLength(String input, BytesRefBuilder result) {
        int pos = 0;
        while (pos < input.length()) {
                if (Character.isDigit(input.charAt(pos))) {
                    // found beginning of number block, so get its length
                    int start = pos;
                    BytesRefBuilder number = new BytesRefBuilder();
                    while (pos < input.length() && Character.isDigit(input.charAt(pos))) {
                        number.append((byte) input.charAt(pos));
                        pos++;
                    }
                    int length = pos - start;
                    result.append(NUMERIC_MARKER_BYTE); // ensure length byte does cause higher sort order comparing to other byte[]
                    result.append((byte) (length | 0x80)); // add upper bit to mark as length
                    result.append(number);
                } else {
                    if (input.charAt(pos) == DOT_SEPARATOR) {
                        result.append(DOT_SEPARATOR_BYTE);
                    } else {
                        result.append((byte) input.charAt(pos));
                    }
                    pos++;
                }
        }
    }

    public static String decodeVersion(BytesRef version, SortMode mode) {
        System.out.println("decoding: " + version);
        int pos = 0;
        StringBuilder sb = new StringBuilder();
        while (pos < version.length && version.bytes[pos] != BUILD_SEPARATOR_BYTE) {
            pos++;
        }
        sb.append(decodeVersionString(version.bytes, 0, pos));

        // add build part if present
        if (pos < version.length && version.bytes[pos] == BUILD_SEPARATOR_BYTE) {
            sb.append(new BytesRef(Arrays.copyOfRange(version.bytes, pos, version.length)).utf8ToString());
        }
        System.out.println(sb.toString());
        return sb.toString();
    }

    private static char[] decodeVersionString(byte[] input, int startPos, int endPos) {
        int inputPos = startPos;
        int resultPos = 0;
        char[] result = new char[input.length];
        while (inputPos < endPos) {
            byte inputByte = input[inputPos];
            if (inputByte >= 0x30 && ((inputByte & 0x80) == 0)) {
                result[resultPos] = (char) inputByte;
                resultPos++;
            } else if (inputByte == DOT_SEPARATOR_BYTE) {
                result[resultPos] = DOT_SEPARATOR;
                resultPos++;
            } else if (inputByte == PRERELESE_SEPARATOR_BYTE) {
                result[resultPos] = PRERELESE_SEPARATOR;
                resultPos++;
            } else if (inputByte == BUILD_SEPARATOR_BYTE) {
                result[resultPos] = BUILD_SEPARATOR;
                resultPos++;
            }
            inputPos++;
        }
        return Arrays.copyOf(result, resultPos);
    }

    static boolean legalVersionString(String versionString) {
        return LEGAL_VERSION_PATTERN.matcher(versionString).matches();
    }
}
