/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License
 * 2.0; you may not use this file except in compliance with the Elastic License
 * 2.0.
 */

package org.elasticsearch.xpack.stateless.recovery;

import org.apache.http.HttpHost;
import org.apache.http.message.BasicHeader;
import org.apache.http.util.EntityUtils;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.common.Strings;
import org.elasticsearch.core.SuppressForbidden;
import org.elasticsearch.test.ESTestCase;
import org.elasticsearch.test.rest.ObjectPath;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.elasticsearch.test.rest.ESRestTestCase.entityAsMap;
import static org.hamcrest.Matchers.equalTo;

@SuppressForbidden(reason = "test is a utility that prints to stdout")
public class PITRelocationQATests extends ESTestCase {

    /**
     * Manual test that checks that PITs survive a rolling restart.
     *
     * The test first verifies that the cluster is reachable and that the index exists.
     * It turns on the "search.pit_relocation_enabled" feature flag and increases several loggers to DEBUG level in order
     * to facilitate debugging. Note that Debug logging is turned back to the default INFO level after the test,
     * but "TransportStatelessUnpromotableRelocationAction" is kept at DEBUG since it is one of the central PIT relocation loggers.
     *
     * It then starts indexing documents using the Bulk API. After indexing at least 1000 documents, it opens 10 PITs and
     * starts searching on them in parallel threads.
     *
     * This is when the user gets asked to perform a rolling restart of the project.
     * (see https://github.com/elastic/elasticsearch-serverless-support#rolling-restart for details)
     *
     * The test then waits for 4 minutes and then performs a rolling restart. During this time, the test verifies that the PIT searches
     * keep working and that the number of documents found in each PIT remains constant.
     *
     */
    public void testPITDuringRollingRestart() throws IOException, InterruptedException {
        try (RestClient client = buildRestClient()) {
            List<PitWithExpectedDocs> pitsWithExpectedDocs = new ArrayList<>();
            try {
                Response response = client.performRequest(new Request("GET", "/"));
                String responseBody = EntityUtils.toString(response.getEntity());
                System.out.println("---> initial GET /\n" + responseBody);
                String indexName = "test-pit-relocation";

                try {
                    response = client.performRequest(new Request("DELETE", "/" + indexName));
                    System.out.println("---> DELETE /" + indexName + " response code: " + response.getStatusLine().getStatusCode());
                } catch (Exception e) {}

                Request createIndexRequest = new Request("PUT", "/" + indexName);
                response = client.performRequest(createIndexRequest);
                System.out.println("---> PUT /tests-pit-relocation response code: " + response.getStatusLine().getStatusCode());

                boolean enablePITRelocation = true;
                // configureDebugSettings(client, enablePITRelocation);

                Thread mainThread = Thread.currentThread();
                AtomicReference<Boolean> pitSearchRunning = new AtomicReference<>(true);
                AtomicInteger bulkIndexRounds = new AtomicInteger(0);
                Thread bulkIndexThread = new Thread(() -> {
                    while (pitSearchRunning.get()) {
                        List<String> docIds;
                        try {
                            int numDocs = randomIntBetween(100, 500);
                            docIds = bulkIndexDocs(indexName, numDocs, client);
                            bulkIndexRounds.incrementAndGet();
                            if (bulkIndexRounds.get() % 50 == 0) {
                                System.out.println("---> Bulk indexing rounds: " + bulkIndexRounds);
                            }
                        } catch (Exception e) {
                            pitSearchRunning.set(false);
                            mainThread.interrupt();
                            throw new RuntimeException(e);
                        }
                        safeSleep(randomTimeValue(500, 1000, TimeUnit.MILLISECONDS));
                        if (randomBoolean()) {
                            // occasionally also delete a couple of documents so we test generational files as well
                            if (randomBoolean()) {
                                List<String> idsToDelete = randomSubsetOf(randomIntBetween(1, docIds.size() / 2), docIds);
                                try {
                                    bulkDeleteDocs(indexName, idsToDelete, client);
                                } catch (IOException e) {
                                    pitSearchRunning.set(false);
                                    mainThread.interrupt();
                                    throw new RuntimeException(e);
                                }
                            } else {
                                try {
                                    List<String> idsToUpdate = randomSubsetOf(randomIntBetween(1, docIds.size() / 2), docIds);
                                    bulkUpdateDocs(indexName, idsToUpdate, client);
                                } catch (IOException e) {
                                    pitSearchRunning.set(false);
                                    mainThread.interrupt();
                                    throw new RuntimeException(e);
                                }
                            }

                        }
                        safeSleep(randomTimeValue(50, 100, TimeUnit.MILLISECONDS));
                    }
                });
                bulkIndexThread.start();

                waitForDocCount(client, indexName, 1000);

                List<String> pitIds = new ArrayList<>();
                for (int i = 0; i < 10; i++) {
                    pitIds.add(openPITAndReturnId(client, indexName));
                    if (i < 9) {
                        Thread.sleep(2000);
                    }
                }

                for (String pitId : pitIds) {
                    int expectedDocs = getDocCount(client, indexName, pitId);
                    pitsWithExpectedDocs.add(new PitWithExpectedDocs(new AtomicReference<>(pitId), expectedDocs));
                    logger.info("---> PIT {} has {} docs", pitId, expectedDocs);
                }

                AtomicInteger searches = new AtomicInteger(0);
                List<Thread> pitSearchThreads = new ArrayList<>(pitIds.size());
                AtomicBoolean pitIdUpdated = new AtomicBoolean(false);

                for (PitWithExpectedDocs pit : pitsWithExpectedDocs) {
                    Thread pitSearchThread = createPITSearchThread(
                        client,
                        pit.pitId(),
                        pit.expectedDocs(),
                        mainThread,
                        pitSearchRunning,
                        searches,
                        pitIdUpdated
                    );
                    pitSearchThreads.add(pitSearchThread);
                    pitSearchThread.start();
                }

                System.out.println("-----------> Please manually trigger a rolling restart <----------->");
                try {
                    Thread.sleep(TimeUnit.MINUTES.toMillis(4));
                } catch (InterruptedException e) {
                    System.out.println("---> Main thread interrupted by worker thread exception");
                }

                System.out.println("---> Done");
                pitSearchRunning.set(false);
                try {
                    for (Thread pitSearchThread : pitSearchThreads) {
                        pitSearchThread.join();
                    }
                    bulkIndexThread.join();
                } catch (InterruptedException e) {
                    System.out.println("---> Main thread interrupted while joining worker threads (likely a worker threw)");
                    Thread.currentThread().interrupt();
                }
                System.out.println("---> Bulk indexing rounds during relocation: " + bulkIndexRounds.get());
                System.out.println("---> PIT searches during relocation: " + searches.get());
                if (enablePITRelocation) {
                    assertThat(
                        "PIT id wasn't updated. This indicates no PIT relocation took place. Please check you started a rolling-restart "
                            + "and did the original search node terminate before the test ended?",
                        pitIdUpdated.get(),
                        equalTo(true)
                    );
                }

            } finally {
                tryClosePITs(client, pitsWithExpectedDocs);
                // resetDebugSettings(client);
            }
        }
    }

