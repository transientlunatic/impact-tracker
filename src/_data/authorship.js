const outputs = require("./outputs.js");

// { [personId]: [{id, title, type, created, roles, detail}, ...] } - every
// output whose group_authors names this person, newest first, along with
// their CRediT roles/detail on that output. Drives the "papers" list on
// the people pages without every template re-scanning all outputs.
module.exports = () => {
  const all = outputs();
  const byPerson = {};
  for (const output of all) {
    for (const entry of output.group_authors || []) {
      byPerson[entry.id] = byPerson[entry.id] || [];
      byPerson[entry.id].push({
        id: output.id,
        title: output.title,
        type: output.type,
        created: output.created,
        roles: entry.roles || [],
        detail: entry.detail || "",
      });
    }
  }
  for (const list of Object.values(byPerson)) {
    list.sort((a, b) => b.created.localeCompare(a.created));
  }
  return byPerson;
};
