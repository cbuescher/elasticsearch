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

package org.elasticsearch.transport.client;

import org.elasticsearch.action.index.IndexResponse;
import org.elasticsearch.client.Client;
import org.elasticsearch.client.IndicesAdminClient;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.common.transport.TransportAddress;

import java.net.InetAddress;
import java.net.UnknownHostException;

public class Test {


    public static void main(String[] arg) throws UnknownHostException {
        Settings settings = Settings.builder()
                .put("cluster.name", "elasticsearch")
                .build();

          Client client = new PreBuiltTransportClient(settings)
                              .addTransportAddress(new TransportAddress(InetAddress.getByName("127.0.0.1"), 9300));

          IndicesAdminClient indicesAdminClient = client.admin().indices();

          indicesAdminClient.prepareCreate("calls")
          .setSettings(Settings.builder()
                  .put("index.number_of_shards", 10)
          )
         .addMapping("call", "{\n" +
                  "    \"call\": {\n" +
                  "      \"properties\": {\n" +
                  "        \"id\": {\n" +
                  "          \"type\": \"string\"}\n" +
                  "           },\n" +
                  "        \"number\": {\n" +
                  "          \"type\": \"string\"}\n" +
                  "           },\n" +
                  "        \"name\": {\n" +
                  "          \"type\": \"string\"\n" +
                  "        }\n" +
                  "      }\n" +
                  "    }\n" +
                  "  }")
          .get();

          String json = "{" +

                  "\"id\":\"1\"," +
                  "\"number\":\"123333333\"," +
                  "\"name\":\"Sharon Tries Elastic\"" +
              "}";

      IndexResponse response = client.prepareIndex("calls", "call")
              .setSource(json)
              .get();

      // Index name
      String _index = response.getIndex();
      // Type name
      String _type = response.getType();
      // Document ID (generated or not)
      String _id = response.getId();
      // Version (if it's the first time you index this document, you will get: 1)
      long _version = response.getVersion();
      client.close();
    }
}
