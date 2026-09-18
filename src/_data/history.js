const fs = require("fs");
const path = require("path");
const fastGlob = require("fast-glob");

const ROOT = path.join(__dirname, "..", "..");

// { [outputId]: [{date, metric, value}, ...] } sorted by date ascending.
module.exports = () => {
  const files = fastGlob.sync("data/history/*.jsonl", { cwd: ROOT });
  const history = {};
  for (const file of files) {
    const id = path.basename(file, ".jsonl");
    const text = fs.readFileSync(path.join(ROOT, file), "utf8");
    const rows = text
      .split("\n")
      .filter((line) => line.trim().length)
      .map((line) => JSON.parse(line));
    rows.sort((a, b) => a.date.localeCompare(b.date));
    history[id] = rows;
  }
  return history;
};
