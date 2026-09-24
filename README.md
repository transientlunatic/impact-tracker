# Impact Tracker

Tracks impact metrics for a research group's outputs &mdash; software,
publications, and datasets &mdash; and their evolution over time, and
publishes an interactive D3 dashboard to GitHub Pages.

## How it works

```
data/outputs/*.yaml    one file per research output (metadata + which
                        automated fetchers apply to it)
data/people/*.yaml     one file per group member, current or former
                        (name, ORCID, role, dates)
data/history/*.jsonl   dated metric snapshots, appended weekly
                        {"date": "...", "metric": "...", "value": ...}
data/events/*.jsonl    dated events (releases, versions) for the
                        activity timeline
data/schema/           JSON Schema the outputs and people are validated
                        against

scripts/fetchers/      one module per metric/event source (GitHub,
                        Zenodo, NASA ADS, INSPIRE-HEP, Altmetric, PyPI)
scripts/fetch_metrics.py   runs the fetchers for every output, appends
                            history, merges events
scripts/validate_outputs.py   schema-validates data/outputs/*.yaml
scripts/validate_people.py    schema-validates data/people/*.yaml

src/                    Eleventy site (Nunjucks templates + D3) that
                        reads data/ and builds the dashboard
```

An output's `group_authors` field names which `data/people/` entries are
authors on it &mdash; the mechanism for highlighting group members on
large-collaboration papers (e.g. LVK) whose `authors` field is just the
collaboration name. See [CONTRIBUTING.md](CONTRIBUTING.md).

A scheduled GitHub Action (`.github/workflows/fetch-metrics.yml`) runs the
fetchers weekly and commits the new snapshots. A second workflow
(`.github/workflows/deploy.yml`) then rebuilds and deploys the site to
GitHub Pages. A third (`.github/workflows/validate.yml`) schema-validates
any pull request that touches `data/outputs/`.

**Adding a new output does not require touching any code** &mdash; see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Local development

```bash
npm install
npm run build      # build the static site into _site/
npm run serve      # build + serve with live reload

pip install -r requirements.txt
python scripts/validate_outputs.py       # schema-check data/outputs/*.yaml
python scripts/validate_people.py        # schema-check data/people/*.yaml
python scripts/fetch_metrics.py          # run all fetchers (needs network + tokens)
python scripts/fetch_metrics.py --only example-software   # just one output
```

Fetchers that need credentials read them from the environment:

| Variable | Used by |
|---|---|
| `GITHUB_TOKEN` | GitHub stats/releases (raises your rate limit; public repos work unauthenticated too) |
| `ADS_TOKEN` | NASA ADS citation counts &mdash; get one at https://ui.adsabs.harvard.edu/user/settings/token |
| `ALTMETRIC_EXPLORER_KEY` / `ALTMETRIC_EXPLORER_SECRET` | Altmetric &mdash; **Explorer** API credentials from https://www.altmetric.com/explorer/settings (institutional subscription; both required) |

INSPIRE-HEP, Zenodo, and PyPI downloads need no credentials.

### About the Altmetric fetcher

`scripts/fetchers/altmetric.py` uses the **Explorer API**, not the free
single-DOI Details Page API, since Explorer is what an institutional
subscription (key + secret) grants access to. Explorer is built around
bulk queries: on each run, every output with `altmetric` in its `sources`
has its DOI batched into one signed "identifier list" request, then one
`research_outputs` query fetches all of their metrics together (paginating
as needed) rather than one API call per output. Re-running with the same
set of outputs reuses the same identifier list (the endpoint is a
find-or-create keyed on exact DOI-list content); adding or removing a
tracked output changes that content and creates a new list, so you may
see old lists accumulate in your Explorer account's UI over time.

The exact attribute names read off each `research_outputs` row
(`score`, `cited_by_tweeters_count`, `doi`) are carried over from
Altmetric's Details Page API schema as a best guess, since the Explorer
response schema wasn't reachable while writing this. If metrics come back
empty once you have real credentials, add a quick `print(row)` in
`_load_cache` in that file to see the actual field names and adjust.

Set these as repository secrets (`Settings -> Secrets and variables ->
Actions`) so the scheduled workflow can use them.

## Enabling GitHub Pages

In the repository's `Settings -> Pages`, set **Source** to "GitHub
Actions". The `deploy.yml` workflow handles the rest on every push to
`main`.

## Design notes

- **History is append-only JSONL**, not a rewritten "current value" field,
  so the dashboard can chart evolution and the git history of `data/`
  doubles as an audit trail of every recorded snapshot.
- **Events are separate from metrics** so a release/version timeline can be
  built independently of numeric metrics (some outputs may have one but not
  the other).
- **The site build makes no network calls** &mdash; it only reads what's
  already committed under `data/`. All external API calls happen in the
  scheduled fetch job, keeping the deploy fast and reproducible.
