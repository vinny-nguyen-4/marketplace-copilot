"""Turn raw competitor reviews into structured customer insights."""
import pandas as pd

from modules.llm import ask_json, has_api_key, load_prompt

MAX_REVIEWS = 150          # keep prompts a reasonable size
MAX_CHARS_PER_REVIEW = 400


def analyze_reviews(reviews: pd.DataFrame, category: str) -> dict:
    """Return {top_complaints, top_praises, unmet_needs, summary, mode}."""
    if reviews.empty:
        return {"top_complaints": [], "top_praises": [], "unmet_needs": [], "summary": "No reviews found.", "mode": "none"}

    # Prioritize critical reviews: complaints are where the opportunities are.
    sample = reviews.sort_values("rating").head(MAX_REVIEWS)

    if not has_api_key():
        result = _offline_analysis(sample)
        result["mode"] = "offline"
        return result

    formatted = "\n".join(
        f"- [{int(r.rating)}★] {str(r.review_text)[:MAX_CHARS_PER_REVIEW]}" for r in sample.itertuples()
    )
    prompt = load_prompt("review_analysis", category=category, reviews=formatted)
    result = ask_json(prompt, max_tokens=2000)
    result["mode"] = "claude"
    return result


# ---------- offline fallback (keyword matching) ----------

THEMES = {
    "Stability / tipping": ["tip", "wobble", "wobbly", "stable", "sturdy", "light", "slides"],
    "Durability / breaks": ["broke", "snapped", "flimsy", "loose", "peeling", "cheap", "weak"],
    "Case compatibility": ["case", "otterbox", "thick"],
    "Height / angle": ["short", "height", "tall", "angle", "look down"],
    "Charging / cable access": ["charging", "cable", "charger", "port"],
    "Portability": ["portable", "fold", "bag", "carry", "pocket"],
    "Shipping / damage": ["shipping", "dent", "missing", "arrived"],
    "Build quality / look": ["premium", "aluminum", "looks nice", "solid"],
}


def _count_themes(texts: pd.Series) -> list[dict]:
    lowered = texts.str.lower()
    results = []
    for theme, keywords in THEMES.items():
        mask = lowered.apply(lambda t: any(k in t for k in keywords))
        if mask.any():
            results.append({"theme": theme, "frequency": int(mask.sum()), "example": texts[mask].iloc[0][:120]})
    return sorted(results, key=lambda x: x["frequency"], reverse=True)[:5]


def _offline_analysis(reviews: pd.DataFrame) -> dict:
    negative = reviews[reviews["rating"] <= 3]["review_text"].astype(str).reset_index(drop=True)
    positive = reviews[reviews["rating"] >= 4]["review_text"].astype(str).reset_index(drop=True)
    complaints = _count_themes(negative)
    return {
        "top_complaints": complaints,
        "top_praises": _count_themes(positive),
        "unmet_needs": [f"Solve: {c['theme'].lower()}" for c in complaints[:3]],
        "summary": "Offline keyword analysis (add an ANTHROPIC_API_KEY for Claude-powered insights).",
    }
