package org.elasticsearch.client;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;

import org.apache.http.util.EntityUtils;
import org.elasticsearch.common.xcontent.XContentFactory;
import org.elasticsearch.common.xcontent.XContentParser;
import org.elasticsearch.common.xcontent.XContentType;

public class SearchResponse {

    private ObjectPath object;
    private Map<String, Object> map;

    public SearchResponse(Response response) throws IOException {
        String contentType = response.getHeader("Content-Type");
        String body = EntityUtils.toString(response.getEntity(), StandardCharsets.UTF_8);
        XContentType xContentType = XContentType.fromMediaTypeOrFormat(contentType);
        this.object = ObjectPath.createFromXContent(xContentType.xContent(), body);
        XContentParser parser = XContentFactory.xContent(body).createParser(body);
        this.map = parser.mapOrdered();
    }

    public ObjectPath getObjectPath() {
        return this.object;
    }


    public Map<String, Object> getMap() {
        return this.map;
    }

    @SuppressWarnings("unchecked")
    public Object get(String path) throws IOException {
//        String[] parts = path.split("\\.");
//        if (parts.length == 0) {
//            return null;
//        }
//        if (parts.length == 1) {
//
//            return this.map.get(parts[0]);
//        } else {
//            Map<String, Object> subMap = (Map<String, Object>) map.get(parts[0]);
//            for (int i = 1; i < parts.length - 1; i++) {
//                subMap = (Map<String, Object>) subMap.get(parts[i]);
//            }
//            return subMap.get(parts[parts.length - 1]);
//        }
        return object.evaluate(path);
    }

}
