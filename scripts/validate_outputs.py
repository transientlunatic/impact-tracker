#!/usr/bin/env python3
"""Validate every data/outputs/*.yaml file against the JSON Schema.

Used as a CI gate on pull requests that touch data/outputs/** so a
contributor adding a new research output gets fast, specific feedback.
"""
import glob
import json
import os
import sys

import yaml
from jsonschema import Draft7Validator

SCHEMA_PATH = "data/schema/output.schema.json"
OUTPUTS_DIR = "data/outputs"
OUTPUTS_GLOB = f"{OUTPUTS_DIR}/*.yaml"
PEOPLE_GLOB = "data/people/*.yaml"


def known_person_ids():
    """IDs of every data/people/*.yaml, so group_authors can be checked for
    typos/removed people. Empty (not an error) if data/people/ has no files
    yet - person records are optional."""
    ids = set()
    for path in glob.glob(PEOPLE_GLOB):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        if doc.get("id"):
            ids.add(doc["id"])
    return ids


def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)
    people_ids = known_person_ids()

    ok = True
    seen_ids = {}

    # A file that doesn't end in .yaml is invisible to this glob (and to the
    # site build's own glob) and would otherwise fail silently - nobody sees
    # an error and the output just never appears anywhere. Catch that here.
    all_files = {f for f in glob.glob(f"{OUTPUTS_DIR}/*") if os.path.isfile(f)}
    yaml_files = set(glob.glob(OUTPUTS_GLOB))
    for path in sorted(all_files - yaml_files):
        print(f"::error file={path}::file name must end in .yaml or it will be silently ignored")
        ok = False

    for path in sorted(glob.glob(OUTPUTS_GLOB)):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        if doc is None:
            print(f"::error file={path}::File is empty")
            ok = False
            continue

        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        for error in errors:
            location = ".".join(str(p) for p in error.path) or "(root)"
            print(f"::error file={path}::{location}: {error.message}")
            ok = False

        for person_id in doc.get("group_authors") or []:
            if person_id not in people_ids:
                print(
                    f"::error file={path}::group_authors references "
                    f"{person_id!r}, which has no data/people/{person_id}.yaml"
                )
                ok = False

        output_id = doc.get("id")
        base_name = os.path.splitext(os.path.basename(path))[0]
        if output_id and output_id != base_name:
            print(
                f"::error file={path}::id {output_id!r} does not match "
                f"filename {base_name!r}"
            )
            ok = False

        if output_id in seen_ids:
            print(
                f"::error file={path}::duplicate id {output_id!r} "
                f"(already used in {seen_ids[output_id]})"
            )
            ok = False
        elif output_id:
            seen_ids[output_id] = path

    if not ok:
        sys.exit(1)
    print(f"Validated {len(seen_ids)} output(s) OK.")


if __name__ == "__main__":
    main()
