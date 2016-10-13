var chartingLib = {
    createOpts: function(title, labelsDiv, yLabel, commits) {
        return {
            "title": title,
            "colors": ["#00BFB3", "#FED10A", "#0078A0", "#DF4998", "#93C90E", "#00A9E5", "#222", "#AAA", "#777"],
            "axisLabelColor": "#555",
            "axisLineColor": "#555",
            "labelsUTC": false,
            "includeZero": true,
            "xlabel": "Timestamp (UTC)",
            "ylabel": yLabel,
            "connectSeparatedPoints": true,
            "hideOverlayOnMouseOut": false,
            "labelsDiv": labelsDiv,
            "labelsSeparateLines": true,
            "legend": "always",
            "drawPoints": true,
            "pointSize": 3,
            "gridLineColor": "#BBB",
            pointClickCallback: function(e, p) {
                    var commitInfo = commits[p.xval];
                    if (commitInfo) {
                        var url = "https://github.com/elastic/elasticsearch/compare/" + commitInfo.prev_commit + "..." + commitInfo.this_commit;
                        window.open(url);
                    }
                }
                //"strokePattern": [5, 10]
        }
    },

    renderChart: function(elementId, title, yLabel, annotationSource) {
        var commits = {};
        var g = new Dygraph(
            document.getElementById("chart_" + elementId),
            elementId + ".csv",
            this.createOpts("<a href='#" + elementId + "'>" + title + "</a>", "chart_" + elementId + "_labels", yLabel, commits)
        );
        g.ready(function() {
            var annotationSource = elementId + '_annotations.json'
            $.getJSON(annotationSource, function(json) {
                g.setAnnotations(json);
            });
            $.ajax({
                type: 'GET',
                url: 'source_revision.csv',
                dataType: 'text',
                success: function(allText) {
                    var allTextLines = allText.split(/\r\n|\n/);

                    var previousCommit = null;
                    for (var i = 1; i < allTextLines.length; i++) {
                        var data = allTextLines[i].split(',');
                        var date = new Date(data[0]);
                        commits[date.getTime()] = {
                            this_commit: data[1],
                            prev_commit: previousCommit
                        };
                        previousCommit = data[1];
                    }
                }
            });
        });
        return g;
    },

    // Multiple column bar chart
    multiColumnBarPlotter: function(e) {
        // We need to handle all the series simultaneously.
        if (e.seriesIndex !== 0) return;

        var g = e.dygraph;
        var ctx = e.drawingContext;
        var sets = e.allSeriesPoints;
        var y_bottom = e.dygraph.toDomYCoord(0);
        var bar_width = 5.0

        if (sets.length > 1) {
            // Find the minimum separation between x-values.
            // This determines the bar width.
            var min_sep = Infinity;
            for (var j = 0; j < sets.length; j++) {
                var points = sets[j];
                for (var i = 1; i < points.length; i++) {
                    var sep = points[i].canvasx - points[i - 1].canvasx;
                    if (sep < min_sep) min_sep = sep;
                }
            }
            bar_width = Math.max(Math.floor(2.0 / 3 * min_sep), bar_width);
         }

        var fillColors = [];
        var strokeColors = g.getColors();
        for (var i = 0; i < strokeColors.length; i++) {
            var color = Dygraph.toRGB_(strokeColors[i]);
            color.r = Math.floor((255 + color.r) / 2);
            color.g = Math.floor((255 + color.g) / 2);
            color.b = Math.floor((255 + color.b) / 2);
            darkened = 'rgb(' + color.r + ',' + color.g + ',' + color.b + ')';
            fillColors.push(darkened);
        }

        for (var j = 0; j < sets.length; j++) {
            ctx.fillStyle = fillColors[j];
            ctx.strokeStyle = strokeColors[j];
            for (var i = 0; i < sets[j].length; i++) {
                var p = sets[j][i];
                var center_x = p.canvasx;
                var x_left = center_x - (bar_width / 2) * (1 - j / Math.max(sets.length - 1, 1));

                ctx.fillRect(x_left, p.canvasy,
                    bar_width / sets.length, y_bottom - p.canvasy);

                ctx.strokeRect(x_left, p.canvasy,
                    bar_width / sets.length, y_bottom - p.canvasy);
            }
        }
    },

    comparisonParser: function(versions) {
        return function(str) {
            return $.inArray(str, versions) + 1;
        }
    },


    createBarOpts: function(title, labelsDiv, yLabel, versions) {
        return {
            "title": title,
            "colors": ["#00BFB3", "#FED10A", "#0078A0", "#DF4998", "#93C90E", "#00A9E5", "#222", "#AAA", "#777"],
            "axisLabelColor": "#555",
            "axisLineColor": "#555",
            "labelsUTC": false,
            "includeZero": true,
            "xlabel": "Elasticsearch Version",
            "ylabel": yLabel,
            "hideOverlayOnMouseOut": false,
            "labelsDiv": labelsDiv,
            "labelsSeparateLines": true,
            "legend": "always",
            "drawPoints": false,
            "pointSize": 0,
            "gridLineColor": "#BBB",
            "plotter": this.multiColumnBarPlotter,
            // use a gap of 1 on each side to ensure we show all bars
            "dateWindow": [0, versions.length + 1],
            "xValueParser": this.comparisonParser(versions),
            "axes": {
                "x": {
                    "axisLabelFormatter": function(x) {
                        var v = versions[x - 1];
                        if (v === undefined) {
                            return ""
                        } else {
                            return v
                        }
                    }
                }
            },
            "legend": "always",
            "valueFormatter": function(x, opts, seriesName, dygraph, row, col) {
                var v = versions[x - 1];
                if (v === undefined) {
                    return ""
                } else {
                    return v
                }
            }
        }
    },


    renderBarChart: function(elementId, title, yLabel, versions) {
        var g = new Dygraph(
            document.getElementById("chart_" + elementId),
            elementId + "_comparison.csv",
            this.createBarOpts("<a href='#" + elementId + "'>" + title + "</a>", "chart_" + elementId + "_labels", yLabel, versions)
        );
        return g;
    },

    synchronize: function(graphs) {
        var sync = Dygraph.synchronize(graphs, {
            selection: false,
            zoom: true,
            // synchronize x-axis only
            range: false
        });
    }
};