/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the "Elastic License
 * 2.0", the "GNU Affero General Public License v3.0 only", and the "Server Side
 * Public License v 1"; you may not use this file except in compliance with, at
 * your election, the "Elastic License 2.0", the "GNU Affero General Public
 * License v3.0 only", or the "Server Side Public License, v 1".
 */

package org.elasticsearch.action.search;

import org.elasticsearch.TransportVersion;
import org.elasticsearch.action.NoShardAvailableActionException;
import org.elasticsearch.common.bytes.BytesArray;
import org.elasticsearch.common.bytes.BytesReference;
import org.elasticsearch.common.io.stream.NamedWriteableRegistry;
import org.elasticsearch.common.util.concurrent.AtomicArray;
import org.elasticsearch.index.query.IdsQueryBuilder;
import org.elasticsearch.index.query.MatchAllQueryBuilder;
import org.elasticsearch.index.query.QueryBuilder;
import org.elasticsearch.index.query.TermQueryBuilder;
import org.elasticsearch.index.shard.ShardId;
import org.elasticsearch.search.SearchPhaseResult;
import org.elasticsearch.search.SearchShardTarget;
import org.elasticsearch.search.internal.AliasFilter;
import org.elasticsearch.search.internal.ShardSearchContextId;
import org.elasticsearch.test.ESTestCase;
import org.elasticsearch.test.TransportVersionUtils;

import java.util.Base64;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;

public class SearchContextIdTests extends ESTestCase {

    QueryBuilder randomQueryBuilder() {
        if (randomBoolean()) {
            return new TermQueryBuilder(randomAlphaOfLength(10), randomAlphaOfLength(10));
        } else if (randomBoolean()) {
            return new MatchAllQueryBuilder();
        } else {
            return new IdsQueryBuilder().addIds(randomAlphaOfLength(10));
        }
    }

    public void testEncode() {
        final NamedWriteableRegistry namedWriteableRegistry = new NamedWriteableRegistry(
            List.of(
                new NamedWriteableRegistry.Entry(QueryBuilder.class, TermQueryBuilder.NAME, TermQueryBuilder::new),
                new NamedWriteableRegistry.Entry(QueryBuilder.class, MatchAllQueryBuilder.NAME, MatchAllQueryBuilder::new),
                new NamedWriteableRegistry.Entry(QueryBuilder.class, IdsQueryBuilder.NAME, IdsQueryBuilder::new)
            )
        );
        final AtomicArray<SearchPhaseResult> queryResults = TransportSearchHelperTests.generateQueryResults();
        final TransportVersion version = TransportVersion.current();
        final Map<String, AliasFilter> aliasFilters = new HashMap<>();
        Map<SearchShardTarget, ShardSearchFailure> shardSearchFailures = new HashMap<>();
        int idx = 0;
        for (SearchPhaseResult result : queryResults.asList()) {
            if (randomBoolean()) {
                shardSearchFailures.put(
                    result.getSearchShardTarget(),
                    new ShardSearchFailure(
                        new NoShardAvailableActionException(result.getSearchShardTarget().getShardId()),
                        result.getSearchShardTarget()
                    )
                );
                queryResults.set(idx, null);
            } else {
                final AliasFilter aliasFilter;
                if (randomBoolean()) {
                    aliasFilter = AliasFilter.of(randomQueryBuilder());
                } else if (randomBoolean()) {
                    aliasFilter = AliasFilter.of(randomQueryBuilder(), "alias-" + between(1, 10));
                } else {
                    aliasFilter = AliasFilter.EMPTY;
                }
                if (randomBoolean()) {
                    aliasFilters.put(result.getSearchShardTarget().getShardId().getIndex().getUUID(), aliasFilter);
                }
            }
            idx += 1;
        }
        final BytesReference id = SearchContextId.encode(
            queryResults.asList(),
            aliasFilters,
            version,
            shardSearchFailures.values().toArray(ShardSearchFailure[]::new)
        );
        final SearchContextId context = SearchContextId.decode(namedWriteableRegistry, id);
        assertThat(context.shards().keySet(), hasSize(3));
        // TODO assertThat(context.failedShards().keySet(), hasSize(shardsFailed));
        assertThat(context.aliasFilter(), equalTo(aliasFilters));

        ShardId shardIdForNode1 = new ShardId("idx", "uuid1", 2);
        SearchShardTarget shardTargetForNode1 = new SearchShardTarget("node_1", shardIdForNode1, "cluster_x");
        SearchContextIdForNode node1 = context.shards().get(shardIdForNode1);
        assertThat(node1.getClusterAlias(), equalTo("cluster_x"));
        if (shardSearchFailures.containsKey(shardTargetForNode1)) {
            assertNull(node1.getNode());
            assertNull(node1.getSearchContextId());
        } else {
            assertThat(node1.getNode(), equalTo("node_1"));
            assertThat(node1.getSearchContextId().getId(), equalTo(1L));
            assertThat(node1.getSearchContextId().getSessionId(), equalTo("a"));
        }

        ShardId shardIdForNode2 = new ShardId("idy", "uuid2", 42);
        SearchShardTarget shardTargetForNode2 = new SearchShardTarget("node_2", shardIdForNode2, "cluster_y");
        SearchContextIdForNode node2 = context.shards().get(shardIdForNode2);
        assertThat(node2.getClusterAlias(), equalTo("cluster_y"));
        if (shardSearchFailures.containsKey(shardTargetForNode2)) {
            assertNull(node2.getNode());
            assertNull(node2.getSearchContextId());
        } else {
            assertThat(node2.getNode(), equalTo("node_2"));
            assertThat(node2.getSearchContextId().getId(), equalTo(12L));
            assertThat(node2.getSearchContextId().getSessionId(), equalTo("b"));
        }

        ShardId shardIdForNode3 = new ShardId("idy", "uuid2", 43);
        SearchShardTarget shardTargetForNode3 = new SearchShardTarget("node_3", shardIdForNode3, null);
        SearchContextIdForNode node3 = context.shards().get(shardIdForNode3);
        assertThat(node3.getClusterAlias(), nullValue());
        if (shardSearchFailures.containsKey(shardTargetForNode3)) {
            assertNull(node3.getNode());
            assertNull(node3.getSearchContextId());
        } else {
            assertThat(node3.getNode(), equalTo("node_3"));
            assertThat(node3.getSearchContextId().getId(), equalTo(42L));
            assertThat(node3.getSearchContextId().getSessionId(), equalTo("c"));
        }

        final String[] indices = SearchContextId.decodeIndices(id);
        assertThat(indices.length, equalTo(3));
        assertThat(indices[0], equalTo("cluster_x:idx"));
        assertThat(indices[1], equalTo("cluster_y:idy"));
        assertThat(indices[2], equalTo("idy"));
    }