    /**
     * Manual test that checks that PITs work correctly under concurrent search load without any indexing or document mutations.
     *
     * This test assumes that the target index already exists and contains data. It opens 10 PITs and searches on them
     * concurrently in parallel threads. The user is asked to perform a rolling restart during the test. The test verifies
     * that PIT searches keep working and that the document count remains stable across all PITs.
     *
     * Unlike {@link #testPITDuringRollingRestart()}, this test does not perform any indexing, deleting, or updating of documents.
     */
    public void testPITConcurrently() throws IOException, InterruptedException {
        try (RestClient client = buildRestClient()) {
            List<PitWithExpectedDocs> pitsWithExpectedDocs = new ArrayList<>();
            try {
                Response response = client.performRequest(new Request("GET", "/"));
                String responseBody = EntityUtils.toString(response.getEntity());
                System.out.println("---> initial GET /\n" + responseBody);
                // use existing index, e.g. one filled with data from rally
                String indexName = "gradle-tasks";

                boolean enablePITRelocation = true;
                // configureDebugSettings(client, enablePITRelocation);

                Thread mainThread = Thread.currentThread();
                AtomicReference<Boolean> pitSearchRunning = new AtomicReference<>(true);

                List<String> pitIds = new ArrayList<>();
                for (int i = 0; i < 10; i++) {
                    pitIds.add(openPITAndReturnId(client, indexName));
                    if (i < 9) {
                        Thread.sleep(5000);
                    }
                }

                for (String pitId : pitIds) {
                    int expectedDocs = getDocCount(client, indexName, pitId);
                    pitsWithExpectedDocs.add(new PitWithExpectedDocs(new AtomicReference<>(pitId), expectedDocs));
                    logger.info("---> PIT {} has {} docs", pitId, expectedDocs);
                }

                AtomicInteger searches = new AtomicInteger(0);
                List<Thread> pitSearchThreads = new ArrayList<>(pitIds.size());
                AtomicBoolean pitIdUpdated = new AtomicBoolean(false);

                for (PitWithExpectedDocs pit : pitsWithExpectedDocs) {
                    Thread pitSearchThread = createPITSearchThread(
                        client,
                        pit.pitId(),
                        pit.expectedDocs(),
                        mainThread,
                        pitSearchRunning,
                        searches,
                        pitIdUpdated
                    );
                    pitSearchThreads.add(pitSearchThread);
                    pitSearchThread.start();
                }

                System.out.println("-----------> Please manually trigger a rolling restart <----------->");
                try {
                    Thread.sleep(TimeUnit.MINUTES.toMillis(18));
                } catch (InterruptedException e) {
                    System.out.println("---> Main thread interrupted by worker thread exception");
                }

                System.out.println("---> Done");
                pitSearchRunning.set(false);
                try {
                    for (Thread pitSearchThread : pitSearchThreads) {
                        pitSearchThread.join();
                    }
                } catch (InterruptedException e) {
                    System.out.println("---> Main thread interrupted while joining worker threads (likely a worker threw)");
                    Thread.currentThread().interrupt();
                }
                if (enablePITRelocation) {
                    assertThat(
                        "PIT id wasn't updated. This indicates no PIT relocation took place. Please check you started a rolling-restart "
                            + "and did the original search node terminate before the test ended?",
                        pitIdUpdated.get(),
                        equalTo(true)
                    );
                }

            } finally {
                tryClosePITs(client, pitsWithExpectedDocs);
                // resetDebugSettings(client);
            }
        }
    }

