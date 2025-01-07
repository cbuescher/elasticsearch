/*
 * Copyright Elasticsearch B.V. and/or licensed to Elasticsearch B.V. under one
 * or more contributor license agreements. Licensed under the Elastic License
 * 2.0; you may not use this file except in compliance with the Elastic License
 * 2.0.
 */

package org.elasticsearch.xpack.spatial.index.query;

import org.elasticsearch.common.Strings;
import org.elasticsearch.common.geo.GeoJson;
import org.elasticsearch.common.settings.Settings;
import org.elasticsearch.core.UpdateForV9;
import org.elasticsearch.env.Environment;
import org.elasticsearch.geo.GeometryTestUtils;
import org.elasticsearch.geometry.Geometry;
import org.elasticsearch.geometry.MultiPoint;
import org.elasticsearch.geometry.Point;
import org.elasticsearch.index.IndexVersion;
import org.elasticsearch.index.IndexVersions;
import org.elasticsearch.index.mapper.DocumentParsingException;
import org.elasticsearch.index.mapper.MapperParsingException;
import org.elasticsearch.plugins.Plugin;
import org.elasticsearch.test.ESSingleNodeTestCase;
import org.elasticsearch.test.index.IndexVersionUtils;
import org.elasticsearch.xcontent.XContentFactory;
import org.elasticsearch.xpack.spatial.LocalStateSpatialPlugin;
import org.junit.ClassRule;
import org.junit.rules.TemporaryFolder;

import java.io.IOException;
import java.io.OutputStream;
import java.net.URISyntaxException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collection;
import java.util.Collections;
import java.util.Objects;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

import static org.elasticsearch.action.support.WriteRequest.RefreshPolicy.IMMEDIATE;
import static org.elasticsearch.index.query.QueryBuilders.geoIntersectionQuery;
import static org.elasticsearch.index.query.QueryBuilders.geoShapeQuery;
import static org.elasticsearch.index.query.QueryBuilders.matchAllQuery;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertAcked;
import static org.elasticsearch.test.hamcrest.ElasticsearchAssertions.assertHitCount;
import static org.elasticsearch.xcontent.XContentFactory.jsonBuilder;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.greaterThan;

@UpdateForV9(owner = UpdateForV9.Owner.SEARCH_ANALYTICS)
public class LegacyGeoShapeWithDocValuesQueryTests extends ESSingleNodeTestCase {

    private static final String defaultFieldName = "geo";

    @ClassRule
    public static TemporaryFolder REPOSITORY_PATH = new TemporaryFolder();
    private static String defaultIndexName = "changeme";

    @Override
    protected Collection<Class<? extends Plugin>> getPlugins() {
        return Collections.singleton(LocalStateSpatialPlugin.class);
    }

    protected Settings nodeSettings() {
        Settings.Builder settings = Settings.builder().put(super.nodeSettings());
        settings.put(Environment.PATH_REPO_SETTING.getKey(), REPOSITORY_PATH.getRoot().getPath());
        return settings.build();
    }


    @Override
    protected boolean forbidPrivateIndexSettings() {
        return false;
    }

    public void testPointsOnlyExplicit() throws Exception {
        String mapping = Strings.toString(
            XContentFactory.jsonBuilder()
                .startObject()
                .startObject("properties")
                .startObject(defaultFieldName)
                .field("type", "geo_shape")
                .field("tree", randomBoolean() ? "quadtree" : "geohash")
                .field("tree_levels", "6")
                .field("distance_error_pct", "0.01")
                .field("points_only", true)
                .endObject()
                .endObject()
                .endObject()
        );

        String indexName = "geo_points_only";
        MapperParsingException ex = expectThrows(
            MapperParsingException.class,
            () -> indicesAdmin().prepareCreate(indexName).setMapping(mapping).get()
        );
        assertThat(
            ex.getMessage(),
            containsString(
                "using deprecated parameters [points_only, tree, distance_error_pct, tree_levels] "
                    + "in mapper [geo] of type [geo_shape] is no longer allowed"
            )
        );


        // copy, register snapshot and restore snapshot
        String repositoryPath = REPOSITORY_PATH.getRoot().getPath();
        copySnapshotFromResources(repositoryPath, "geo_points_only-v7-snapshot.zip");
        final Settings.Builder repositorySettings = Settings.builder().put("location", repositoryPath);
        assertAcked(
                clusterAdmin().preparePutRepository(TEST_REQUEST_TIMEOUT, TEST_REQUEST_TIMEOUT, "repository")
                        .setType("fs")
                        .setVerify(false)
                        .setSettings(repositorySettings.build())
        );

        System.out.println("---> " + clusterAdmin().prepareGetSnapshots(TEST_REQUEST_TIMEOUT, "repository").get());

        assertThat(
                clusterAdmin().prepareRestoreSnapshot(TEST_REQUEST_TIMEOUT, "repository", "snapshot")
                        .setIndices(indexName)
                        .setWaitForCompletion(true)
                        .get()
                        .getRestoreInfo()
                        .successfulShards(),
                greaterThan(0)
        );

        // MULTIPOINT
        MultiPoint multiPoint = GeometryTestUtils.randomMultiPoint(false);
        prepareIndex(indexName).setId("1")
            .setSource(GeoJson.toXContent(multiPoint, jsonBuilder().startObject().field(defaultFieldName), null).endObject())
            .setRefreshPolicy(IMMEDIATE)
            .get();

        // POINT
        Point point = GeometryTestUtils.randomPoint(false);
        prepareIndex(indexName).setId("2")
            .setSource(GeoJson.toXContent(point, jsonBuilder().startObject().field(defaultFieldName), null).endObject())
            .setRefreshPolicy(IMMEDIATE)
            .get();

        // test that point was inserted
        assertHitCount(client().prepareSearch(indexName).setQuery(matchAllQuery()), 2L);
    }