    public void testEndodeDecodeWithNullShardSearchContextId() {
        Map<ShardId, SearchContextIdForNode> shards = new HashMap<>();
        shards.put(
            new ShardId("idx", "uuid1", 0),
            new SearchContextIdForNode("cluster_x", "node_1", new ShardSearchContextId("sessionId", 1, "searcherId"))
        );
        shards.put(new ShardId("idx", "uuid1", 1), new SearchContextIdForNode("cluster_x", "node_1", null));
        SearchContextId original = new SearchContextId(shards, Collections.emptyMap());
        BytesReference pointInTimeId = SearchContextId.encode(
            original.shards(),
            original.aliasFilter(),
            TransportVersion.current(),
            ShardSearchFailure.EMPTY_ARRAY
        );
        String originalBase64Id = Base64.getUrlEncoder().encodeToString(BytesReference.toBytes(pointInTimeId));
        System.out.println("original: " + originalBase64Id);
        BytesReference reDecoded = new BytesArray(Base64.getUrlDecoder().decode(originalBase64Id));
        SearchContextId decoded = SearchContextId.decode(new NamedWriteableRegistry(Collections.emptyList()), reDecoded);
        assertThat(decoded.shards().size(), equalTo(2));
        assertThat(decoded.shards().get(new ShardId("idx", "uuid1", 0)).getSearchContextId().getSearcherId(), equalTo("searcherId"));
        assertThat(decoded.shards().get(new ShardId("idx", "uuid1", 1)).getSearchContextId(), equalTo(null));
        assertEquals(original, decoded);
    }

