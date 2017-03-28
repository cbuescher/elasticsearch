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
package org.elasticsearch.search.aggregations.metrics.avg;

import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.io.stream.StreamOutput;
import org.elasticsearch.common.xcontent.ObjectParser;
import org.elasticsearch.common.xcontent.ObjectParser.ValueType;
import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.search.DocValueFormat;
import org.elasticsearch.search.aggregations.InternalAggregation;
import org.elasticsearch.search.aggregations.metrics.InternalNumericMetricsAggregation;
import org.elasticsearch.search.aggregations.metrics.max.InternalMax;
import org.elasticsearch.search.aggregations.pipeline.PipelineAggregator;

import java.io.IOException;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class InternalAvg extends InternalNumericMetricsAggregation.SingleValue implements Avg {
    private final double sum;
    private final long count;

    public InternalAvg(String name, double sum, long count, DocValueFormat format, List<PipelineAggregator> pipelineAggregators,
            Map<String, Object> metaData) {
        super(name, pipelineAggregators, metaData);
        this.sum = sum;
        this.count = count;
        this.format = format;
    }

    /**
     * Read from a stream.
     */
    public InternalAvg(StreamInput in) throws IOException {
        super(in);
        format = in.readNamedWriteable(DocValueFormat.class);
        sum = in.readDouble();
        count = in.readVLong();
    }

    @Override
    protected void doWriteTo(StreamOutput out) throws IOException {
        out.writeNamedWriteable(format);
        out.writeDouble(sum);
        out.writeVLong(count);
    }

    @Override
    public double value() {
        return getValue();
    }

    @Override
    public double getValue() {
        return sum / count;
    }

    double getSum() {
        return sum;
    }

    long getCount() {
        return count;
    }

    @Override
    public String getWriteableName() {
        return AvgAggregationBuilder.NAME;
    }

    @Override
    public InternalAvg doReduce(List<InternalAggregation> aggregations, ReduceContext reduceContext) {
        long count = 0;
        double sum = 0;
        for (InternalAggregation aggregation : aggregations) {
            count += ((InternalAvg) aggregation).count;
            sum += ((InternalAvg) aggregation).sum;
        }
        return new InternalAvg(getName(), sum, count, format, pipelineAggregators(), getMetaData());
    }

    @Override
    public XContentBuilder doXContentBody(XContentBuilder builder, Params params) throws IOException {
        builder.field(CommonFields.VALUE.getPreferredName(), count != 0 ? getValue() : null);
        if (format != DocValueFormat.RAW) {
            builder.field(CommonFields.VALUE_AS_STRING.getPreferredName(), format.format(getValue()));
        }
        return builder;
    }

    private static final ObjectParser<Map<String, Object>, Void> PARSER = new ObjectParser<>(
            "internal_avg", true, HashMap::new);

    static {
        declareCommonField(PARSER);
        PARSER.declareField((map, value) -> map.put(CommonFields.VALUE.getPreferredName(), value),
                (p,c) -> InternalMax.parseValue(p, Double.POSITIVE_INFINITY), CommonFields.VALUE, ValueType.DOUBLE_OR_NULL);
        PARSER.declareString((map, valueAsString) -> map.put(CommonFields.VALUE_AS_STRING.getPreferredName(), valueAsString),
                CommonFields.VALUE_AS_STRING);
    }

    public static InternalAvg parseXContentBody(String name, XContentParser parser) {
        Map<String, Object> map = PARSER.apply(parser, null);
        double sum = (Double) map.getOrDefault(CommonFields.VALUE.getPreferredName(),
                Double.POSITIVE_INFINITY);
        String valueAsString = (String) map.get(CommonFields.VALUE_AS_STRING.getPreferredName());
        @SuppressWarnings("unchecked")
        Map<String, Object> metaData = (Map<String, Object>) map
                .get(CommonFields.META.getPreferredName());
        DocValueFormat formatter = DocValueFormat.RAW;
        if (valueAsString != null) {
            formatter = InternalNumericMetricsAggregation.wrapValueAsString(Collections.singletonMap(sum, valueAsString));
        }
        // we cannot parse back the count, in order to get the same avg. we use sum and count=1
        long count = Double.isFinite(sum) ? 1L : 0L;
        return new InternalAvg(name, sum, count, formatter, Collections.emptyList(), metaData);
    }

    @Override
    protected int doHashCode() {
        return Objects.hash(sum, count, format.getWriteableName());
    }

    @Override
    protected boolean doEquals(Object obj) {
        InternalAvg other = (InternalAvg) obj;
        return Objects.equals(sum, other.sum) &&
                Objects.equals(count, other.count) &&
                Objects.equals(format.getWriteableName(), other.format.getWriteableName());
    }
}
