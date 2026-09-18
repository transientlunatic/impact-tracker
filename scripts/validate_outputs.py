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
OUTPUTS_GLOB = "data/outputs/*.yaml"


def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)

    ok = True
    seen_ids = {}

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
