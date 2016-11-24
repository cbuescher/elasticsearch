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

package org.elasticsearch.client;

import org.apache.http.util.EntityUtils;
import org.elasticsearch.common.unit.TimeValue;
import org.elasticsearch.common.xcontent.ObjectPath;
import org.elasticsearch.common.xcontent.XContentFactory;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.common.xcontent.XContentType;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;

public class SearchResponse {

    private ObjectPath object;
    private Map<String, Object> map;

    public SearchResponse(Response response) throws IOException {
        String contentType = response.getHeader("Content-Type");
        String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
        XContentType xContentType = XContentType.fromMediaTypeOrFormat(contentType);
        this.object = ObjectPath.createFromXContent(xContentType.xContent(), body);
        XContentParser parser = XContentFactory.xContent(body).createParser(body);
        this.map = parser.mapOrdered();
    }

    public ObjectPath getObjectPath() {
        return this.object;
    }

    public Map<String, Object> getMap() {
        return this.map;
    }

    public Object get(String path) {
        return object.evaluate(path);
    }

    /**
     * Has the search operation timed out.
     */
    public boolean isTimedOut() {
        return (Boolean) get(org.elasticsearch.action.search.SearchResponse.Fields.TIMED_OUT);
    }

    /**
     * How long the search took.
     */
    public TimeValue getTook() {
        return new TimeValue(getTookInMillis());
    }

    /**
     * How long the search took in milliseconds.
     */
    public long getTookInMillis() {
        Object object = get(org.elasticsearch.action.search.SearchResponse.Fields.TOOK);
        if (object instanceof Integer) {
            return ((Integer) object).longValue();
        }
        if (object instanceof Long) {
            return (Long) object;
        }
        throw new IllegalArgumentException("'took' should be integer or long value but was " + object.getClass());
    }

    /**
     * The total number of shards the search was executed on.
     */
    public int getTotalShards() {
        return (Integer) get("_shards.total");
    }

    /**
     * The successful number of shards the search was executed on.
     */
    public int getSuccessfulShards() {
        return (Integer) get("_shards.successful");
    }

    /**
     * The failed number of shards the search was executed on.
     */
    public int getFailedShards() {
        return (Integer) get("_shards.failed");
    }
}
