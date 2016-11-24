package org.elasticsearch.client;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import org.elasticsearch.common.xcontent.XContentBuilder;
import org.elasticsearch.common.xcontent.XContentFactory;
import org.elasticsearch.index.query.MatchQueryBuilder;
import org.elasticsearch.search.builder.SearchSourceBuilder;

public class MainApp {

    public static void main(String[] args) throws IOException {
        try (ESJavaClient client = new ESJavaClient("localhost", 9200)) {

            SearchRequest request = new SearchRequest(new SearchSourceBuilder()).indices("index");
            SearchResponse response = client.performSearchRequest(request);
            System.out.println("took: " + response.get("took"));
            System.out.println("total hits: " + response.get("hits.total"));
            System.out.println(mapToString(response.getMap()));

            Map<String, String> urlParams = new HashMap<>();
            urlParams.put("pretty", "true");
            urlParams.put("q", "title:john");
            request = new SearchRequest(new SearchSourceBuilder()).indices("index").params(urlParams);
            response = client.performSearchRequest(request);
            System.out.println("took: " + response.get("took"));
            System.out.println("total hits: " + response.get("hits.total"));
            System.out.println(mapToString(response.getMap()));

            urlParams = new HashMap<>();
            urlParams.put("pretty", "true");
            SearchSourceBuilder source = new SearchSourceBuilder().query(
                    new MatchQueryBuilder("title.keyword", "John F. Kennedy"));
            request = new SearchRequest(source).indices("enwiki_rank").params(urlParams);
            response = client.performSearchRequest(request);
            System.out.println("took: " + response.get("took"));
            System.out.println("total hits: " + response.get("hits.total"));
            System.out.println(response.get("hits.hits.0._source.title"));
        }
    }

    private static String mapToString(Map<String, Object> map) throws IOException {
        XContentBuilder builder = XContentFactory.jsonBuilder();
        builder.prettyPrint();
        builder.map(map);
        return builder.string();
    }
}
