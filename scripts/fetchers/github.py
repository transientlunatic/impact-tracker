import os

import requests

from .base import event_fetcher, metric_fetcher

API = "https://api.github.com"


def _headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _owner_repo(output):
    repo_url = output.get("links", {}).get("repo", "")
    parts = repo_url.rstrip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"links.repo is not a valid GitHub URL: {repo_url!r}")
    return parts[-2], parts[-1]


@metric_fetcher("github_stats")
def fetch_stats(output):
    owner, repo = _owner_repo(output)
    r = requests.get(f"{API}/repos/{owner}/{repo}", headers=_headers(), timeout=30)
    r.raise_for_status()
    data = r.json()
    return {
        "github_stars": data.get("stargazers_count", 0),
        "github_forks": data.get("forks_count", 0),
        "github_open_issues": data.get("open_issues_count", 0),
    }


@event_fetcher("github_releases")
def fetch_releases(output):
    owner, repo = _owner_repo(output)
    r = requests.get(
        f"{API}/repos/{owner}/{repo}/releases",
        headers=_headers(),
        params={"per_page": 100},
        timeout=30,
    )
    r.raise_for_status()
    events = []
    for release in r.json():
        if release.get("draft"):
            continue
        date = (release.get("published_at") or release.get("created_at") or "")[:10]
        if not date:
            continue
        events.append(
            {
                "date": date,
                "kind": "release",
                "label": release.get("name") or release.get("tag_name"),
                "url": release.get("html_url"),
            }
        )
    return events
