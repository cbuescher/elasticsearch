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

package org.elasticsearch.client.rollup;

import org.elasticsearch.common.ParseField;
import org.elasticsearch.common.xcontent.ConstructingObjectParser;
import org.elasticsearch.common.xcontent.XContentParser;

import java.io.IOException;

import static org.elasticsearch.common.xcontent.ConstructingObjectParser.constructorArg;

public class DeleteRollupJobResponse extends AcknowledgedResponse {

    private static final String PARSE_FIELD_NAME = "acknowledged";

    public DeleteRollupJobResponse(boolean acknowledged) {
        super(acknowledged, PARSE_FIELD_NAME);
    }

    public static DeleteRollupJobResponse fromXContent(final XContentParser parser) throws IOException {
        return PARSER.parse(parser, null);
    }

    private static final ConstructingObjectParser<DeleteRollupJobResponse, Void> PARSER
        = new ConstructingObjectParser<>("delete_rollup_job_response", true,
        args -> new DeleteRollupJobResponse((boolean) args[0]));
    static {
        PARSER.declareBoolean(constructorArg(), new ParseField(PARSE_FIELD_NAME));
    }
}
