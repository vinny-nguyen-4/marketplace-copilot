"""Orchestrator: runs every step in order and returns one result dict."""
from dataclasses import dataclass

import db
from modules import fetcher, listing_writer, pricing, review_analyzer


@dataclass
class ProductInput:
    search_query: str               # what a shopper would type, e.g. "adjustable phone stand"
    product_description: str        # what OUR product actually is (specs, materials, features)
    marketplace: str = "amazon"
    source: str = "sample"          # "sample" or "rainforest"
    costs: pricing.CostInputs | None = None


def run_pipeline(inp: ProductInput, progress=None) -> dict:
    def step(msg):
        if progress:
            progress(msg)

    step("Fetching competitor listings...")
    competitors = fetcher.fetch_competitors(inp.search_query, source=inp.source)
    if competitors.empty:
        raise RuntimeError("No competitor listings found. Try a broader search query.")

    step("Fetching competitor reviews...")
    reviews = fetcher.fetch_reviews(competitors["asin"].tolist(), source=inp.source)

    step("Analyzing reviews...")
    insights = review_analyzer.analyze_reviews(reviews, category=inp.search_query)

    step("Writing optimized listing...")
    listing = listing_writer.write_listing(inp.product_description, competitors, insights, inp.marketplace)

    pricing_result, scenarios = None, None
    if inp.costs:
        step("Running pricing model...")
        pricing_result = pricing.recommend_price(inp.costs, competitors["price"])
        scenarios = pricing.scenario_table(inp.costs, competitors["price"])

    result = {
        "competitors": competitors,
        "reviews": reviews,
        "keywords": listing_writer.top_keywords(competitors["title"]),
        "insights": insights,
        "listing": listing,
        "pricing": pricing_result,
        "scenarios": scenarios,
    }

    db.save_run(inp.search_query, {k: v for k, v in result.items() if k not in ("competitors", "reviews", "scenarios")})
    step("Done.")
    return result


if __name__ == "__main__":
    # Quick smoke test from the terminal: python pipeline.py
    out = run_pipeline(
        ProductInput(
            search_query="adjustable phone stand",
            product_description="Aluminum adjustable phone stand with weighted steel base, fits phones in cases up to 6mm thick, cable channel",
            costs=pricing.CostInputs(unit_cost=3.20, freight_per_unit=0.60, duty_rate=0.25, fulfillment_fee=3.22),
        ),
        progress=print,
    )
    print("\nTop complaints:", [c["theme"] for c in out["insights"]["top_complaints"]])
    print("Title:", out["listing"]["title"])
    print("Recommended price:", out["pricing"]["recommended_price"], "|", out["pricing"]["verdict"])