    public void testPointsOnly() throws Exception {
        String mapping = Strings.toString(
            XContentFactory.jsonBuilder()
                .startObject()
                .startObject("properties")
                .startObject(defaultFieldName)
                .field("type", "geo_shape")
                .field("tree", randomBoolean() ? "quadtree" : "geohash")
                .field("tree_levels", "6")
                .field("distance_error_pct", "0.01")
                .field("points_only", true)
                .endObject()
                .endObject()
                .endObject()
        );

        MapperParsingException ex = expectThrows(
            MapperParsingException.class,
            () -> indicesAdmin().prepareCreate("geo_points_only").setMapping(mapping).get()
        );
        assertThat(
            ex.getMessage(),
            containsString(
                "using deprecated parameters [points_only, tree, distance_error_pct, tree_levels] "
                    + "in mapper [geo] of type [geo_shape] is no longer allowed"
            )
        );

        IndexVersion version = IndexVersionUtils.randomPreviousCompatibleVersion(random(), IndexVersions.V_8_0_0);
        Settings settings = settings(version).build();
        indicesAdmin().prepareCreate("geo_points_only").setMapping(mapping).setSettings(settings).get();
        ensureGreen();

        Geometry geometry = GeometryTestUtils.randomGeometry(false);
        try {
            prepareIndex("geo_points_only").setId("1")
                .setSource(GeoJson.toXContent(geometry, jsonBuilder().startObject().field(defaultFieldName), null).endObject())
                .setRefreshPolicy(IMMEDIATE)
                .get();
        } catch (DocumentParsingException e) {
            // Random geometry generator created something other than a POINT type, verify the correct exception is thrown
            assertThat(e.getMessage(), containsString("is configured for points only"));
            return;
        }

        // test that point was inserted
        assertHitCount(client().prepareSearch("geo_points_only").setQuery(geoIntersectionQuery(defaultFieldName, geometry)), 1L);
    }

    public void testFieldAlias() throws IOException {
        String mapping = Strings.toString(
            XContentFactory.jsonBuilder()
                .startObject()
                .startObject("properties")
                .startObject(defaultFieldName)
                .field("type", "geo_shape")
                .field("tree", randomBoolean() ? "quadtree" : "geohash")
                .endObject()
                .startObject("alias")
                .field("type", "alias")
                .field("path", defaultFieldName)
                .endObject()
                .endObject()
                .endObject()
        );

        MapperParsingException ex = expectThrows(
            MapperParsingException.class,
            () -> indicesAdmin().prepareCreate(defaultIndexName).setMapping(mapping).get()
        );
        assertThat(
            ex.getMessage(),
            containsString("using deprecated parameters [tree] in mapper [geo] of type [geo_shape] is no longer allowed")
        );

        IndexVersion version = IndexVersionUtils.randomPreviousCompatibleVersion(random(), IndexVersions.V_8_0_0);
        Settings settings = settings(version).build();
        indicesAdmin().prepareCreate(defaultIndexName).setMapping(mapping).setSettings(settings).get();
        ensureGreen();

        MultiPoint multiPoint = GeometryTestUtils.randomMultiPoint(false);
        prepareIndex(defaultIndexName).setId("1")
            .setSource(GeoJson.toXContent(multiPoint, jsonBuilder().startObject().field(defaultFieldName), null).endObject())
            .setRefreshPolicy(IMMEDIATE)
            .get();

        assertHitCount(client().prepareSearch(defaultIndexName).setQuery(geoShapeQuery("alias", multiPoint)), 1L);
    }

    private static void copySnapshotFromResources(String repositoryPath, String snapshotName) throws IOException, URISyntaxException {
        Path zipFilePath = Paths.get(
                Objects.requireNonNull(LegacyGeoShapeWithDocValuesQueryTests.class.getClassLoader().getResource(snapshotName))
                        .toURI()
        );
        unzip(zipFilePath, Paths.get(repositoryPath));
    }

    private static void unzip(Path zipFilePath, Path outputDir) throws IOException {
        try (ZipInputStream zipIn = new ZipInputStream(Files.newInputStream(zipFilePath))) {
            ZipEntry entry;
            while ((entry = zipIn.getNextEntry()) != null) {
                Path outputPath = outputDir.resolve(entry.getName());
                if (entry.isDirectory()) {
                    Files.createDirectories(outputPath);
                } else {
                    Files.createDirectories(outputPath.getParent());
                    try (OutputStream out = Files.newOutputStream(outputPath)) {
                        byte[] buffer = new byte[1024];
                        int len;
                        while ((len = zipIn.read(buffer)) > 0) {
                            out.write(buffer, 0, len);
                        }
                    }
                }
                zipIn.closeEntry();
            }
        }
    }
}
