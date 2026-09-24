const outputs = require("./outputs.js");

// { [personId]: [{id, title, type, created}, ...] } - every output whose
// group_authors names this person, newest first. Drives the "papers" list
// on the people pages without every template re-scanning all outputs.
module.exports = () => {
  const all = outputs();
  const byPerson = {};
  for (const output of all) {
    for (const personId of output.group_authors || []) {
      byPerson[personId] = byPerson[personId] || [];
      byPerson[personId].push({
        id: output.id,
        title: output.title,
        type: output.type,
        created: output.created,
      });
    }
  }
  for (const list of Object.values(byPerson)) {
    list.sort((a, b) => b.created.localeCompare(a.created));
  }
  return byPerson;
};
