const history = require("./history.js");

// { [outputId]: { [metric]: value } } - the most recent recorded value per
// metric per output, used for stat tiles and leaderboards.
module.exports = () => {
  const all = history();
  const latest = {};
  for (const [id, rows] of Object.entries(all)) {
    const byMetric = {};
    for (const row of rows) {
      // rows are sorted ascending, so the last write per metric wins.
      byMetric[row.metric] = row.value;
    }
    latest[id] = byMetric;
  }
  return latest;
};
