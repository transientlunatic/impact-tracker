# Contributing a research output

Add a new software project, publication, or dataset by opening a pull
request that adds one YAML file. No code changes needed.

## The fast way: let the tool fill it in

Instead of writing the YAML by hand, give `scripts/add_output.py` an
identifier and it does the lookup for you:

```bash
pip install -r requirements.txt

python scripts/add_output.py publication --doi 10.1103/PhysRevLett.116.061102
python scripts/add_output.py publication --inspire 1421100
python scripts/add_output.py publication --ads 2016PhRvL.116f1102A

python scripts/add_output.py software --repo https://github.com/bilby-dev/bilby

python scripts/add_output.py dataset --zenodo 10.5281/zenodo.7654321
```

It pulls title/authors/date/journal/etc. from INSPIRE-HEP, NASA ADS,
Zenodo, or GitHub as appropriate, derives the `id`/filename from the title
(override with `--id`), auto-fills `sources` based on which links it has,
and runs the same schema check CI does before writing anything. If a
lookup fails or comes back incomplete, it still writes the file but exits
with a non-zero status and prints exactly which fields need to be filled
in by hand (search the file for `TODO`) — it's a starting point, not a
guarantee, so read the result before opening a pull request. Won't
overwrite an existing file unless you pass `--force`.

For a publication with a very large author list (e.g. a LIGO/Virgo/KAGRA
collaboration paper), it uses the collaboration name as the single author
entry when INSPIRE reports one, rather than dumping hundreds of names into
the YAML.

## Writing the file by hand

Create `data/outputs/<your-slug>.yaml`, where `<your-slug>` is a short,
url-safe id (lowercase letters, digits, hyphens) that also becomes the
file's `id` field and the site's `/outputs/<your-slug>/` URL.

**The filename must end in `.yaml`.** A file with no extension, or the
wrong one, is silently invisible to both the site build and the local
validator (though `validate_outputs.py` will now flag a stray file in
`data/outputs/` that doesn't match `*.yaml`, so a pull request will catch
it even if you don't run it locally first).

Pick the template closest to what you're adding:

**Software**
```yaml
id: your-slug
type: software
title: "Your Software Name"
description: "One or two sentences about what it does."
authors:
  - "Last, F."
created: "2023-01-15"        # date of first commit/release - always quoted
tags: [gravitational-waves, bayesian]
links:
  repo: https://github.com/org/repo
  doi: 10.5281/zenodo.XXXXXXX   # optional, if it has a Zenodo concept DOI
  pypi: your-package-name        # optional
sources:
  - github_stats
  - github_releases
  - zenodo          # only if links.doi is a Zenodo DOI
  - pypi_downloads  # only if links.pypi is set
software:
  language: Python
  license: MIT
```

**Publication**
```yaml
id: your-slug
type: publication
title: "Your Paper Title"
authors:
  - "Last, F."
created: "2023-01-15"     # submission or first-posted date
links:
  doi: 10.1000/your.doi
  ads: 2023ApJ...000....1A     # ADS bibcode, if you have one
  inspire: "1234567"           # INSPIRE-HEP literature record id, if in HEP
sources:
  - ads_citations       # needs links.ads
  - inspire_citations   # needs links.inspire
  - altmetric           # needs links.doi
publication:
  journal: "Journal Name"
  arxiv: "2301.00000"
  year: 2023
```

**Dataset**
```yaml
id: your-slug
type: dataset
title: "Your Dataset Name"
authors:
  - "Last, F."
created: "2023-01-15"
links:
  doi: 10.5281/zenodo.XXXXXXX
sources:
  - zenodo
  - altmetric
dataset:
  format: HDF5
  size: "1.2 GB"
  repository: Zenodo
```

Only list a `sources` entry if the corresponding `links.*` field is set
&mdash; the fetcher will otherwise have nothing to look up. See the full
field reference in `data/schema/output.schema.json`.

**Important:** dates must be quoted strings (`"2023-01-15"`), not bare
YAML dates, or the schema check will fail.

## Validate locally (optional but recommended)

```bash
pip install -r requirements.txt
python scripts/validate_outputs.py
```

## Open a pull request

A GitHub Action schema-validates your file automatically and will comment
with specific errors if something's missing or malformed. Once merged, the
next scheduled run (weekly) will fetch its first metrics and it will show
up on the dashboard.

## Removing or renaming an output

Delete `data/outputs/<slug>.yaml`. Its history (`data/history/<slug>.jsonl`)
and events (`data/events/<slug>.jsonl`) are left in place unless you delete
them too &mdash; the site simply stops listing an output once its YAML file
is gone.
