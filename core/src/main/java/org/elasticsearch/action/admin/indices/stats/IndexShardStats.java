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

package org.elasticsearch.action.admin.indices.stats;

import org.elasticsearch.common.io.stream.StreamInput;
import org.elasticsearch.common.io.stream.StreamOutput;
import org.elasticsearch.common.io.stream.Writeable;
import org.elasticsearch.index.shard.ShardId;

import java.io.IOException;
import java.util.Arrays;
import java.util.Iterator;

public class IndexShardStats implements Iterable<ShardStats>, Writeable {

    private ShardId shardId;

    private ShardStats[] shards;

    private final CommonStatsFlags flags;


    public IndexShardStats(ShardId shardId, CommonStatsFlags flags, ShardStats[] shards) {
        this.shardId = shardId;
        this.shards = shards;
        this.flags = flags;
    }

    private IndexShardStats(StreamInput in) throws IOException {
        shardId = ShardId.readShardId(in);
        int shardSize = in.readVInt();
        shards = new ShardStats[shardSize];
        for (int i = 0; i < shardSize; i++) {
            shards[i] = ShardStats.readShardStats(in);
        }
        flags = new CommonStatsFlags(in);
    }

    public ShardId getShardId() {
        return this.shardId;
    }

    public ShardStats[] getShards() {
        return shards;
    }

    public ShardStats getAt(int position) {
        return shards[position];
    }

    @Override
    public Iterator<ShardStats> iterator() {
        return Arrays.stream(shards).iterator();
    }

    private CommonStats total = null;

    public CommonStats getTotal() {
        if (total == null) {
            total = ShardStats.calculateTotalStats(shards, flags);
        }
        return total;
    }

    private CommonStats primary = null;

    public CommonStats getPrimary() {
        if (primary == null) {
            primary = ShardStats.calculatePrimaryStats(shards, flags);
        }
        return primary;
    }

    @Override
    public void writeTo(StreamOutput out) throws IOException {
        shardId.writeTo(out);
        out.writeVInt(shards.length);
        for (ShardStats stats : shards) {
            stats.writeTo(out);
        }
        flags.writeTo(out);
    }

    public static IndexShardStats readIndexShardStats(StreamInput in) throws IOException {
        return new IndexShardStats(in);
    }

}