    public void testPITNoNPE() throws IOException, InterruptedException {
        try (RestClient client = buildRestClient()) {
            AtomicReference<String> pitIdRef = null;
            try {
                Response response = client.performRequest(new Request("GET", "/"));
                String responseBody = EntityUtils.toString(response.getEntity());
                System.out.println("---> initial GET /\n" + responseBody);

                String[] indexNames = { "index1", "index2", "index3", "index4", "index5" };
                try {
                    response = client.performRequest(new Request("DELETE", "/" + String.join(",", indexNames) ));
                    System.out.println("---> DELETE /" + String.join(",", indexNames) + " response code: " + response.getStatusLine().getStatusCode());
                } catch (Exception e) {}

                dateIndexSetup(client, indexNames);
                indexTestDataDatefield(client, indexNames);

                boolean enablePITRelocation = true;
                configureDebugSettings(client, enablePITRelocation);

                Thread mainThread = Thread.currentThread();
                AtomicReference<Boolean> pitSearchRunning = new AtomicReference<>(true);

                String pitId = openPITAndReturnId(client, String.join(",",indexNames));
                pitIdRef = new AtomicReference<>(pitId);



                int expectedDocs = getDocCount(client, String.join(",",indexNames), pitId);
                logger.info("---> PIT {} has {} docs", pitId, expectedDocs);

                // index more docs
                indexTestDataDatefield(client, indexNames);

                AtomicInteger searches = new AtomicInteger(0);
                AtomicBoolean pitIdUpdated = new AtomicBoolean(false);


                Thread pitSearchThread = createPITSearchThread(
                    client,
                    pitIdRef,
                    expectedDocs,
                    mainThread,
                    pitSearchRunning,
                    searches,
                    pitIdUpdated
                );
                pitSearchThread.start();

                System.out.println("-----------> Please manually trigger a rolling restart <----------->");
                try {
                    Thread.sleep(TimeUnit.MINUTES.toMillis(4));
                } catch (InterruptedException e) {
                    System.out.println("---> Main thread interrupted by worker thread exception");
                }

                System.out.println("---> Done");
                pitSearchRunning.set(false);
                pitSearchThread.join();
                if (enablePITRelocation) {
                    assertThat(
                        "PIT id wasn't updated. This indicates no PIT relocation took place. Please check you started a rolling-restart "
                            + "and did the original search node terminate before the test ended?",
                        pitIdUpdated.get(),
                        equalTo(true)
                    );
                }

            } catch (Exception e) {
                logger.error("Exception while running test", e);
                throw e;
            } finally {
                tryClosePITs(client, List.of(new PitWithExpectedDocs(pitIdRef, 0)));
                resetDebugSettings(client);
            }
        }
    }

