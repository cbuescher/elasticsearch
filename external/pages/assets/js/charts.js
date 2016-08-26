var chartingLib = {
      createOpts: function(title, labelsDiv, yLabel, commits) {
        return { "title": title,
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
                var url = "https://github.com/elastic/elasticsearch/compare/" + commitInfo.prev_commit + "..." +  commitInfo.this_commit;
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
              for (var i=1; i<allTextLines.length; i++) {
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

      synchronize: function(graphs) {
        var sync = Dygraph.synchronize(graphs, {
            selection: false,
            zoom: true,
            // synchronize x-axis only
            range: false
        });
      }
};
