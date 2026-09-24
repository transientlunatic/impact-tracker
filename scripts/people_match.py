"""Shared helpers for matching data/people/*.yaml against the per-author
identities (ORCID / INSPIRE BAI) in an INSPIRE-HEP or NASA ADS record.

An ORCID or INSPIRE BAI match is high-confidence: those ids are specific
to one person. Matching by name alone is not - "Smith, J." collides across
authors - so every caller must show a name-only match to a human as
'unconfirmed' rather than writing it silently. Used by both
add_output.py (--detect-group-authors, for a new output) and
detect_group_authors.py (for scanning outputs already in the repo).
"""
import glob

import yaml

PEOPLE_GLOB = "data/people/*.yaml"


def load_people():
    people = []
    for path in glob.glob(PEOPLE_GLOB):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        if doc.get("id"):
            people.append(doc)
    return people


def name_key(name):
    """('smith', 'j') from either 'Smith, Jane A.' (INSPIRE/ADS style) or
    'Jane Smith' (our data/people/*.yaml style) - enough to bridge that
    formatting difference, not to tell apart two people who share both a
    surname and a first initial."""
    name = (name or "").strip()
    if not name:
        return None
    if "," in name:
        last, rest = name.split(",", 1)
    else:
        parts = name.split()
        if len(parts) < 2:
            return (parts[0].lower(), "") if parts else None
        last, rest = parts[-1], " ".join(parts[:-1])
    rest = rest.strip()
    return (last.strip().lower(), rest[:1].lower() if rest else "")


def inspire_identities(metadata):
    """[{full_name, orcid, bai}, ...] from a *full* (uncollapsed) INSPIRE
    authors list - the same record scripts/add_output.py collapses to a
    single collaboration-name entry when the author list is very large."""
    identities = []
    for author in metadata.get("authors") or []:
        orcid = bai = None
        for ident in author.get("ids") or []:
            schema = (ident.get("schema") or "").upper()
            if schema == "ORCID":
                orcid = ident.get("value")
            elif schema == "INSPIRE BAI":
                bai = ident.get("value")
        identities.append({"full_name": author.get("full_name", ""), "orcid": orcid, "bai": bai})
    return identities


def ads_identities(doc):
    """[{full_name, orcid, bai}, ...] from an ADS search doc fetched with
    `orcid_pub` in its `fl` param (see add_output.fetch_ads) - `orcid_pub`
    is positionally aligned with `author`, with '-' for an unknown ORCID."""
    authors = doc.get("author") or []
    orcids = doc.get("orcid_pub") or []
    identities = []
    for i, name in enumerate(authors):
        orcid = orcids[i] if i < len(orcids) and orcids[i] not in ("-", "", None) else None
        identities.append({"full_name": name, "orcid": orcid, "bai": None})
    return identities


def match_people(identities, people, exclude_ids=()):
    """For each candidate person not already in `exclude_ids`, look for an
    ORCID or INSPIRE BAI match first, falling back to a same-surname-and-
    initial name match flagged 'unconfirmed'. Returns
    [(person_id, confidence, matched_full_name), ...]."""
    matches = []
    for person in people:
        if person["id"] in exclude_ids:
            continue
        person_orcid = (person.get("orcid") or "").strip().upper()
        person_bai = (person.get("links") or {}).get("inspire")
        person_key = name_key(person.get("name", ""))

        found = None
        for identity in identities:
            if person_orcid and identity["orcid"] and identity["orcid"].strip().upper() == person_orcid:
                found = ("orcid", identity["full_name"])
                break
            if person_bai and identity["bai"] and identity["bai"] == person_bai:
                found = ("inspire-bai", identity["full_name"])
                break
        if not found and person_key:
            for identity in identities:
                if identity["full_name"] and name_key(identity["full_name"]) == person_key:
                    found = ("name (unconfirmed)", identity["full_name"])
                    break
        if found:
            matches.append((person["id"], found[0], found[1]))
    return matches


def print_matches(matches):
    if not matches:
        print("No group-author matches found against data/people/*.yaml.")
        return
    print("Possible group authors (not added automatically - confirm, then add to")
    print("group_authors by hand with any CRediT roles/detail):")
    for person_id, confidence, matched_name in matches:
        print(f"  - id: {person_id}   # {confidence} match on {matched_name!r}")
