"""Altmetric Explorer API (institutional bulk API).

Auth: every GET is signed with an HMAC-SHA1 digest of the *filter*
parameters, keyed by the account's API secret - see
https://www.altmetric.com/explorer/documentation/api#authentication
and the reference client this was ported from:
https://github.com/altmetric/altmetric-explorer-api-client

Explorer is built around querying "identifier lists" rather than one DOI
at a time, so this fetcher batches every output that lists `altmetric` as
a source into a single identifier list + a single `research_outputs`
query per run (via `_load_cache`, cached for the life of the process),
then serves each output's metrics from that cache.

NOTE ON FIELD NAMES: `score` / `cited_by_tweeters_count` / `doi` below are
carried over from the (documented) Details Page API response shape. The
Explorer `research_outputs` JSON:API response schema itself wasn't
reachable while writing this - run once with real credentials and inspect
a raw row (e.g. `print(row)` in `_load_cache`) to confirm the attribute
names, and adjust if they differ.
"""
import glob
import hashlib
import hmac
import os

import requests
import yaml

from .base import metric_fetcher

EXPLORER_API = "https://www.altmetric.com/explorer/api"

_cache = None  # {doi: {metric: value}}, populated once per process


def _digest(secret, message):
    return hmac.new(secret.encode("utf-8"), (message or "").encode("utf-8"), hashlib.sha1).hexdigest()


def _filters_message(filters):
    """The string that gets signed: filter args+values, sorted by arg name,
    pipe-joined. Mirrors Filters.message() in the reference client."""
    parts = []
    for arg, value in sorted(filters.items()):
        parts.append(arg)
        if isinstance(value, (list, tuple, set)):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return "|".join(parts)


def _filters_query(filters):
    parts = []
    for arg, value in filters.items():
        if isinstance(value, (list, tuple, set)):
            parts.extend(f"filter[{arg}][]={v}" for v in value)
        else:
            parts.append(f"filter[{arg}]={value}")
    return "&".join(parts)


def _get(api_key, api_secret, path, page_size=None, page_number=None, order=None, **filters):
    # page[size]/page[number]/filter[order] are NOT part of the signed
    # message - only filters are (see Query.add_params in the reference
    # client), so they're kept out of _filters_message.
    query_parts = []
    if page_size is not None:
        query_parts.append(f"page[size]={page_size}")
    if page_number is not None:
        query_parts.append(f"page[number]={page_number}")
    if order is not None:
        query_parts.append(f"filter[order]={order}")

    query_parts.append(f"key={api_key}")
    query_parts.append(f"digest={_digest(api_secret, _filters_message(filters))}")

    filter_query = _filters_query(filters)
    if filter_query:
        query_parts.append(filter_query)

    url = f"{EXPLORER_API}/{path}?" + "&".join(query_parts)
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def _create_identifier_list(api_key, api_secret, identifiers):
    # This endpoint is a "find or create": posting the same identifiers
    # (same order) returns the existing list rather than making a new one,
    # so running this weekly with an unchanged output set is idempotent.
    # Per the API docs it signs with the secret's hyphens stripped, unlike
    # every read endpoint above - do not "fix" this to match _get().
    payload = "\n".join(identifiers)
    body_secret = api_secret.replace("-", "")
    body = {
        "key": api_key,
        "digest": _digest(body_secret, payload),
        "identifiers": payload,
    }
    r = requests.post(f"{EXPLORER_API}/identifier_lists", data=body, timeout=30)
    r.raise_for_status()
    return r.json()["data"]["id"]


def _all_dois_using_altmetric():
    dois = []
    for path in sorted(glob.glob("data/outputs/*.yaml")):
        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        if "altmetric" in (doc.get("sources") or []):
            doi = doc.get("links", {}).get("doi")
            if doi:
                dois.append(doi)
    return dois


def _load_cache():
    global _cache
    if _cache is not None:
        return _cache

    api_key = os.environ.get("ALTMETRIC_EXPLORER_KEY")
    api_secret = os.environ.get("ALTMETRIC_EXPLORER_SECRET")
    if not api_key or not api_secret:
        raise RuntimeError("ALTMETRIC_EXPLORER_KEY / ALTMETRIC_EXPLORER_SECRET not set")

    dois = _all_dois_using_altmetric()
    _cache = {}
    if not dois:
        return _cache

    list_id = _create_identifier_list(api_key, api_secret, dois)
    body = _get(api_key, api_secret, "research_outputs", page_size=100, identifier_list_id=list_id)

    while True:
        for row in body.get("data", []):
            attrs = row.get("attributes", row)
            doi = attrs.get("doi")
            if not doi:
                continue
            _cache[doi] = {
                "altmetric_score": attrs.get("score", 0),
                "altmetric_cited_by_tweeters": attrs.get("cited_by_tweeters_count", 0),
            }
        next_url = body.get("links", {}).get("next")
        if not next_url:
            break
        r = requests.get(next_url, timeout=30)
        r.raise_for_status()
        body = r.json()

    return _cache


@metric_fetcher("altmetric")
def fetch(output):
    doi = output.get("links", {}).get("doi")
    if not doi:
        return {}
    return _load_cache().get(doi, {})
