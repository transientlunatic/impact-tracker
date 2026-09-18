import os

import requests

from .base import metric_fetcher


@metric_fetcher("altmetric")
def fetch(output):
    doi = output.get("links", {}).get("doi")
    if not doi:
        return {}
    key = os.environ.get("ALTMETRIC_KEY")
    params = {"key": key} if key else {}
    r = requests.get(f"https://api.altmetric.com/v1/doi/{doi}", params=params, timeout=30)
    if r.status_code == 404:
        # Altmetric has no record for this DOI yet.
        return {"altmetric_score": 0}
    r.raise_for_status()
    data = r.json()
    return {
        "altmetric_score": data.get("score", 0),
        "altmetric_cited_by_tweeters": data.get("cited_by_tweeters_count", 0),
    }