    private void indexTestDataDatefield(RestClient client, String[] indexNames) throws IOException {

        for (int i = 0; i < 5; i++) {
            final int month = i + 1;
            StringBuilder bulkBody = new StringBuilder();
            for (int j = 0; j < 500; j++) {
                String date = String.format(
                    Locale.ROOT,
                    "2025-%02d-%02dT%02d:%02d:%02d.000Z",
                    month,
                    // use 28 as maximum days in month since thats also true for February dates
                    randomIntBetween(1, 28),
                    randomIntBetween(0, 23),
                    randomIntBetween(0, 59),
                    randomIntBetween(0, 59)
                );
                bulkBody.append("{\"index\":{\"_index\":\"").append(indexNames[i]).append("\"}}\n");
                bulkBody.append("{\"finished\":\"").append(date).append("\"}\n");
            }
            Request bulkRequest = new Request("POST", "/_bulk");
            bulkRequest.setJsonEntity(bulkBody.toString());
            Response response = client.performRequest(bulkRequest);
            assertEquals(200, response.getStatusLine().getStatusCode());

            Map<String, Object> responseMap = entityAsMap(response.getEntity());
            Boolean errors = (Boolean) responseMap.get("errors");
            if (errors != null && errors) {
                throw new AssertionError("Bulk request had failures");
            }
        }

        // Flush and refresh all indices
        for (String indexName : indexNames) {
            Request refreshRequest = new Request("POST", "/" + indexName + "/_refresh");
            client.performRequest(refreshRequest);
        }
    }

    private void dateIndexSetup(RestClient client, String[] indexNames) throws IOException, InterruptedException {
        for (int i = 0; i < 5; i++) {
            Request createIndexRequest = new Request("PUT", "/" + indexNames[i]);
            createIndexRequest.setJsonEntity("""
                {
                    "settings": {
                        "index": {
                            "number_of_shards": 6,
                            "number_of_replicas": 1
                        }
                    },
                    "mappings": {
                        "properties": {
                            "finished": {
                                "type": "date"
                            }
                        }
                    }
                }
                """);
            Response response = client.performRequest(createIndexRequest);
            System.out.println("---> PUT /" + indexNames[i] + " response code: " + response.getStatusLine().getStatusCode());
            assertEquals(200, response.getStatusLine().getStatusCode());
        }

        // Wait for green status on all indices
        for (String indexName : indexNames) {
            waitForGreenStatus(client, indexName);
        }
    }

    private void waitForGreenStatus(RestClient client, String indexName) throws IOException {
        Request healthRequest = new Request("GET", "/_cluster/health/" + indexName);
        healthRequest.addParameter("wait_for_status", "green");
        healthRequest.addParameter("timeout", "30s");
        Response response = client.performRequest(healthRequest);
        System.out.println("---> Cluster health for " + indexName + ": " + response.getStatusLine().getStatusCode());
    }

