/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License
 * 2.0 and the Server Side Public License, v 1; you may not use this file except
 * in compliance with, at your election, the Elastic License 2.0 or the Server
 * Side Public License, v 1.
 */

package org.elasticsearch.test.rest.yaml;

import com.carrotsearch.randomizedtesting.annotations.ParametersFactory;
import com.carrotsearch.randomizedtesting.annotations.TimeoutSuite;

import org.apache.http.HttpEntity;
import org.apache.http.HttpHost;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.lucene.tests.util.TimeUnits;
import org.elasticsearch.Version;
import org.elasticsearch.client.NodeSelector;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.elasticsearch.core.IOUtils;
import org.elasticsearch.core.Tuple;
import org.elasticsearch.test.rest.ObjectPath;
import org.elasticsearch.test.rest.yaml.section.ClientYamlTestSection;
import org.elasticsearch.test.rest.yaml.section.DoSection;
import org.elasticsearch.test.rest.yaml.section.ExecutableSection;
import org.elasticsearch.test.rest.yaml.section.MatchAssertion;
import org.junit.AfterClass;
import org.junit.Before;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static java.util.Collections.unmodifiableList;

@TimeoutSuite(millis = 15 * TimeUnits.MINUTE) // to account for slow as hell VMs
public class CcsCommonYamlTestSuiteIT extends ESClientYamlSuiteTestCase {

    private static final Logger logger = LogManager.getLogger(CcsCommonYamlTestSuiteIT.class);
    private static RestClient searchClient;
    private static RestClient adminSearchClient;
    private static List<HttpHost> clusterHosts;
    private static ClientYamlTestClient searchYamlTestClient;

    // the remote cluster is the one we write index operations etc... to
    private static final String REMOTE_CLUSTER_NAME = "remote_cluster";
    // the following are the CCS api calls that we run against the "search" cluster in this test setup
    private static final Set<String> CCS_APIS = Set.of(
        "search",
        "field_caps",
        "msearch",
        "scroll",
        "clear_scroll",
        "indices.resolve_index"
    );

    @Before
    public void initSearchClient() throws IOException {
        if (searchClient == null) {
            assert adminSearchClient == null;
            assert clusterHosts == null;

            final String cluster = System.getProperty("tests.rest.search_cluster");
            assertNotNull("[tests.rest.search_cluster] is not configured", cluster);
            String[] stringUrls = cluster.split(",");
            List<HttpHost> hosts = new ArrayList<>(stringUrls.length);
            for (String stringUrl : stringUrls) {
                int portSeparator = stringUrl.lastIndexOf(':');
                if (portSeparator < 0) {
                    throw new IllegalArgumentException("Illegal cluster url [" + stringUrl + "]");
                }
                String host = stringUrl.substring(0, portSeparator);
                int port = Integer.parseInt(stringUrl.substring(portSeparator + 1));
                hosts.add(buildHttpHost(host, port));
            }
            clusterHosts = unmodifiableList(hosts);
            logger.info("initializing REST search clients against {}", clusterHosts);
            searchClient = buildClient(restClientSettings(), clusterHosts.toArray(new HttpHost[clusterHosts.size()]));
            adminSearchClient = buildClient(restAdminSettings(), clusterHosts.toArray(new HttpHost[clusterHosts.size()]));

            Tuple<Version, Version> versionVersionTuple = readVersionsFromCatNodes(adminSearchClient);
            final Version esVersion = versionVersionTuple.v1();
            final Version masterVersion = versionVersionTuple.v2();
            final String os = readOsFromNodesInfo(adminSearchClient);

            searchYamlTestClient = new ClientYamlTestClient(
                getRestSpec(),
                searchClient,
                hosts,
                esVersion,
                masterVersion,
                os,
                this::getClientBuilderWithSniffedHosts
            ) {
                public ClientYamlTestResponse callApi(
                    String apiName,
                    Map<String, String> params,
                    HttpEntity entity,
                    Map<String, String> headers,
                    NodeSelector nodeSelector
                ) throws IOException {
                    // on request, we need to replace index specifications by prefixing the remote cluster
                    if (apiName.equals("scroll") == false && apiName.equals("clear_scroll") == false) {
                        String parameterName = "index";
                        if (apiName.equals("indices.resolve_index")) {
                            // in this api the index parameter is called "name"
                            parameterName = "name";
                        }
                        String originalIndices = params.get(parameterName);
                        String expandedIndices = REMOTE_CLUSTER_NAME + ":*";
                        if (originalIndices != null && (originalIndices.isEmpty() == false)) {
                            String[] indices = originalIndices.split(",");
                            List<String> newIndices = new ArrayList<>();
                            for (String indexName : indices) {
                                newIndices.add(REMOTE_CLUSTER_NAME + ":" + indexName);
                            }
                            expandedIndices = String.join(",", newIndices);
                        }
                        params.put(parameterName, String.join(",", expandedIndices));
                    }
                    ClientYamlTestResponse clientYamlTestResponse = super.callApi(apiName, params, entity, headers, nodeSelector);
                    logger.info(clientYamlTestResponse.getBodyAsString());
                    return clientYamlTestResponse;
                };
            };

            // check that we have an established CCS connection
            Request request = new Request("GET", "_remote/info");
            Response response = adminSearchClient.performRequest(request);
            assertOK(response);
            ObjectPath responseObject = ObjectPath.createFromResponse(response);
            assertNotNull(responseObject.evaluate(REMOTE_CLUSTER_NAME));
            logger.info("Established connection to remote cluster [" + REMOTE_CLUSTER_NAME + "]");
        }

        assert searchClient != null;
        assert adminSearchClient != null;
        assert clusterHosts != null;
    }

