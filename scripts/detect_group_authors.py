#!/usr/bin/env python3
"""Suggest group_authors for outputs already in data/outputs/*.yaml.

For every output with a links.inspire or links.ads, fetches the *full*
author list from that record (INSPIRE and ADS both keep the complete list
with per-author ORCID/INSPIRE BAI even for a collaboration paper whose
`authors` field we've collapsed to the collaboration name) and matches it
against data/people/*.yaml.

This is a suggestion tool, not a writer: it never edits data/outputs/*.yaml.
An ORCID or INSPIRE BAI match is high-confidence; a name-only match is not
(common names collide) and is always printed as 'unconfirmed' for a human
to check before adding it.

Examples:
  python scripts/detect_group_authors.py
  python scripts/detect_group_authors.py --only gw150914-discovery
"""
import argparse
import glob
import os
import sys

import yaml

import add_output
import people_match

OUTPUTS_GLOB = "data/outputs/*.yaml"


def scan_output(path, people):
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not doc:
        return None

    already = {e["id"] for e in doc.get("group_authors") or [] if isinstance(e, dict)}
    links = doc.get("links") or {}

    identities = []
    if links.get("inspire"):
        metadata = add_output.fetch_inspire(recid=links["inspire"])
        if metadata:
            identities += people_match.inspire_identities(metadata)
    if links.get("ads"):
        ads_doc = add_output.fetch_ads(links["ads"])
        if ads_doc:
            identities += people_match.ads_identities(ads_doc)

    if not identities:
        return None
    return people_match.match_people(identities, people, already)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="only check this output's id, instead of every output")
    args = parser.parse_args()

    people = people_match.load_people()
    if not people:
        print("data/people/*.yaml is empty - nothing to match against.", file=sys.stderr)
        return

    paths = sorted(glob.glob(OUTPUTS_GLOB))
    if args.only:
        paths = [p for p in paths if os.path.splitext(os.path.basename(p))[0] == args.only]
        if not paths:
            print(f"error: no output with id {args.only!r}", file=sys.stderr)
            sys.exit(1)

    found_any = False
    for path in paths:
        matches = scan_output(path, people)
        if not matches:
            continue
        found_any = True
        output_id = os.path.splitext(os.path.basename(path))[0]
        print(f"\n{output_id}:")
        for person_id, confidence, matched_name in matches:
            print(f"  - id: {person_id}   # {confidence} match on {matched_name!r}")

    if not found_any:
        print("No new group-author matches found.")
    else:
        print(
            "\nThese are suggestions, not written automatically - copy the ones you want\n"
            "into each output's group_authors (add CRediT roles/detail by hand), and check\n"
            "any 'name (unconfirmed)' match carefully (common names can collide)."
        )


if __name__ == "__main__":
    main()
