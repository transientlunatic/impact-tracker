const fs = require("fs");
const path = require("path");
const fastGlob = require("fast-glob");
const yaml = require("js-yaml");

const ROOT = path.join(__dirname, "..", "..");

module.exports = () => {
  const files = fastGlob.sync("data/people/*.yaml", { cwd: ROOT });
  return files
    .map((file) => yaml.load(fs.readFileSync(path.join(ROOT, file), "utf8")))
    .sort((a, b) => a.name.localeCompare(b.name));
};
