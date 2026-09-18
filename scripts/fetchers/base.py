"""Fetcher registries.

Two kinds of fetcher, selected per-output by the `sources` list in its YAML file:

- metric fetchers return {metric_name: numeric_value}, appended as dated rows
  to data/history/<id>.jsonl.
- event fetchers return a list of {date, kind, label, url} dicts, merged into
  data/events/<id>.yaml (deduplicated by url) to build the activity timeline.
"""

METRIC_FETCHERS = {}
EVENT_FETCHERS = {}


def metric_fetcher(source_name):
    def decorator(fn):
        METRIC_FETCHERS[source_name] = fn
        return fn

    return decorator


def event_fetcher(source_name):
    def decorator(fn):
        EVENT_FETCHERS[source_name] = fn
        return fn

    return decorator
