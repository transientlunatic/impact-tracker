#!/usr/bin/env python3
"""Scaffold a new data/outputs/<id>.yaml from an external identifier.

Examples:
  python scripts/add_output.py publication --doi 10.1103/PhysRevLett.116.061102
  python scripts/add_output.py publication --inspire 1421100
  python scripts/add_output.py publication --ads 2016PhRvL.116f1102A
  python scripts/add_output.py publication --inspire 1421100 --group-authors jane-smith,john-doe
  python scripts/add_output.py publication --inspire 1421100 --detect-group-authors
  python scripts/add_output.py software --repo https://github.com/bilby-dev/bilby
  python scripts/add_output.py dataset --zenodo 10.5281/zenodo.7654321

This fills in what it can from public APIs (INSPIRE-HEP, NASA ADS, Zenodo,
GitHub) and writes the YAML file, but it is a starting point, not a
guarantee - always read the result before opening a pull request. It will
not overwrite an existing file unless --force is given, and it runs the
same schema check as CI before writing, printing anything still missing.
"""
import argparse
import glob
import json
import os
import re
import sys

import requests
import yaml
from jsonschema import Draft7Validator

import people_match

OUTPUTS_DIR = "data/outputs"
SCHEMA_PATH = "data/schema/output.schema.json"

FIELD_ORDER = [
    "id", "type", "title", "description", "authors", "group_authors", "created",
    "tags", "links", "sources", "software", "publication", "dataset",
]


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def ordered_dump(record):
    ordered = {k: record[k] for k in FIELD_ORDER if k in record}
    return yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=100)


def validate_record(record):
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    return sorted(validator.iter_errors(record), key=lambda e: list(e.path))


def known_person_ids():
    return {p["id"] for p in people_match.load_people()}


def parse_group_authors(raw):
    """--group-authors is a comma-separated list of data/people/<id>.yaml
    ids. Warn (but don't fail) on an id with no matching person file, since
    the person record might be added in the same pull request. Written out
    as {id: ...} entries with no `roles`/`detail` - CRediT roles are for a
    human to fill in by hand, not to guess."""
    if not raw:
        return []
    ids = [p.strip() for p in raw.split(",") if p.strip()]
    known = known_person_ids()
    for person_id in ids:
        if person_id not in known:
            print(f"warning: group author {person_id!r} has no data/people/{person_id}.yaml (yet)", file=sys.stderr)
    return [{"id": person_id} for person_id in ids]


