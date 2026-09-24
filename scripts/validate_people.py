#!/usr/bin/env python3
"""Validate every data/people/*.yaml file against the JSON Schema.

Used as a CI gate on pull requests that touch data/people/** so a
contributor adding or updating a group member gets fast, specific
feedback. Mirrors scripts/validate_outputs.py.
"""
import glob
import json
import os
import sys

import yaml
from jsonschema import Draft7Validator

SCHEMA_PATH = "data/schema/person.schema.json"
PEOPLE_DIR = "data/people"
PEOPLE_GLOB = f"{PEOPLE_DIR}/*.yaml"


def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)

    ok = True
    seen_ids = {}

    all_files = {f for f in glob.glob(f"{PEOPLE_DIR}/*") if os.path.isfile(f)}
    yaml_files = set(glob.glob(PEOPLE_GLOB))
    for path in sorted(all_files - yaml_files):
        print(f"::error file={path}::file name must end in .yaml or it will be silently ignored")
        ok = False

    for path in sorted(glob.glob(PEOPLE_GLOB)):
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

        person_id = doc.get("id")
        base_name = os.path.splitext(os.path.basename(path))[0]
        if person_id and person_id != base_name:
            print(
                f"::error file={path}::id {person_id!r} does not match "
                f"filename {base_name!r}"
            )
            ok = False

        if person_id in seen_ids:
            print(
                f"::error file={path}::duplicate id {person_id!r} "
                f"(already used in {seen_ids[person_id]})"
            )
            ok = False
        elif person_id:
            seen_ids[person_id] = path

        if doc.get("status") == "former" and not doc.get("left"):
            print(f"::error file={path}::status is 'former' but 'left' date is not set")
            ok = False
        if doc.get("status") == "current" and doc.get("left"):
            print(f"::error file={path}::status is 'current' but a 'left' date is set")
            ok = False

    if not ok:
        sys.exit(1)
    print(f"Validated {len(seen_ids)} group member(s) OK.")


if __name__ == "__main__":
    main()
