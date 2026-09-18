#!/usr/bin/env python3
"""Run configured fetchers for every research output and record the results.

Metric snapshots are appended to data/history/<id>.jsonl (one JSON object per
line: {"date": ..., "metric": ..., "value": ...}) so the dashboard can chart
evolution over time. Event fetchers (e.g. GitHub releases) are merged into
data/events/<id>.yaml, deduplicated by url, to build the activity timeline.

Best-effort by design: a fetcher failing for one output/source (missing
token, network hiccup, no DOI yet) is logged and skipped rather than failing
the whole run, since this is meant to run unattended on a schedule.
"""
import argparse
import datetime
import glob
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from fetchers import EVENT_FETCHERS, METRIC_FETCHERS  # noqa: E402

OUTPUTS_DIR = "data/outputs"
HISTORY_DIR = "data/history"
EVENTS_DIR = "data/events"


def load_output(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def append_history(output_id, metrics, date):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{output_id}.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        for metric, value in metrics.items():
            f.write(json.dumps({"date": date, "metric": metric, "value": value}) + "\n")


def merge_events(output_id, new_events):
    os.makedirs(EVENTS_DIR, exist_ok=True)
    path = os.path.join(EVENTS_DIR, f"{output_id}.jsonl")
    existing = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = [json.loads(line) for line in f if line.strip()]
    seen_urls = {e.get("url") for e in existing if e.get("url")}
    merged = existing + [e for e in new_events if e.get("url") not in seen_urls]
    merged.sort(key=lambda e: e.get("date", ""))
    with open(path, "w", encoding="utf-8") as f:
        for event in merged:
            f.write(json.dumps(event) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Only process the output with this id")
    args = parser.parse_args()

    date = datetime.date.today().isoformat()

    for path in sorted(glob.glob(os.path.join(OUTPUTS_DIR, "*.yaml"))):
        output = load_output(path)
        output_id = output["id"]
        if args.only and output_id != args.only:
            continue

        metrics = {}
        events = []
        for source in output.get("sources", []):
            try:
                if source in METRIC_FETCHERS:
                    metrics.update(METRIC_FETCHERS[source](output))
                elif source in EVENT_FETCHERS:
                    events.extend(EVENT_FETCHERS[source](output))
                else:
                    print(f"[{output_id}] unknown source {source!r}, skipping")
            except Exception as exc:  # noqa: BLE001 - best effort, keep going
                print(f"[{output_id}] source {source!r} failed: {exc}")

        if metrics:
            append_history(output_id, metrics, date)
            print(f"[{output_id}] recorded {len(metrics)} metric(s): {sorted(metrics)}")
        if events:
            merge_events(output_id, events)
            print(f"[{output_id}] merged {len(events)} event(s)")


if __name__ == "__main__":
    main()
