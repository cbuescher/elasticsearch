package org.elasticsearch.client;
import java.io.Closeable;
import java.io.IOException;

import org.apache.http.HttpHost;
import org.apache.http.entity.StringEntity;

public class ESJavaClient implements Closeable {

    private RestClient restClient;

    public ESJavaClient(String host, int port) {
        this.restClient = RestClient.builder(new HttpHost(host, port)).build();
    }

    @Override
    public void close() throws IOException {
        this.restClient.close();
        this.restClient = null;
    }

    public SearchResponse performSearchRequest(SearchRequest request) throws IOException {
        StringEntity entity = new StringEntity(request.searchSource().toString());
        String indices = String.join(",", request.indices());
        if (indices.length() > 0) {
            indices = indices + "/";
        }
        String types = String.join(",", request.types());
        if (types.length() > 0) {
            indices = indices + "/";
        }
        Response response = this.restClient.performRequest("GET",
                "/" + indices + types + "_search", request.urlParams, entity);
        return new SearchResponse(response);
    }
}
