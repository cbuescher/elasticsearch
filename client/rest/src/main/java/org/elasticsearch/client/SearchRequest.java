package org.elasticsearch.client;
import java.util.Collections;
import java.util.Map;
import java.util.Objects;

import org.elasticsearch.common.Strings;
import org.elasticsearch.search.builder.SearchSourceBuilder;

public class SearchRequest {

    private SearchSourceBuilder searchSourceBuilder = new SearchSourceBuilder();
    private String[] indices = Strings.EMPTY_ARRAY;
    private String[] types = Strings.EMPTY_ARRAY;
    Map<String, String> urlParams = Collections.emptyMap();

    public SearchRequest(SearchSourceBuilder searchSource) {
        this.searchSourceBuilder = Objects.requireNonNull(searchSource);
    }

    public SearchRequest indices(String... indices) {
        this.indices = Objects.requireNonNull(indices);
        return this;
    }

    public SearchRequest types(String... types) {
        this.types = Objects.requireNonNull(types);
        return this;
    }

    public SearchRequest params(Map<String, String> urlParams) {
        this.urlParams = Objects.requireNonNull(urlParams);
        return this;
    }

    public SearchSourceBuilder searchSource() {
        return this.searchSourceBuilder;
    }

    public String[] indices() {
        return this.indices;
    }

    public String[] types() {
        return this.types;
    }

    public Map<String, String> params() {
        return this.urlParams;
    }
}