    private void tryClosePITs(RestClient client, List<PitWithExpectedDocs> pitsWithExpectedDocs) {
        for (PitWithExpectedDocs pitWithExpectedDocs : pitsWithExpectedDocs) {
            String pitId = pitWithExpectedDocs.pitId().get();
            if (pitId != null) {
                try {
                    Request closeRequest = new Request("DELETE", "/_pit");
                    closeRequest.setJsonEntity("""
                        {
                            "id": "%s"
                        }
                        """.formatted(pitId));
                    Response response = client.performRequest(closeRequest);
                    System.out.println("---> Closed PIT " + pitId + " with response code: " + response.getStatusLine().getStatusCode());
                } catch (Exception e) {
                    System.out.println("---> Failed to close PIT " + pitId + ": " + e.getMessage());
                }
            }
        }
    }

    /**
     * Builds a RestClient from environment variables.
     * Configuration:
     * - ES_HOSTNAME: hostname of the cluster to test against
     * - ES_USER: username to use for authentication
     * - ES_PASS: password to use for authentication
     * Alternatively, if Auth is done via API key, set ES_API_KEY to the API key.
     *
     * Note: The above environment variables can be set in the test run configuration under "Environment variables"
     */
    private RestClient buildRestClient() {
        String hostname = System.getenv("ES_HOSTNAME");
        String user = System.getenv("ES_USER");
        String pass = System.getenv("ES_PASS");
        String apiKey = System.getenv("ES_API_KEY");

        String auth = java.util.Base64.getEncoder().encodeToString((user + ":" + pass).getBytes(java.nio.charset.StandardCharsets.UTF_8));
        BasicHeader[] defaultHeaders;
        if (Strings.isNullOrEmpty(apiKey)) {
            defaultHeaders = new BasicHeader[] { new BasicHeader("Authorization", "Basic " + auth) };
        } else {
            defaultHeaders = new BasicHeader[] { new BasicHeader("Authorization", "ApiKey " + apiKey) };
        }

        HttpHost https = new HttpHost(hostname, 443, "https");
        return RestClient.builder(https).setDefaultHeaders(defaultHeaders).build();
    }

    /**
     * Configures debug-level logging and the PIT relocation feature flag.
     */
    private void configureDebugSettings(RestClient client, boolean enablePITRelocation) throws IOException {
        Request settingsRequest = new Request("PUT", "/_cluster/settings");
        settingsRequest.setJsonEntity("""
             {
                 "persistent": {
                    "logger.org.elasticsearch.xpack.stateless.recovery.TransportStatelessUnpromotableRelocationAction": "DEBUG",
                    "logger.org.elasticsearch.search.SearchService" : "DEBUG",
                    "logger.org.elasticsearch.action.search" : "DEBUG",
                    "logger.org.elasticsearch.xpack.stateless.recovery" : "DEBUG"
                    // "search.pit_relocation_enabled" : %s
                }
            }
            """.formatted(enablePITRelocation));
        Response response = client.performRequest(settingsRequest);
        System.out.println("---> PUT /_cluster/settings response code: " + response.getStatusLine().getStatusCode());
    }

    /**
     * Resets debug-level logging back to INFO (except TransportStatelessUnpromotableRelocationAction which stays at DEBUG).
     */
    private void resetDebugSettings(RestClient client) throws IOException {
        Request settingsRequest = new Request("PUT", "/_cluster/settings");
        settingsRequest.setJsonEntity("""
             {
                 "persistent": {
                    "logger.org.elasticsearch.xpack.stateless.recovery.TransportStatelessUnpromotableRelocationAction": "DEBUG",
                    "logger.org.elasticsearch.search.SearchService" : "INFO",
                    "logger.org.elasticsearch.action.search" : "INFO",
                    "logger.org.elasticsearch.xpack.stateless.recovery" : "INFO"
                }
            }
            """);
        var response = client.performRequest(settingsRequest);
        System.out.println("---> PUT /_cluster/settings response code: " + response.getStatusLine().getStatusCode());
    }

