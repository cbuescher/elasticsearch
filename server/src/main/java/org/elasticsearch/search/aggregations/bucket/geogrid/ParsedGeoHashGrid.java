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

package org.elasticsearch.search.aggregations.bucket.geogrid;

import org.elasticsearch.common.geo.GeoPoint;
import org.elasticsearch.common.xcontent.ObjectParser;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.search.aggregations.ParsedMultiBucketAggregation;

import java.io.IOException;
import java.util.List;

public class ParsedGeoHashGrid extends ParsedMultiBucketAggregation<ParsedGeoHashGrid.ParsedBucket> implements GeoHashGrid {

    private GeoHashType type = GeoHashType.DEFAULT;

    @Override
    public String getType() {
        return GeoGridAggregationBuilder.NAME;
    }

    @Override
    public List<? extends GeoHashGrid.Bucket> getBuckets() {
        return buckets;
    }

    private void setType(String type) {
        // TODO something less brittle than enum#valueOf() needed I think
        this.type = GeoHashType.forString(type);
    }

    private static ObjectParser<ParsedGeoHashGrid, Void> PARSER =
            new ObjectParser<>(ParsedGeoHashGrid.class.getSimpleName(), true, ParsedGeoHashGrid::new);
    static {
        declareMultiBucketAggregationFields(PARSER, ParsedBucket::fromXContent, ParsedBucket::fromXContent);
        PARSER.declareString(ParsedGeoHashGrid::setType, InternalGeoHashGrid.HASH_TYPE_FIELD);
    }

    public static ParsedGeoHashGrid fromXContent(XContentParser parser, String name) throws IOException {
        ParsedGeoHashGrid aggregation = PARSER.parse(parser, null);
        aggregation.setName(name);
        // transfer hash type info to buckets after parsing, this is horrible IMHO but I couldn't make it work
        // otherwise quickly
        // TODO don't do it like this!
        for (ParsedBucket b : aggregation.buckets) {
            b.hashType = aggregation.type;
        }
        return aggregation;
    }

    public static class ParsedBucket extends ParsedMultiBucketAggregation.ParsedBucket implements GeoHashGrid.Bucket {

        private String geohashAsString;
        private GeoHashType hashType = GeoHashType.DEFAULT;

        @Override
        public GeoPoint getKey() {
            // TODO in order for this to work, the GeoHashTypeProvider needs to convert back from String -> GeoPoint
            // return hashType.getHandler().hashStringAsGeoPoint(geohashAsString);
            return null;
        }

        @Override
        public String getKeyAsString() {
            return geohashAsString;
        }

        @Override
        protected XContentBuilder keyToXContent(XContentBuilder builder) throws IOException {
            return builder.field(CommonFields.KEY.getPreferredName(), geohashAsString);
        }

        static ParsedBucket fromXContent(XContentParser parser) throws IOException {
            return parseXContent(parser, false, ParsedBucket::new, (p, bucket) -> bucket.geohashAsString = p.textOrNull());
        }
    }
}
