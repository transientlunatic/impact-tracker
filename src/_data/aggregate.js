const history = require("./history.js");

// { [metric]: [{date, value}, ...] } - sum across every output, grouped by
// exact date. Accurate as long as the metrics were recorded by the same
// scheduled run (data/../fetch-metrics.yml fetches all outputs together
// once per run, so their history rows share a date).
module.exports = () => {
  const all = history();
  const byMetricDate = {};
  for (const rows of Object.values(all)) {
    for (const row of rows) {
      byMetricDate[row.metric] = byMetricDate[row.metric] || {};
      byMetricDate[row.metric][row.date] = (byMetricDate[row.metric][row.date] || 0) + row.value;
    }
  }
  const result = {};
  for (const [metric, dateMap] of Object.entries(byMetricDate)) {
    result[metric] = Object.entries(dateMap)
      .map(([date, value]) => ({ date, value }))
      .sort((a, b) => a.date.localeCompare(b.date));
  }
  return result;
};
