import requests

from .base import metric_fetcher


@metric_fetcher("pypi_downloads")
def fetch(output):
    package = output.get("links", {}).get("pypi")
    if not package:
        return {}
    r = requests.get(f"https://pypistats.org/api/packages/{package}/recent", timeout=30)
    r.raise_for_status()
    data = r.json().get("data", {})
    return {"pypi_downloads_month": data.get("last_month", 0)}
