import re

import requests

from .base import metric_fetcher

_RECORD_RE = re.compile(r"zenodo\.(\d+)")


@metric_fetcher("zenodo")
def fetch(output):
    doi = output.get("links", {}).get("doi", "") or output.get("links", {}).get("zenodo", "")
    match = _RECORD_RE.search(doi)
    if not match:
        return {}
    record_id = match.group(1)
    r = requests.get(f"https://zenodo.org/api/records/{record_id}", timeout=30)
    r.raise_for_status()
    stats = r.json().get("stats", {})
    return {
        "zenodo_downloads": stats.get("downloads", 0),
        "zenodo_views": stats.get("views", 0),
    }
