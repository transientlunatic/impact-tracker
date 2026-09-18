module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy({ "src/assets": "assets" });
  eleventyConfig.addPassthroughCopy({ "node_modules/d3/dist/d3.min.js": "assets/js/d3.min.js" });
  eleventyConfig.setDataDeepMerge(true);

  eleventyConfig.addFilter("dateFormat", (isoDate) => {
    if (!isoDate) return "";
    const d = new Date(`${isoDate}T00:00:00Z`);
    return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
  });

  eleventyConfig.addFilter("sum", (values) => (values || []).reduce((a, b) => a + b, 0));

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes",
      data: "_data",
    },
    pathPrefix: process.env.PATH_PREFIX || "/",
  };
};