    private Thread createPITSearchThread(
        RestClient client,
        AtomicReference<String> pitId,
        int expectedPITDocs,
        Thread mainThread,
        AtomicReference<Boolean> pitSearchRunning,
        AtomicInteger searches,
        AtomicBoolean pitIdUpdated
    ) {
        return new Thread(() -> {

            while (pitSearchRunning.get()) {
                try {
                    String updatedPitId = searchAndAssertDocs(client, expectedPITDocs, pitId.get());
                    // check that at some point the PIT ID was updated (which means that the search was redirected to a different node after
                    // relocation)
                    if (pitId != null && pitId.get().equals(updatedPitId) == false) {
                        logger.info("---> PIT ID updated from {} to {}", pitId, updatedPitId);
                        pitIdUpdated.set(true);
                    }
                    pitId.set(updatedPitId);
                    searches.incrementAndGet();
                    if (searches.get() % 100 == 0) {
                        System.out.println("---> PIT search iterations: " + searches);
                    }
                } catch (Throwable e) {
                    logger.error("Exception while searching PIT", e);
                    pitSearchRunning.set(false);
                    mainThread.interrupt();
                    throw new RuntimeException(e);
                }
                // wait a bit to not flood the cluster
                safeSleep(randomTimeValue(1500, 3500, TimeUnit.MILLISECONDS));
            }
        });
    }

    private void waitForDocCount(RestClient client, String indexName, int minDocs) throws InterruptedException, IOException {
        while (true) {
            int count = getDocCount(client, indexName, null);
            if (count >= minDocs) {
                System.out.println("---> Index has " + count + " documents (>= " + minDocs + ")");
                return;
            }
            Thread.sleep(500);
        }
    }

    private int getDocCount(RestClient client, String indexName, String pitId) throws IOException {
        Request searchRequest;
        if (pitId != null) {
            searchRequest = new Request("POST", "/_search");
            searchRequest.setJsonEntity("""
                {
                    "pit": {
                        "id": "%s"
                    },
                    "track_total_hits": true,
                          "query": {
                              "range": {
                                "finished": {
                                  "gte": "2026-05-12T00:00:00.000Z"
                                }
                              }
                          }
                }
                """.formatted(pitId));
        } else {
            searchRequest = new Request("POST", "/" + indexName + "/_search");
            searchRequest.setJsonEntity("""
                {
                    "track_total_hits": true,
                    "query": {
                              "range": {
                                "finished": {
                                  "gte": "2026-05-12T00:00:00.000Z"
                                }
                              }
                          }
                }
                """);
        }
        Response response = client.performRequest(searchRequest);
        Map<String, Object> stringObjectMap = entityAsMap(response.getEntity());
        return ((Number) ObjectPath.evaluate(stringObjectMap, "hits.total.value")).intValue();
    }

    private String searchAndAssertDocs(RestClient client, int numdocs, String pitId) throws IOException {
        assert pitId != null;
        Request searchRequest = new Request("POST", "/_search");
        searchRequest.addParameter("allow_partial_search_results", "false");
        searchRequest.setJsonEntity("""
            {
                "pit": {
                    "id": "%s"
                },
                "track_total_hits": true,
                "query": {
                              "range": {
                                "finished": {
                                  "gte": "2026-05-12T00:00:00.000Z"
                                }
                              }
                          }
            }
            """.formatted(pitId));
        Response response = client.performRequest(searchRequest);
        Map<String, Object> stringObjectMap = entityAsMap(response.getEntity());
        assertThat(ObjectPath.evaluate(stringObjectMap, "hits.total.value"), equalTo(numdocs));
        // return the potentially updated PIT id
        return ObjectPath.evaluate(stringObjectMap, "pit_id").toString();
    }

    private String openPITAndReturnId(RestClient client, String index) throws IOException {
        Request request = new Request("POST", "/" + index + "/_pit?keep_alive=10m");
        Response response = client.performRequest(request);
        String responseBody = EntityUtils.toString(response.getEntity());
        System.out.println("---> POST /" + index + "/_pit response body:\n" + responseBody);
        // Extract and return PIT ID from response if needed
        String pitId = responseBody.split("\"id\":\"")[1].split("\"")[0];
        System.out.println("---> Extracted PIT ID: " + pitId);
        return pitId;
    }

