def alerts = [];
for(environment in ctx.payload.aggregations.environments.buckets) {
  for(track in environment.tracks.buckets) {
    for (setup in track.setups.buckets) {
      for (name in setup.names.buckets) {

        def std_upper = Double.valueOf(name.series_stats.std_deviation_bounds.upper);
        def std_lower = Double.valueOf(name.series_stats.std_deviation_bounds.lower);
        def avg = Double.valueOf(name.series.buckets.last().avg.value);
        if (Double.isNaN(std_upper) || Double.isNaN(std_lower) || Double.isNaN(avg)) {
          continue;
        }
        if (avg > std_upper) {
          String date = new Date(name.series.buckets.last().key).toString()

          alerts << [
                  title      : environment.key + "::" + track.key + "::" + setup.key + "::" + name.key,
                  value      : avg - std_upper,
                  threshold  : std_upper,
                  date       : date,
                  descriptor1: "greater",
                  descriptor2: "above"
          ];
        }
        if (avg < std_lower) {
          String date = new Date(name.series.buckets.last().key).toString()

          alerts << [
                  title      : environment.key + "::" + track.key + "::" + setup.key + "::" + name.key,
                  value      : std_lower - avg,
                  threshold  : std_lower,
                  date       : date,
                  descriptor1: "lower",
                  descriptor2: "below"
          ];
        }
      }
    }
  }
}

return [alerts: alerts];
