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

package org.elasticsearch.action.ingest;

import org.elasticsearch.common.Strings;
import org.elasticsearch.common.io.stream.BytesStreamOutput;
import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.test.AbstractStreamableXContentTestCase;

import java.io.IOException;

import static org.hamcrest.CoreMatchers.equalTo;

public class WritePipelineResponseTests extends AbstractStreamableXContentTestCase<WritePipelineResponse> {

    public void testSerializationWithoutError() throws IOException {
        boolean isAcknowledged = randomBoolean();
        WritePipelineResponse response;
        response = new WritePipelineResponse(isAcknowledged);
        BytesStreamOutput out = new BytesStreamOutput();
        response.writeTo(out);
        StreamInput streamInput = out.bytes().streamInput();
        WritePipelineResponse otherResponse = new WritePipelineResponse(false);
        otherResponse.readFrom(streamInput);

        assertThat(otherResponse.isAcknowledged(), equalTo(response.isAcknowledged()));
    }

    public void testSerializationWithError() throws IOException {
        WritePipelineResponse response = new WritePipelineResponse(false);
        BytesStreamOutput out = new BytesStreamOutput();
        response.writeTo(out);
        StreamInput streamInput = out.bytes().streamInput();
        WritePipelineResponse otherResponse = new WritePipelineResponse(false);
        otherResponse.readFrom(streamInput);

        assertThat(otherResponse.isAcknowledged(), equalTo(response.isAcknowledged()));
    }

    public void testToXContent() {
        WritePipelineResponse response = new WritePipelineResponse(true);
        String output = Strings.toString(response);
        assertEquals("{\"acknowledged\":true}", output);
    }

    @Override
    protected WritePipelineResponse doParseInstance(XContentParser parser) {
        return WritePipelineResponse.fromXContent(parser);
    }

    @Override
    protected WritePipelineResponse createTestInstance() {
        return new WritePipelineResponse(randomBoolean());
    }

    @Override
    protected WritePipelineResponse createBlankInstance() {
        return new WritePipelineResponse(false);
    }

    @Override
    protected WritePipelineResponse mutateInstance(WritePipelineResponse response) {
        return new WritePipelineResponse(response.isAcknowledged() == false);
    }
}
