def status = false;
for(environment in ctx.payload.aggregations.environments.buckets) {
  for(track in environment.tracks.buckets) {
    for (setup in track.setups.buckets) {
      for (name in setup.names.buckets) {

        def std_upper = Double.valueOf(name.series_stats.std_deviation_bounds.upper);
        def std_lower = Double.valueOf(name.series_stats.std_deviation_bounds.lower);
        def avg = Double.valueOf(name.series.buckets.last().avg.value);
        if (std_upper == Double.NaN || avg == Double.NaN || std_lower == Double.NaN) {
          continue;
        }
        if (avg > std_upper || avg < std_lower) {
          status = true;
          break;
        }
      }
    }
  }
}

return status;
