var chartingLib = {
      createOpts: function(title, labelsDiv, yLabel) {
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
            "gridLineColor": "#BBB"
            //"strokePattern": [5, 10]
        }
    },

      renderChart: function(elementId, title, yLabel, annotationSource) {
          var g = new Dygraph(
              document.getElementById("chart_" + elementId),
              elementId + ".csv",
              this.createOpts("<a href='#" + elementId + "'>" + title + "</a>", "chart_" + elementId + "_labels", yLabel)
          );
          g.ready(function() {
            var annotationSource = elementId + '_annotations.json'
            $.getJSON(annotationSource, function(json) {
              g.setAnnotations(json);
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
