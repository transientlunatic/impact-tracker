const fs = require("fs");
const path = require("path");
const fastGlob = require("fast-glob");

const ROOT = path.join(__dirname, "..", "..");

// { [outputId]: [{date, kind, label, url}, ...] } sorted by date ascending.
module.exports = () => {
  const files = fastGlob.sync("data/events/*.jsonl", { cwd: ROOT });
  const events = {};
  for (const file of files) {
    const id = path.basename(file, ".jsonl");
    const text = fs.readFileSync(path.join(ROOT, file), "utf8");
    const rows = text
      .split("\n")
      .filter((line) => line.trim().length)
      .map((line) => JSON.parse(line));
    rows.sort((a, b) => a.date.localeCompare(b.date));
    events[id] = rows;
  }
  return events;
};
