"""Fetch competitor listings and reviews.

Two sources:
  - "sample":     bundled CSVs in data/sample (free, offline, great for demos)
  - "rainforest": live Amazon data via Rainforest API (needs RAINFOREST_API_KEY)

Both return the same shape, so the rest of the pipeline doesn't care which is used.
"""
import os
from pathlib import Path

import pandas as pd
import requests

import db

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
LISTING_COLUMNS = ["asin", "marketplace", "title", "brand", "price", "rating", "review_count", "bullets"]


def fetch_competitors(query: str, source: str = "sample", max_results: int = 20) -> pd.DataFrame:
    if source == "sample":
        return _sample_listings(query, max_results)
    if source == "rainforest":
        return _rainforest_listings(query, max_results)
    raise ValueError(f"Unknown source: {source}")


def fetch_reviews(asins: list[str], source: str = "sample", per_product: int = 10) -> pd.DataFrame:
    if source == "sample":
        reviews = pd.read_csv(SAMPLE_DIR / "reviews.csv")
        reviews = reviews[reviews["asin"].isin(asins)]
        return reviews.groupby("asin").head(per_product).reset_index(drop=True)
    if source == "rainforest":
        frames = [_rainforest_reviews(asin, per_product) for asin in asins]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["asin", "rating", "review_text"])
    raise ValueError(f"Unknown source: {source}")


# ---------- sample data ----------

def _sample_listings(query: str, max_results: int) -> pd.DataFrame:
    df = pd.read_csv(SAMPLE_DIR / "listings.csv")
    # Simple relevance: rank by how many query words appear in the title.
    words = [w.lower() for w in query.split() if len(w) > 2]
    if words:
        df["relevance"] = df["title"].str.lower().apply(lambda t: sum(w in t for w in words))
        df = df.sort_values(["relevance", "review_count"], ascending=False).drop(columns="relevance")
    return df.head(max_results).reset_index(drop=True)


# ---------- Rainforest API (live Amazon data) ----------

RAINFOREST_URL = "https://api.rainforestapi.com/request"


def _rainforest_get(params: dict) -> dict:
    api_key = os.getenv("RAINFOREST_API_KEY")
    if not api_key:
        raise RuntimeError("RAINFOREST_API_KEY is not set. Use source='sample' or add the key to .env")

    cache_key = "rainforest:" + "|".join(f"{k}={v}" for k, v in sorted(params.items()))
    cached = db.cache_get(cache_key)
    if cached is not None:
        return cached

    resp = requests.get(RAINFOREST_URL, params={"api_key": api_key, **params}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    db.cache_set(cache_key, data)
    return data


def _rainforest_listings(query: str, max_results: int) -> pd.DataFrame:
    data = _rainforest_get({"type": "search", "amazon_domain": "amazon.com", "search_term": query})
    rows = []
    for item in data.get("search_results", [])[:max_results]:
        price = (item.get("price") or {}).get("value")
        if price is None:
            continue
        rows.append(
            {
                "asin": item.get("asin"),
                "marketplace": "amazon",
                "title": item.get("title", ""),
                "brand": item.get("brand", ""),
                "price": float(price),
                "rating": item.get("rating"),
                "review_count": item.get("ratings_total", 0),
                "bullets": "",
            }
        )
    return pd.DataFrame(rows, columns=LISTING_COLUMNS)


def _rainforest_reviews(asin: str, per_product: int) -> pd.DataFrame:
    data = _rainforest_get({"type": "reviews", "amazon_domain": "amazon.com", "asin": asin})
    rows = [
        {"asin": asin, "rating": r.get("rating"), "review_text": r.get("body", "")}
        for r in data.get("reviews", [])[:per_product]
    ]
    return pd.DataFrame(rows, columns=["asin", "rating", "review_text"])