def find_todos(value, path=""):
    """A placeholder like 'TODO: title' is a valid non-empty string, so the
    schema validator alone won't catch it (draft7 format assertions aren't
    enforced without an explicit FormatChecker). Walk the record separately
    for anything a failed lookup left unfilled."""
    todos = []
    if isinstance(value, dict):
        for key, sub in value.items():
            todos += find_todos(sub, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            todos += find_todos(sub, f"{path}[{i}]")
    elif isinstance(value, str) and "TODO" in value:
        todos.append((path, value))
    return todos


def write_output(output_id, record, force):
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    path = os.path.join(OUTPUTS_DIR, f"{output_id}.yaml")
    if os.path.exists(path) and not force:
        print(f"error: {path} already exists (pass --force to overwrite)", file=sys.stderr)
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(ordered_dump(record))

    errors = validate_record(record)
    todos = find_todos(record)
    if errors or todos:
        print(f"Wrote {path}, but it still needs attention before it's ready:")
        for error in errors:
            location = ".".join(str(p) for p in error.path) or "(root)"
            print(f"  - {location}: {error.message}")
        for location, value in todos:
            print(f"  - {location}: not filled in automatically ({value!r}) - edit by hand")
        sys.exit(1)

    print(f"Wrote {path} - schema-valid and fully populated. Review it, then open a pull request.")


# --- INSPIRE-HEP -------------------------------------------------------
# https://github.com/inspirehep/rest-api-doc

INSPIRE_API = "https://inspirehep.net/api"


def fetch_inspire(recid=None, doi=None, arxiv=None):
    for path in filter(None, [
        f"literature/{recid}" if recid else None,
        f"doi/{doi}" if doi else None,
        f"arxiv/{arxiv}" if arxiv else None,
    ]):
        try:
            r = requests.get(f"{INSPIRE_API}/{path}", timeout=30)
            if r.status_code == 404:
                continue
            r.raise_for_status()
            return r.json().get("metadata")
        except requests.RequestException as exc:
            print(f"warning: INSPIRE lookup via {path} failed: {exc}", file=sys.stderr)
    return None


def _normalize_date(value):
    if not value:
        return None
    parts = value.split("-")
    parts += ["01"] * (3 - len(parts))
    return "-".join(parts)


def _inspire_authors(metadata):
    collaborations = metadata.get("collaborations") or []
    if collaborations:
        return [" and ".join(c["value"] for c in collaborations)]

    authors = metadata.get("authors") or []
    names = [a["full_name"] for a in authors if a.get("full_name")]
    author_count = metadata.get("author_count", len(names))
    if not names:
        return []
    if author_count > len(names) or len(names) > 10:
        return names[:10] + ["et al."]
    return names


def parse_inspire(metadata):
    fields = {}
    titles = metadata.get("titles") or []
    if titles:
        fields["title"] = titles[0]["title"]

    authors = _inspire_authors(metadata)
    if authors:
        fields["authors"] = authors

    created = _normalize_date(metadata.get("earliest_date"))
    if created:
        fields["created"] = created

    dois = metadata.get("dois") or []
    if dois:
        fields["doi"] = dois[0]["value"]

    arxiv_eprints = metadata.get("arxiv_eprints") or []
    if arxiv_eprints:
        fields["arxiv"] = arxiv_eprints[0]["value"]
        fields["tags"] = arxiv_eprints[0].get("categories", [])

    for identifier in metadata.get("external_system_identifiers") or []:
        if identifier.get("schema", "").upper() == "ADS":
            fields["ads"] = identifier["value"]

    pub_info = metadata.get("publication_info") or []
    if pub_info:
        journal = pub_info[0].get("journal_title")
        if journal:
            fields["journal"] = journal
        year = pub_info[0].get("year")
        if year:
            fields["year"] = year

    control_number = metadata.get("control_number")
    if control_number:
        fields["inspire"] = str(control_number)

    return fields


# --- NASA ADS ------------------------------------------------------------

def fetch_ads(bibcode):
    token = os.environ.get("ADS_TOKEN")
    if not token:
        print("warning: ADS_TOKEN not set, skipping ADS lookup", file=sys.stderr)
        return None
    try:
        r = requests.get(
            "https://api.adsabs.harvard.edu/v1/search/query",
            params={"q": f"bibcode:{bibcode}", "fl": "title,author,doi,pubdate,year,orcid_pub"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        return docs[0] if docs else None
    except requests.RequestException as exc:
        print(f"warning: ADS lookup failed: {exc}", file=sys.stderr)
        return None


def parse_ads(doc):
    fields = {}
    if doc.get("title"):
        fields["title"] = doc["title"][0]
    authors = doc.get("author") or []
    if authors:
        fields["authors"] = authors[:10] + (["et al."] if len(authors) > 10 else [])
    if doc.get("doi"):
        fields["doi"] = doc["doi"][0]
    pubdate = doc.get("pubdate")  # "YYYY-MM-00" style
    if pubdate:
        fields["created"] = _normalize_date(pubdate.replace("-00", "-01"))
    if doc.get("year"):
        fields["year"] = int(doc["year"])
    return fields


def cmd_publication(args):
    inspire_meta = None
    if args.inspire or args.doi or args.arxiv:
        inspire_meta = fetch_inspire(recid=args.inspire, doi=args.doi, arxiv=args.arxiv)
    fields = parse_inspire(inspire_meta) if inspire_meta else {}

    ads_doc = None
    if args.ads:
        fields.setdefault("ads", args.ads)
        ads_doc = fetch_ads(args.ads)
        if ads_doc:
            for key, value in parse_ads(ads_doc).items():
                fields.setdefault(key, value)

    # Explicit CLI identifiers always win over anything cross-referenced.
    if args.doi:
        fields["doi"] = args.doi
    if args.inspire:
        fields["inspire"] = args.inspire
    if args.ads:
        fields["ads"] = args.ads

    title = fields.get("title", "TODO: title")
    output_id = args.id or slugify(title) or "TODO-id"

    links = {k: v for k, v in fields.items() if k in ("doi", "ads", "inspire")}
    if fields.get("arxiv"):
        links["homepage"] = f"https://arxiv.org/abs/{fields['arxiv']}"

    sources = []
    if links.get("ads"):
        sources.append("ads_citations")
    if links.get("inspire"):
        sources.append("inspire_citations")
    if links.get("doi"):
        sources.append("altmetric")

    record = {
        "id": output_id,
        "type": "publication",
        "title": title,
        "authors": fields.get("authors") or ["TODO: authors"],
        "group_authors": parse_group_authors(args.group_authors) or None,
        "created": fields.get("created") or "TODO: YYYY-MM-DD",
        "tags": fields.get("tags", []),
        "links": links,
        "sources": sources,
        "publication": {
            k: v for k, v in {
                "journal": fields.get("journal"),
                "arxiv": fields.get("arxiv"),
                "year": fields.get("year"),
            }.items() if v is not None
        } or None,
    }
    record = {k: v for k, v in record.items() if v is not None}

    if args.detect_group_authors:
        identities = []
        if inspire_meta:
            identities += people_match.inspire_identities(inspire_meta)
        if ads_doc:
            identities += people_match.ads_identities(ads_doc)
        if identities:
            already = {e["id"] for e in record.get("group_authors") or []}
            people_match.print_matches(people_match.match_people(identities, people_match.load_people(), already))
        else:
            print("No per-author identifiers to match against (no INSPIRE/ADS record found).")

    write_output(output_id, record, args.force)


# --- Zenodo ---------------------------------------------------------------

_ZENODO_RECORD_RE = re.compile(r"zenodo\.(\d+)")


def fetch_zenodo(identifier):
    match = _ZENODO_RECORD_RE.search(identifier)
    record_id = match.group(1) if match else identifier
    r = requests.get(f"https://zenodo.org/api/records/{record_id}", timeout=30)
    r.raise_for_status()
    return r.json()


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _human_size(total_bytes):
    size = float(total_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024


def cmd_dataset(args):
    record_json = fetch_zenodo(args.zenodo)
    metadata = record_json.get("metadata", {})

    title = metadata.get("title", "TODO: title")
    output_id = args.id or slugify(title) or "TODO-id"

    creators = metadata.get("creators") or []
    authors = [c["name"] for c in creators if c.get("name")] or ["TODO: authors"]

    files = record_json.get("files") or []
    size_by_extension = {}
    for f in files:
        key = f.get("key", "")
        if "." in key:
            ext = key.rsplit(".", 1)[-1].upper()
            size_by_extension[ext] = size_by_extension.get(ext, 0) + f.get("size", 0)
    # weight by total bytes, not file count - a 2 GB .h5 next to a 500-byte
    # README should pick H5, not tie on "one file each"
    fmt = max(size_by_extension, key=size_by_extension.get) if size_by_extension else "TODO: format"
    total_size = sum(f.get("size", 0) for f in files)

    doi = record_json.get("doi") or args.zenodo

    record = {
        "id": output_id,
        "type": "dataset",
        "title": title,
        "description": _strip_html(metadata.get("description", ""))[:500] or None,
        "authors": authors,
        "created": metadata.get("publication_date", "TODO: YYYY-MM-DD"),
        "tags": metadata.get("keywords", []),
        "links": {"doi": doi},
        "sources": ["zenodo", "altmetric"],
        "dataset": {
            "format": fmt,
            "size": _human_size(total_size) if total_size else "TODO: size",
            "repository": "Zenodo",
        },
    }
    record = {k: v for k, v in record.items() if v is not None}
    write_output(output_id, record, args.force)


# --- GitHub -----------------------------------------------------------

def _owner_repo(repo_url):
    parts = repo_url.rstrip("/").split("/")
    return parts[-2], parts[-1]


def _github_headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def cmd_software(args):
    owner, repo = _owner_repo(args.repo)
    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=_github_headers(), timeout=30)
    r.raise_for_status()
    repo_data = r.json()

    contributors = []
    try:
        cr = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/contributors",
            headers=_github_headers(),
            params={"per_page": 5},
            timeout=30,
        )
        cr.raise_for_status()
        contributors = [c["login"] for c in cr.json()]
    except requests.RequestException as exc:
        print(f"warning: could not fetch contributors: {exc}", file=sys.stderr)

    title = repo_data.get("name", repo)
    output_id = args.id or slugify(title)

    links = {"repo": repo_data.get("html_url", args.repo)}
    if repo_data.get("homepage"):
        links["homepage"] = repo_data["homepage"]
    if args.zenodo:
        links["doi"] = args.zenodo
    if args.pypi:
        links["pypi"] = args.pypi

    sources = ["github_stats", "github_releases"]
    if args.zenodo:
        sources.append("zenodo")
    if args.pypi:
        sources.append("pypi_downloads")

    record = {
        "id": output_id,
        "type": "software",
        "title": title,
        "description": repo_data.get("description") or None,
        "authors": contributors or [f"TODO: authors (top contributors: none found for {owner}/{repo})"],
        "created": repo_data.get("created_at", "TODO: YYYY-MM-DD")[:10],
        "tags": repo_data.get("topics", []),
        "links": links,
        "sources": sources,
        "software": {
            k: v for k, v in {
                "language": repo_data.get("language"),
                "license": (repo_data.get("license") or {}).get("spdx_id"),
            }.items() if v and v != "NOASSERTION"
        } or None,
    }
    record = {k: v for k, v in record.items() if v is not None}
    write_output(output_id, record, args.force)


def main():
    # --id/--force live on a shared parent parser so they work in the natural
    # position after the subcommand too (`... publication --doi X --id Y`),
    # not just before it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--id", help="override the auto-derived slug/id")
    common.add_argument("--force", action="store_true", help="overwrite an existing file")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[common]
    )
    subparsers = parser.add_subparsers(dest="type", required=True)

    pub = subparsers.add_parser("publication", parents=[common], help="enrich from ADS bibcode / INSPIRE recid / DOI")
    pub.add_argument("--doi")
    pub.add_argument("--arxiv")
    pub.add_argument("--inspire")
    pub.add_argument("--ads")
    pub.add_argument(
        "--group-authors",
        help="comma-separated data/people/<id>.yaml ids of group members who are authors "
        "(useful when --inspire collapses authors to a collaboration name)",
    )
    pub.add_argument(
        "--detect-group-authors",
        action="store_true",
        help="print possible group_authors matches against data/people/*.yaml, by ORCID/INSPIRE "
        "BAI (high confidence) or name (unconfirmed) - suggestions only, never written automatically",
    )

    software = subparsers.add_parser("software", parents=[common], help="enrich from a GitHub repo URL")
    software.add_argument("--repo", required=True)
    software.add_argument("--zenodo", help="Zenodo DOI, if this software has one")
    software.add_argument("--pypi", help="PyPI package name, if published there")

    dataset = subparsers.add_parser("dataset", parents=[common], help="enrich from a Zenodo DOI or record id")
    dataset.add_argument("--zenodo", required=True)

    args = parser.parse_args()

    if args.type == "publication":
        if not (args.doi or args.arxiv or args.inspire or args.ads):
            pub.error("give at least one of --doi, --arxiv, --inspire, --ads")
        cmd_publication(args)
    elif args.type == "software":
        cmd_software(args)
    elif args.type == "dataset":
        cmd_dataset(args)


if __name__ == "__main__":
    main()
