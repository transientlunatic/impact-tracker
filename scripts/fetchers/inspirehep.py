import requests

from .base import metric_fetcher


@metric_fetcher("inspire_citations")
def fetch(output):
    recid = output.get("links", {}).get("inspire")
    if not recid:
        return {}
    r = requests.get(f"https://inspirehep.net/api/literature/{recid}", timeout=30)
    r.raise_for_status()
    metadata = r.json().get("metadata", {})
    return {"citations_inspire": metadata.get("citation_count", 0)}