    public CcsCommonYamlTestSuiteIT(ClientYamlTestCandidate testCandidate) throws IOException {
        super(rewrite(testCandidate));
    }

    private static ClientYamlTestCandidate rewrite(ClientYamlTestCandidate clientYamlTestCandidate) {
        ClientYamlTestSection testSection = clientYamlTestCandidate.getTestSection();
        List<ExecutableSection> executableSections = testSection.getExecutableSections();
        List<ExecutableSection> modifiedExecutableSections = new ArrayList<>();
        String lastAPIDoSection = "";
        for (ExecutableSection section : executableSections) {
            ExecutableSection rewrittenSection = section;
            if (section instanceof MatchAssertion) {
                MatchAssertion matchSection = (MatchAssertion) section;
                if (matchSection.getField().endsWith("_index")) {
                    String modifiedExpectedValue = REMOTE_CLUSTER_NAME + ":" + matchSection.getExpectedValue();
                    rewrittenSection = new MatchAssertion(matchSection.getLocation(), matchSection.getField(), modifiedExpectedValue);
                }
                if (lastAPIDoSection.equals("indices.resolve_index") && matchSection.getField().endsWith("name")) {
                    // modify " indices.resolve_index" expected index names
                    String modifiedExpectedValue = REMOTE_CLUSTER_NAME + ":" + matchSection.getExpectedValue();
                    rewrittenSection = new MatchAssertion(matchSection.getLocation(), matchSection.getField(), modifiedExpectedValue);
                }
            } else if (section instanceof DoSection) {
                lastAPIDoSection = ((DoSection) section).getApiCallSection().getApi();
                if (lastAPIDoSection.equals("msearch")) {
                    // modify "msearch" body sections so the "index" part is targeting the remote cluster
                    DoSection doSection = ((DoSection) section);
                    List<Map<String, Object>> bodies = doSection.getApiCallSection().getBodies();
                    for (Map<String, Object> body : bodies) {
                        if (body.containsKey("index")) {
                            String modifiedIndex = REMOTE_CLUSTER_NAME + ":" + body.get("index");
                            body.put("index", modifiedIndex);
                        }
                    }
                }
            }
            modifiedExecutableSections.add(rewrittenSection);
        }
        return new ClientYamlTestCandidate(
            clientYamlTestCandidate.getRestTestSuite(),
            new ClientYamlTestSection(
                testSection.getLocation(),
                testSection.getName(),
                testSection.getSkipSection(),
                modifiedExecutableSections
            )
        );
    };

    @ParametersFactory
    public static Iterable<Object[]> parameters() throws Exception {
        return createParameters();
    }

    @Override
    protected ClientYamlTestExecutionContext createRestTestExecutionContext(
        ClientYamlTestCandidate clientYamlTestCandidate,
        ClientYamlTestClient clientYamlTestClient
    ) {
        return new ClientYamlTestExecutionContext(clientYamlTestCandidate, clientYamlTestClient, randomizeContentType()) {
            protected ClientYamlTestClient clientYamlTestClient(String apiName) {
                if (CCS_APIS.contains(apiName)) {
                    return searchYamlTestClient;
                } else {
                    return super.clientYamlTestClient(apiName);
                }
            }
        };
    }

    @AfterClass
    public static void closeSearchClients() throws IOException {
        try {
            IOUtils.close(searchClient, adminSearchClient);
        } finally {
            clusterHosts = null;
        }
    }
}
