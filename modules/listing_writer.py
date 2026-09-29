"""Generate optimized marketplace listings and supplier emails."""
import json
from collections import Counter

import pandas as pd

from modules.llm import ask_json, has_api_key, load_prompt

STYLE_RULES = {
    "amazon": "Title under 200 characters, brand first, no ALL CAPS, no promotional claims like 'best seller'. 5 bullets, each starting with a short capitalized benefit phrase.",
    "walmart": "Title 50-75 characters, format Brand + Product + Key Attribute. 3-10 key features, plain factual language.",
    "ebay": "Title max 80 characters packed with search keywords, no filler words. Short scannable bullets.",
}

LANGUAGES = {"None": "", "Simplified Chinese": "Simplified Chinese", "Malay": "Malay"}

STOPWORDS = {"for", "with", "and", "the", "phone", "compatible", "desk", "stand", "holder", "cell"}


def top_keywords(titles: pd.Series, n: int = 12) -> list[tuple[str, int]]:
    """Most common words across competitor titles (a quick SEO signal)."""
    words = []
    for title in titles.astype(str):
        for w in title.lower().replace(",", " ").split():
            w = w.strip("()-/")
            if len(w) > 2 and w not in STOPWORDS and not w.isdigit():
                words.append(w)
    return Counter(words).most_common(n)


def write_listing(product_description: str, competitors: pd.DataFrame, insights: dict, marketplace: str = "amazon") -> dict:
    marketplace = marketplace.lower()
    if not has_api_key():
        return _offline_listing(product_description, competitors, insights) | {"mode": "offline"}

    insight_text = json.dumps({k: insights.get(k) for k in ("top_complaints", "unmet_needs", "top_praises")}, indent=2)
    prompt = load_prompt(
        "listing_writer",
        marketplace=marketplace.title(),
        product_description=product_description,
        competitor_titles="\n".join(f"- {t}" for t in competitors["title"].head(15)),
        insights=insight_text,
        style_rules=STYLE_RULES.get(marketplace, STYLE_RULES["amazon"]),
    )
    return ask_json(prompt, max_tokens=2000) | {"mode": "claude"}


def write_vendor_email(product_description: str, unit_cost: float, target_cost: float,
                       quantity: int, goal: str, language: str = "None") -> dict:
    lang = LANGUAGES.get(language, "")
    if not has_api_key():
        body = (
            f"Hello,\n\nWe would like to place an order of {quantity} units of the following product: "
            f"{product_description}.\n\nOur current unit price is ${unit_cost:.2f}. To meet our margin target, "
            f"we are asking for a price of ${target_cost:.2f} per unit at this quantity.\n\n"
            "Please let us know if this is possible, and the expected production and shipping time.\n\nThank you."
        )
        return {"subject": "Price request for upcoming order", "body_english": body,
                "body_translated": "", "mode": "offline"}

    translation_instruction = (
        f"- Also provide a full translation of the body into {lang} in body_translated." if lang
        else "- No translation needed; set body_translated to an empty string."
    )
    prompt = load_prompt(
        "vendor_email",
        goal=goal,
        product_description=product_description,
        unit_cost=f"{unit_cost:.2f}",
        target_cost=f"{target_cost:.2f}",
        quantity=quantity,
        translation_instruction=translation_instruction,
    )
    return ask_json(prompt, max_tokens=2000) | {"mode": "claude"}


def _offline_listing(product_description: str, competitors: pd.DataFrame, insights: dict) -> dict:
    keywords = [w for w, _ in top_keywords(competitors["title"], 6)]
    complaints = [c["theme"] for c in insights.get("top_complaints", [])][:3]
    return {
        "title": f"{product_description.split(',')[0].strip().title()} - {' '.join(keywords[:4]).title()}",
        "bullets": [f"ADDRESSES: {c}" for c in complaints] + ["(Add an ANTHROPIC_API_KEY for Claude-written copy)"],
        "description": product_description,
        "search_keywords": keywords,
        "rationale": ["Offline template: keywords from competitor titles, bullets from top complaints."],
    }