    public void testDecodingPITS() {
        String original = "oMG8BDEiLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAzLTAwMDA0MBZfVy00Zy1mVVJOMkNrb1NVRG1IWWhBAgEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXgWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYK0tId05jSmlYZEsrY3QzNXpDc2IwQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOS4wNS0wMDAwMzcWZXJNZk45dFlSS1NxNjhKTmRyY1FHZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaNFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGENmY2NBVHRobVlLZk84clhUajlaWXc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDkuMDUtMDAwMDM3FmVyTWZOOXRZUktTcTY4Sk5kcmNRR2cBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNchZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJWW5RPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA5LjA1LTAwMDAzNxZlck1mTjl0WVJLU3E2OEpOZHJjUUdnAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF40Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYRGZuQUgva2YrcTllWXhHVHM5UzZUQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNi4xMi0wMDAwMzMWaUNPRUN1ZnhTOU9qek5PeTM3S3FRdwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaMFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGFVTYW9XNFJmTG9TUmEwNzN4U0lXYlE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTItMDAwMDMzFmlDT0VDdWZ4UzlPanpOT3kzN0txUXcBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNcRZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhDZmNjQVR0aG1ZS2ZPOHJYVGo5WGlnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAzLTAwMDA0MBZfVy00Zy1mVVJOMkNrb1NVRG1IWWhBAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4gWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYZ0UraXlQQ1MxYW9ndkRFL2lGVHFTZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMS4wMy0wMDAwNDAWX1ctNGctZlVSTjJDa29TVURtSFloQQABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaOFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGDBsM0tUaU9WNlFjeWI1NmRBVXdTeHc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDQuMjEtMDAwMDc4Fmw4QmE5VDBEUzd5Wm5VOFpNNUV6T1ECARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGmRZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhyaldyMXFoWUNmTndGY0VWaDJpeENnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjA0LjIxLTAwMDA3OBZsOEJhOVQwRFM3eVpuVThaTTVFek9RAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4oWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYcmpXcjFxaFlDZk53RmNFVmgyaXhEQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNC4yMS0wMDAwNzgWbDhCYTlUMERTN3lablU4Wk01RXpPUQABFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI1uFkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFNmdEpuVC9lMkxLZUtNaFh0dDlPZUE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDUuMTAtMDAwMDMxFkxKRVoyTWFzU01xM0RnUkZfdDNQTWcCARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNdxZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJV2lBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA1LjEwLTAwMDAzMRZMSkVaMk1hc1NNcTNEZ1JGX3QzUE1nAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4YWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlxdz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNS4xMC0wMDAwMzEWTEpFWjJNYXNTTXEzRGdSRl90M1BNZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaLFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0Vnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDcuMTQtMDAwMDM1FmVPQ1piZ25sUTJPcktlX2Z0QUdDLVEBARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXhxZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARhEZm5BSC9rZitxOWVZeEdUczlTNnZ3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA3LjE0LTAwMDAzNRZlT0NaYmdubFEyT3JLZV9mdEFHQy1RAgEWUTZOMTVRMmdSVEt6WW93T0lfZW5EQQABAAAAAAAMxpUWdTJlc1VmemtRTE9jeEU0azF2SzBIdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVhoQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNy4xNC0wMDAwMzUWZU9DWmJnbmxRMk9yS2VfZnRBR0MtUQABFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI1oFkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFVTYW9XNFJmTG9TUmEwNzN4U0lYcnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMTIuMDMtMDAwMDQxFm4wOHZCNlNuU2VDX19QX2FxQTdyZ1EAARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXghZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARgvZE5nQ2haNHJpanBNeDYzc09RT2NnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEyLjAzLTAwMDA0MRZuMDh2QjZTblNlQ19fUF9hcUE3cmdRAQEWUTZOMTVRMmdSVEt6WW93T0lfZW5EQQABAAAAAAAMxpIWdTJlc1VmemtRTE9jeEU0azF2SzBIdwEYWS9vbmNXZmlOWXgwMzF3aWYvanhpZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMi4wMy0wMDAwNDEWbjA4dkI2U25TZUNfX1BfYXFBN3JnUQIBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI15FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFZPMGc3ZlBpK3hEMU1IaDY2SWZud3c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDEuMTktMDAwMDQzFmtKRUg5eUkyU1dpSkNGRWJXbjFWUncBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGlBZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhuTTRpaFc5VU9GY01ISXdJS25rVnF3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAxLjE5LTAwMDA0MxZrSkVIOXlJMlNXaUpDRkViV24xVlJ3AAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4MWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYWFpnUGdiWURwRjNTTndkT2txOHp4dz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMy4xNi0wMDAwNzMWZWg0eTlzTmlUdTZlX2pSUnhvZ0lnQQEBFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeJFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGHR0QzB2TzBzcGpIeDlVSURHUGtROEE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMDktMDAwMDMyFjNSRkxLc0Z6VEplN0dIYmFQaDM0d0EAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNahZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJWG1RPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAxLjAyLTAwMDA0MhZ2Qjk1dzRpU1FjV29UdjZBMWhseVNBAAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjWsWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYRG0yUldBc0R5Wmd0SlJRVnJFRkhydz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMy4xNi0wMDAwNzMWZWg0eTlzTmlUdTZlX2pSUnhvZ0lnQQIBFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaWFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGFdRV3FTR0VTNHU2VE5ZMzB1UXlUTnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDMuMTYtMDAwMDczFmVoNHk5c05pVHU2ZV9qUlJ4b2dJZ0EAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNbBZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhXUVdxU0dFUzR1NlROWTMwdVNTV3p3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEwLjAyLTAwMDAzOBZTNWtIWGNpTFNoZVYtTEVFYVFfVkdBAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF44Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYRGZuQUgva2YrcTllWXhHVHM5UzRUZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNC4wOS0wMDAwNzUWRzVWVU1GVFZUck9kb1NWbjlTcnRJdwABFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeFFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGDNUTFVkckZ0SFgzYnRPRXBHY1I1cGc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMTAuMDItMDAwMDM4FlM1a0hYY2lMU2hlVi1MRUVhUV9WR0EAARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGjxZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhVU2FvVzRSZkxvU1JhMDczeFNJWEtnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEwLjAyLTAwMDAzOBZTNWtIWGNpTFNoZVYtTEVFYVFfVkdBAQEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXMWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlDUT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMi4xNi0wMDAwNDUWTE1aZndGLWdRYUthcGd3VUdvMmZZZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaQFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGG15SHNpcHN6aGpUdXI5NkZZdU9zUWc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDIuMTYtMDAwMDQ1FkxNWmZ3Ri1nUWFLYXBnd1VHbzJmWWcBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNdRZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhteUhzaXBzemhqVHVyOTZGWXVqemFBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAyLjE2LTAwMDA0NRZMTVpmd0YtZ1FhS2FwZ3dVR28yZllnAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF48Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYKzVLRU1wV0Q2NXV3bUJzRGxqMmhBQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMi4xMi0wMDAwNDQWOTJQdkVKUXJSYUtiY1BDRGRZSXFWZwEBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI12FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGDZ4a0ZFbTkyRmlod3hyOUJ1VE9KUkE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDUuMTItMDAwMDgwFmF3NnFvS0NXU18tM3NVU1RsYkhQUmcCARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGmBZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhaTXV3UFBUWVZnYXQzR1l1Ky8vdmN3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAyLjEyLTAwMDA0NBY5MlB2RUpRclJhS2JjUENEZFlJcVZnAAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4QWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYT3oybzc3c0lieTRsMjUyQkRFc2I5UT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNS4xMi0wMDAwODAWYXc2cW9LQ1dTXy0zc1VTVGxiSFBSZwEBFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeLFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGFNCVVc3alVpNlFuVjhPTXRCQUdaN2c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDUuMTItMDAwMDgwFmF3NnFvS0NXU18tM3NVU1RsYkhQUmcAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNbxZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhTQlVXN2pVaTZRblY4T010QkFHWjhRPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAxLTAwMDAzORZUUkphd2FIQlJRZXlfWlRxWUdISFRBAAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4EWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOWFWZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMS4wMS0wMDAwMzkWVFJKYXdhSEJSUWV5X1pUcVlHSEhUQQEBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI10FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0R3c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDQuMTQtMDAwMDc3FkdaMDRfVThBVEtLNnpUT0h6WTdDUncBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGkxZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhDa3Yyb3hqdUhHc3RjUDlrZk9YSEZBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjA0LjE0LTAwMDA3NxZHWjA0X1U4QVRLSzZ6VE9Ielk3Q1J3AAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjW0WQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYUTYzQTlTMkJNY05nQStJUkR2ZTNqdz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOC4xMS0wMDAwMzYWdklwTXVDbVpTRWlJX25ESE0yTU1PZwABFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeAFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGFVTYW9XNFJmTG9TUmEwNzN4U0lXTlE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTYtMDAwMDM0FjB3SmoyYl9KUkFheXZJcmdZSU42MVECARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXjBZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARhDZmNjQVR0aG1ZS2ZPOHJYVGo5YUFnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA2LjE2LTAwMDAzNBYwd0pqMmJfSlJBYXl2SXJnWUlONjFRAAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjWkWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYVVNhb1c0UmZMb1NSYTA3M3hTSVpKUT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOC4xMS0wMDAwMzYWdklwTXVDbVpTRWlJX25ESE0yTU1PZwIBFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaXFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0Qnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTYtMDAwMDM0FjB3SmoyYl9KUkFheXZJcmdZSU42MVEBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGkRZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhEZm5BSC9rZitxOWVZeEdUczlTNm13PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA4LjExLTAwMDAzNhZ2SXBNdUNtWlNFaUlfbkRITTJNTU9nAQEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXAWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlCdz09FBZlaDR5OXNOaVR1NmVfalJSeG9nSWdBAAAWYXc2cW9LQ1dTXy0zc1VTVGxiSFBSZwAAFlM1a0hYY2lMU2hlVi1MRUVhUV9WR0EAABZMSkVaMk1hc1NNcTNEZ1JGX3QzUE1nAAAWRzVWVU1GVFZUck9kb1NWbjlTcnRJdwAAFm4wOHZCNlNuU2VDX19QX2FxQTdyZ1EAABY5MlB2RUpRclJhS2JjUENEZFlJcVZnAAAWX1ctNGctZlVSTjJDa29TVURtSFloQQAAFkxNWmZ3Ri1nUWFLYXBnd1VHbzJmWWcAABZ2SXBNdUNtWlNFaUlfbkRITTJNTU9nAAAWMHdKajJiX0pSQWF5dklyZ1lJTjYxUQAAFmVyTWZOOXRZUktTcTY4Sk5kcmNRR2cAABYzUkZMS3NGelRKZTdHSGJhUGgzNHdBAAAWa0pFSDl5STJTV2lKQ0ZFYlduMVZSdwAAFnZCOTV3NGlTUWNXb1R2NkExaGx5U0EAABZHWjA0X1U4QVRLSzZ6VE9Ielk3Q1J3AAAWaUNPRUN1ZnhTOU9qek5PeTM3S3FRdwAAFlRSSmF3YUhCUlFleV9aVHFZR0hIVEEAABZlT0NaYmdubFEyT3JLZV9mdEFHQy1RAAAWbDhCYTlUMERTN3lablU4Wk01RXpPUQAA";
        String updated = "oMG8BDEiLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAzLTAwMDA0MBZfVy00Zy1mVVJOMkNrb1NVRG1IWWhBAgEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXgWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYK0tId05jSmlYZEsrY3QzNXpDc2IwQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOS4wNS0wMDAwMzcWZXJNZk45dFlSS1NxNjhKTmRyY1FHZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaNFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGENmY2NBVHRobVlLZk84clhUajlaWXc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDkuMDUtMDAwMDM3FmVyTWZOOXRZUktTcTY4Sk5kcmNRR2cBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNchZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJWW5RPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA5LjA1LTAwMDAzNxZlck1mTjl0WVJLU3E2OEpOZHJjUUdnAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF40Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYRGZuQUgva2YrcTllWXhHVHM5UzZUQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNi4xMi0wMDAwMzMWaUNPRUN1ZnhTOU9qek5PeTM3S3FRdwABFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAACIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTItMDAwMDMzFmlDT0VDdWZ4UzlPanpOT3kzN0txUXcBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNcRZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhDZmNjQVR0aG1ZS2ZPOHJYVGo5WGlnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAzLTAwMDA0MBZfVy00Zy1mVVJOMkNrb1NVRG1IWWhBAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4gWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYZ0UraXlQQ1MxYW9ndkRFL2lGVHFTZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMS4wMy0wMDAwNDAWX1ctNGctZlVSTjJDa29TVURtSFloQQABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaOFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGDBsM0tUaU9WNlFjeWI1NmRBVXdTeHc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDQuMjEtMDAwMDc4Fmw4QmE5VDBEUzd5Wm5VOFpNNUV6T1ECARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGmRZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhyaldyMXFoWUNmTndGY0VWaDJpeENnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjA0LjIxLTAwMDA3OBZsOEJhOVQwRFM3eVpuVThaTTVFek9RAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4oWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYcmpXcjFxaFlDZk53RmNFVmgyaXhEQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNC4yMS0wMDAwNzgWbDhCYTlUMERTN3lablU4Wk01RXpPUQABFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI1uFkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFNmdEpuVC9lMkxLZUtNaFh0dDlPZUE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDUuMTAtMDAwMDMxFkxKRVoyTWFzU01xM0RnUkZfdDNQTWcCARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNdxZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJV2lBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA1LjEwLTAwMDAzMRZMSkVaMk1hc1NNcTNEZ1JGX3QzUE1nAQEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4YWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlxdz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNS4xMC0wMDAwMzEWTEpFWjJNYXNTTXEzRGdSRl90M1BNZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaLFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0Vnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDcuMTQtMDAwMDM1FmVPQ1piZ25sUTJPcktlX2Z0QUdDLVEBARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXhxZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARhEZm5BSC9rZitxOWVZeEdUczlTNnZ3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA3LjE0LTAwMDAzNRZlT0NaYmdubFEyT3JLZV9mdEFHQy1RAgEWUTZOMTVRMmdSVEt6WW93T0lfZW5EQQABAAAAAAAMxpUWdTJlc1VmemtRTE9jeEU0azF2SzBIdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVhoQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wNy4xNC0wMDAwMzUWZU9DWmJnbmxRMk9yS2VfZnRBR0MtUQABFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI1oFkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFVTYW9XNFJmTG9TUmEwNzN4U0lYcnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMTIuMDMtMDAwMDQxFm4wOHZCNlNuU2VDX19QX2FxQTdyZ1EAARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXghZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARgvZE5nQ2haNHJpanBNeDYzc09RT2NnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEyLjAzLTAwMDA0MRZuMDh2QjZTblNlQ19fUF9hcUE3cmdRAQEWUTZOMTVRMmdSVEt6WW93T0lfZW5EQQABAAAAAAAMxpIWdTJlc1VmemtRTE9jeEU0azF2SzBIdwEYWS9vbmNXZmlOWXgwMzF3aWYvanhpZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMi4wMy0wMDAwNDEWbjA4dkI2U25TZUNfX1BfYXFBN3JnUQIBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI15FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGFZPMGc3ZlBpK3hEMU1IaDY2SWZud3c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDEuMTktMDAwMDQzFmtKRUg5eUkyU1dpSkNGRWJXbjFWUncBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGlBZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhuTTRpaFc5VU9GY01ISXdJS25rVnF3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAxLjE5LTAwMDA0MxZrSkVIOXlJMlNXaUpDRkViV24xVlJ3AAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4MWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYWFpnUGdiWURwRjNTTndkT2txOHp4dz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMy4xNi0wMDAwNzMWZWg0eTlzTmlUdTZlX2pSUnhvZ0lnQQEBFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeJFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGHR0QzB2TzBzcGpIeDlVSURHUGtROEE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMDktMDAwMDMyFjNSRkxLc0Z6VEplN0dIYmFQaDM0d0EAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNahZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhVU2FvVzRSZkxvU1JhMDczeFNJWG1RPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAxLjAyLTAwMDA0MhZ2Qjk1dzRpU1FjV29UdjZBMWhseVNBAAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjWsWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYRG0yUldBc0R5Wmd0SlJRVnJFRkhydz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMy4xNi0wMDAwNzMWZWg0eTlzTmlUdTZlX2pSUnhvZ0lnQQIBFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaWFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGFdRV3FTR0VTNHU2VE5ZMzB1UXlUTnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDMuMTYtMDAwMDczFmVoNHk5c05pVHU2ZV9qUlJ4b2dJZ0EAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNbBZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhXUVdxU0dFUzR1NlROWTMwdVNTV3p3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEwLjAyLTAwMDAzOBZTNWtIWGNpTFNoZVYtTEVFYVFfVkdBAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF44Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYRGZuQUgva2YrcTllWXhHVHM5UzRUZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNC4wOS0wMDAwNzUWRzVWVU1GVFZUck9kb1NWbjlTcnRJdwABFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeFFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGDNUTFVkckZ0SFgzYnRPRXBHY1I1cGc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMTAuMDItMDAwMDM4FlM1a0hYY2lMU2hlVi1MRUVhUV9WR0EAARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGjxZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhVU2FvVzRSZkxvU1JhMDczeFNJWEtnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjEwLjAyLTAwMDAzOBZTNWtIWGNpTFNoZVYtTEVFYVFfVkdBAQEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXMWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlDUT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMi4xNi0wMDAwNDUWTE1aZndGLWdRYUthcGd3VUdvMmZZZwABFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaQFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGG15SHNpcHN6aGpUdXI5NkZZdU9zUWc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDIuMTYtMDAwMDQ1FkxNWmZ3Ri1nUWFLYXBnd1VHbzJmWWcBARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNdRZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhteUhzaXBzemhqVHVyOTZGWXVqemFBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAyLjE2LTAwMDA0NRZMTVpmd0YtZ1FhS2FwZ3dVR28yZllnAgEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF48Wd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYKzVLRU1wV0Q2NXV3bUJzRGxqMmhBQT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wMi4xMi0wMDAwNDQWOTJQdkVKUXJSYUtiY1BDRGRZSXFWZwEBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI12FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGDZ4a0ZFbTkyRmlod3hyOUJ1VE9KUkE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDUuMTItMDAwMDgwFmF3NnFvS0NXU18tM3NVU1RsYkhQUmcCARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGmBZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhaTXV3UFBUWVZnYXQzR1l1Ky8vdmN3PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjAyLjEyLTAwMDA0NBY5MlB2RUpRclJhS2JjUENEZFlJcVZnAAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4QWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYT3oybzc3c0lieTRsMjUyQkRFc2I5UT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNi4wNS4xMi0wMDAwODAWYXc2cW9LQ1dTXy0zc1VTVGxiSFBSZwEBFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeLFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGFNCVVc3alVpNlFuVjhPTXRCQUdaN2c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDUuMTItMDAwMDgwFmF3NnFvS0NXU18tM3NVU1RsYkhQUmcAARZkWkFWdzM2QlRmdWJSclc1Mm0wWjRnAAEAAAAAAAiNbxZBSDVnSGZ5Z1RhdWk5YVF0VmcyV2RnARhTQlVXN2pVaTZRblY4T010QkFHWjhRPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjExLjAxLTAwMDAzORZUUkphd2FIQlJRZXlfWlRxWUdISFRBAAEWRkI0ZEJqbU5SMUc4NmQtSW9Dc1cxdwABAAAAAAAHF4EWd2gzMTRXUV9RdnVSZ0tXUlpYcmRpdwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOWFWZz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4xMS4wMS0wMDAwMzkWVFJKYXdhSEJSUWV5X1pUcVlHSEhUQQEBFmRaQVZ3MzZCVGZ1YlJyVzUybTBaNGcAAQAAAAAACI10FkFINWdIZnlnVGF1aTlhUXRWZzJXZGcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0R3c9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjYuMDQuMTQtMDAwMDc3FkdaMDRfVThBVEtLNnpUT0h6WTdDUncBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGkxZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhDa3Yyb3hqdUhHc3RjUDlrZk9YSEZBPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI2LjA0LjE0LTAwMDA3NxZHWjA0X1U4QVRLSzZ6VE9Ielk3Q1J3AAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjW0WQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYUTYzQTlTMkJNY05nQStJUkR2ZTNqdz09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOC4xMS0wMDAwMzYWdklwTXVDbVpTRWlJX25ESE0yTU1PZwABFkZCNGRCam1OUjFHODZkLUlvQ3NXMXcAAQAAAAAABxeAFndoMzE0V1FfUXZ1UmdLV1JaWHJkaXcBGFVTYW9XNFJmTG9TUmEwNzN4U0lXTlE9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTYtMDAwMDM0FjB3SmoyYl9KUkFheXZJcmdZSU42MVECARZGQjRkQmptTlIxRzg2ZC1Jb0NzVzF3AAEAAAAAAAcXjBZ3aDMxNFdRX1F2dVJnS1dSWlhyZGl3ARhDZmNjQVR0aG1ZS2ZPOHJYVGo5YUFnPT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA2LjE2LTAwMDAzNBYwd0pqMmJfSlJBYXl2SXJnWUlONjFRAAEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjWkWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYVVNhb1c0UmZMb1NSYTA3M3hTSVpKUT09Ii5kcy1ncmFkbGUtdGFza3MtMjAyNS4wOC4xMS0wMDAwMzYWdklwTXVDbVpTRWlJX25ESE0yTU1PZwIBFlE2TjE1UTJnUlRLellvd09JX2VuREEAAQAAAAAADMaXFnUyZXNVZnprUUxPY3hFNGsxdkswSHcBGERmbkFIL2tmK3E5ZVl4R1RzOVM0Qnc9PSIuZHMtZ3JhZGxlLXRhc2tzLTIwMjUuMDYuMTYtMDAwMDM0FjB3SmoyYl9KUkFheXZJcmdZSU42MVEBARZRNk4xNVEyZ1JUS3pZb3dPSV9lbkRBAAEAAAAAAAzGkRZ1MmVzVWZ6a1FMT2N4RTRrMXZLMEh3ARhEZm5BSC9rZitxOWVZeEdUczlTNm13PT0iLmRzLWdyYWRsZS10YXNrcy0yMDI1LjA4LjExLTAwMDAzNhZ2SXBNdUNtWlNFaUlfbkRITTJNTU9nAQEWZFpBVnczNkJUZnViUnJXNTJtMFo0ZwABAAAAAAAIjXAWQUg1Z0hmeWdUYXVpOWFRdFZnMldkZwEYQ2ZjY0FUdGhtWUtmTzhyWFRqOVlCdz09FBZTNWtIWGNpTFNoZVYtTEVFYVFfVkdBAAAWM1JGTEtzRnpUSmU3R0hiYVBoMzR3QQAAFm4wOHZCNlNuU2VDX19QX2FxQTdyZ1EAABZ2SXBNdUNtWlNFaUlfbkRITTJNTU9nAAAWaUNPRUN1ZnhTOU9qek5PeTM3S3FRdwAAFjB3SmoyYl9KUkFheXZJcmdZSU42MVEAABZfVy00Zy1mVVJOMkNrb1NVRG1IWWhBAAAWa0pFSDl5STJTV2lKQ0ZFYlduMVZSdwAAFlRSSmF3YUhCUlFleV9aVHFZR0hIVEEAABZHNVZVTUZUVlRyT2RvU1ZuOVNydEl3AAAWZWg0eTlzTmlUdTZlX2pSUnhvZ0lnQQAAFkxNWmZ3Ri1nUWFLYXBnd1VHbzJmWWcAABZHWjA0X1U4QVRLSzZ6VE9Ielk3Q1J3AAAWTEpFWjJNYXNTTXEzRGdSRl90M1BNZwAAFmw4QmE5VDBEUzd5Wm5VOFpNNUV6T1EAABZhdzZxb0tDV1NfLTNzVVNUbGJIUFJnAAAWZU9DWmJnbmxRMk9yS2VfZnRBR0MtUQAAFjkyUHZFSlFyUmFLYmNQQ0RkWUlxVmcAABZlck1mTjl0WVJLU3E2OEpOZHJjUUdnAAAWdkI5NXc0aVNRY1dvVHY2QTFobHlTQQAA";
        assertFalse(original.equals(updated));

        SearchContextId originalId = SearchContextId.decode(new NamedWriteableRegistry(Collections.emptyList()), new BytesArray(Base64.getUrlDecoder().decode(original)));
        SearchContextId updatedId = SearchContextId.decode(new NamedWriteableRegistry(Collections.emptyList()), new BytesArray(Base64.getUrlDecoder().decode(updated)));

        Set<Map.Entry<ShardId, SearchContextIdForNode>> entries = updatedId.shards().entrySet();
        for (Map.Entry<ShardId, SearchContextIdForNode> entry : entries) {
            if (entry.getValue().getSearchContextId() == null) {
                System.out.println("ShardId: " + entry.getKey() + ", " + entry.getValue());
                System.out.println("Original: " + originalId.shards().get(entry.getKey()));
            }
        }
    }

    public void testDecodingWithUnknownTransportIdThrows() {
        TransportVersion unknownTransportVersion = TransportVersionUtils.getNextVersion(TransportVersion.current(), true);
        BytesReference id = SearchContextId.encode(
            Collections.emptyMap(),
            Collections.emptyMap(),
            unknownTransportVersion,
            ShardSearchFailure.EMPTY_ARRAY
        );

        NamedWriteableRegistry registry = new NamedWriteableRegistry(Collections.emptyList());

        IllegalArgumentException e = expectThrows(IllegalArgumentException.class, () -> SearchContextId.decode(registry, id));
        assertThat(e.getMessage(), equalTo("unknown transport version [" + unknownTransportVersion.id() + "] reading search context id"));
    }
}
