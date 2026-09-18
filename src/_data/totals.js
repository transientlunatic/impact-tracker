const outputsData = require("./outputs.js");
const latestData = require("./latest.js");

module.exports = () => {
  const outputs = outputsData();
  const latest = latestData();

  const sum = (metric) =>
    Object.values(latest).reduce((acc, metrics) => acc + (metrics[metric] || 0), 0);

  const countsByType = outputs.reduce((acc, output) => {
    acc[output.type] = (acc[output.type] || 0) + 1;
    return acc;
  }, {});

  return {
    totalOutputs: outputs.length,
    countsByType,
    totalStars: sum("github_stars"),
    totalCitations: sum("citations_ads") + sum("citations_inspire"),
    totalAltmetric: Math.round(sum("altmetric_score") * 10) / 10,
    totalZenodoDownloads: sum("zenodo_downloads"),
  };
};
