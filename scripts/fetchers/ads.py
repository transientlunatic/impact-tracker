import os

import requests

from .base import metric_fetcher


@metric_fetcher("ads_citations")
def fetch(output):
    bibcode = output.get("links", {}).get("ads")
    if not bibcode:
        return {}
    token = os.environ.get("ADS_TOKEN")
    if not token:
        raise RuntimeError("ADS_TOKEN is not set")
    r = requests.get(
        "https://api.adsabs.harvard.edu/v1/search/query",
        params={"q": f"bibcode:{bibcode}", "fl": "citation_count"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    docs = r.json().get("response", {}).get("docs", [])
    if not docs:
        return {}
    return {"citations_ads": docs[0].get("citation_count", 0)}