    /**
     * Indexes N documents using the Bulk API. Each document contains:
     * - 10 random strings (field names: str0-str9) with lengths between 100 and 500 characters
     * - 10 random integers (field names: int0-int9)
     * @return List of document IDs that were indexed
     */
    private List<String> bulkIndexDocs(String indexName, int numDocs, RestClient client) throws IOException {
        StringBuilder bulkBody = new StringBuilder();

        for (int i = 0; i < numDocs; i++) {
            // Add bulk action metadata
            bulkBody.append("{\"index\":{\"_index\":\"").append(indexName).append("\"}}\n");

            // Build document with 10 random strings and 10 random integers
            bulkBody.append("{");

            // Add 10 random strings
            for (int j = 0; j < 10; j++) {
                int strLength = randomIntBetween(100, 500);
                String randomString = randomAlphaOfLength(strLength);
                bulkBody.append("\"str").append(j).append("\":\"").append(randomString).append("\"");
                bulkBody.append(",");
            }

            // Add 10 random integers
            for (int j = 0; j < 10; j++) {
                int randomInt = randomInt();
                bulkBody.append("\"int").append(j).append("\":").append(randomInt);
                if (j < 9) {
                    bulkBody.append(",");
                }
            }

            bulkBody.append("}\n");
        }

        Request bulkRequest = new Request("POST", "/_bulk?refresh=true");
        bulkRequest.setJsonEntity(bulkBody.toString());

        Response response = client.performRequest(bulkRequest);
        assertEquals(200, response.getStatusLine().getStatusCode());

        // Parse the response to extract document IDs
        Map<String, Object> responseMap = entityAsMap(response.getEntity());
        List<String> documentIds = new ArrayList<>();

        @SuppressWarnings("unchecked")
        List<Map<String, Object>> items = (List<Map<String, Object>>) responseMap.get("items");
        if (items != null) {
            for (Map<String, Object> item : items) {
                @SuppressWarnings("unchecked")
                Map<String, Object> indexResult = (Map<String, Object>) item.get("index");
                if (indexResult != null) {
                    String id = (String) indexResult.get("_id");
                    if (id != null) {
                        documentIds.add(id);
                    }
                }
            }
        }

        return documentIds;
    }

    /**
     * Bulk deletes documents with the specified IDs using the Bulk API.
     * @param indexName The name of the index
     * @param docIds List of document IDs to delete
     * @param client The RestClient to use
     */
    private void bulkDeleteDocs(String indexName, List<String> docIds, RestClient client) throws IOException {
        if (docIds.isEmpty()) {
            return;
        }

        StringBuilder bulkBody = new StringBuilder();

        for (String docId : docIds) {
            // Add bulk delete action metadata
            bulkBody.append("{\"delete\":{\"_index\":\"").append(indexName).append("\",\"_id\":\"").append(docId).append("\"}}\n");
        }

        Request bulkRequest = new Request("POST", "/_bulk?refresh=true");
        bulkRequest.setJsonEntity(bulkBody.toString());

        Response response = client.performRequest(bulkRequest);
        assertEquals(200, response.getStatusLine().getStatusCode());
    }

    /**
     * Bulk updates documents with the specified IDs by adding a random new field using the Bulk API.
     * @param indexName The name of the index
     * @param docIds List of document IDs to update
     * @param client The RestClient to use
     */
    private void bulkUpdateDocs(String indexName, List<String> docIds, RestClient client) throws IOException {
        if (docIds.isEmpty()) {
            return;
        }

        StringBuilder bulkBody = new StringBuilder();

        for (String docId : docIds) {
            // Add bulk update action metadata
            bulkBody.append("{\"update\":{\"_index\":\"").append(indexName).append("\",\"_id\":\"").append(docId).append("\"}}\n");

            // Add update document with a random new field
            String randomFieldName = "updated_field_" + randomAlphaOfLength(5);
            String randomFieldValue = randomAlphaOfLength(randomIntBetween(50, 200));
            bulkBody.append("{\"doc\":{\"").append(randomFieldName).append("\":\"").append(randomFieldValue).append("\"}}\n");
        }

        Request bulkRequest = new Request("POST", "/_bulk?refresh=true");
        bulkRequest.setJsonEntity(bulkBody.toString());

        Response response = client.performRequest(bulkRequest);
        assertEquals(200, response.getStatusLine().getStatusCode());
    }

    private record PitWithExpectedDocs(AtomicReference<String> pitId, int expectedDocs) {}
}
