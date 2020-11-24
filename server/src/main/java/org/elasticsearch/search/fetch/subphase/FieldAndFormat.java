/*
 * Licensed to Elasticsearch under one or more contributor
 * license agreements. See the NOTICE file distributed with
 * this work for additional information regarding copyright
 * ownership. Elasticsearch licenses this file to you under
 * the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

package org.elasticsearch.search.fetch.subphase;

import org.elasticsearch.Version;
import org.elasticsearch.common.Nullable;
import org.elasticsearch.common.ParseField;
import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.io.stream.StreamOutput;
import org.elasticsearch.common.io.stream.Writeable;
import org.elasticsearch.common.xcontent.ConstructingObjectParser;
import org.elasticsearch.common.xcontent.ToXContentObject;
import org.elasticsearch.common.xcontent.XContent;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentParser;

import java.io.IOException;
import java.util.Objects;
import java.util.Optional;

/**
 * Wrapper around a field name and the format that should be used to
 * display values of this field.
 */
public final class FieldAndFormat implements Writeable, ToXContentObject {
    private static final ParseField FIELD_FIELD = new ParseField("field");
    private static final ParseField FORMAT_FIELD = new ParseField("format");
    private static final ParseField INCLUDE_UNMAPPED_FIELD = new ParseField("include_unmapped");

    private static final ConstructingObjectParser<FieldAndFormat, Void> PARSER =
        new ConstructingObjectParser<>("fetch_field_and_format",
        a -> new FieldAndFormat((String) a[0], (String) a[1], Optional.ofNullable((Boolean) a[2])));

    static {
        PARSER.declareString(ConstructingObjectParser.constructorArg(), FIELD_FIELD);
        PARSER.declareStringOrNull(ConstructingObjectParser.optionalConstructorArg(), FORMAT_FIELD);
        PARSER.declareBoolean(ConstructingObjectParser.optionalConstructorArg(), INCLUDE_UNMAPPED_FIELD);
    }

    /**
     * Parse a {@link FieldAndFormat} from some {@link XContent}.
     */
    public static FieldAndFormat fromXContent(XContentParser parser) throws IOException {
        XContentParser.Token token = parser.currentToken();
        if (token.isValue()) {
            return new FieldAndFormat(parser.text(), null);
        } else {
            return PARSER.apply(parser, null);
        }
    }

    @Override
    public XContentBuilder toXContent(XContentBuilder builder, Params params) throws IOException {
        builder.startObject();
        builder.field(FIELD_FIELD.getPreferredName(), field);
        if (format != null) {
            builder.field(FORMAT_FIELD.getPreferredName(), format);
        }
        if (this.includeUnmapped.isPresent()) {
            builder.field(INCLUDE_UNMAPPED_FIELD.getPreferredName(), includeUnmapped.get());
        }
        builder.endObject();
        return builder;
    }

    /** The name of the field. */
    public final String field;

    /** The format of the field, or {@code null} if defaults should be used. */
    public final String format;

    /** Whether to include unmapped fields or not. */
    public final Optional<Boolean> includeUnmapped;

    public FieldAndFormat(String field, @Nullable String format) {
        this(field, format, Optional.empty());
    }

    public FieldAndFormat(String field, @Nullable String format, Optional<Boolean> includeUnmapped) {
        this.field = Objects.requireNonNull(field);
        this.format = format;
        this.includeUnmapped = includeUnmapped;
    }

    /** Serialization constructor. */
    public FieldAndFormat(StreamInput in) throws IOException {
        this.field = in.readString();
        format = in.readOptionalString();
        if (in.getVersion().onOrAfter(Version.CURRENT)) {
            this.includeUnmapped = Optional.ofNullable(in.readOptionalBoolean());
        } else {
            this.includeUnmapped = Optional.empty();
        }
    }

    @Override
    public void writeTo(StreamOutput out) throws IOException {
        out.writeString(field);
        out.writeOptionalString(format);
        if (out.getVersion().onOrAfter(Version.CURRENT)) {
            out.writeOptionalBoolean(this.includeUnmapped.orElse(null));
        }
    }

    @Override
    public int hashCode() {
        int h = field.hashCode();
        h = 31 * h + Objects.hashCode(format);
        h = 31 * h + Boolean.hashCode(this.includeUnmapped.orElse(false));
        return h;
    }

    @Override
    public boolean equals(Object obj) {
        if (obj == null || getClass() != obj.getClass()) {
            return false;
        }
        FieldAndFormat other = (FieldAndFormat) obj;
        return field.equals(other.field) && Objects.equals(format, other.format) && Objects.equals(includeUnmapped, other.includeUnmapped);
    }
}
