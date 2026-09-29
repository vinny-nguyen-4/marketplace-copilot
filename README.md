# Marketplace Copilot

An AI tool for e-commerce operators. Give it a product and it will:

1. **Research the market.** Pulls competitor listings across Amazon, Walmart, and eBay: price, rating, review count, and title keywords.
2. **Mine customer reviews.** Uses Claude to find the top complaints, praised features, and unmet needs across competitors.
3. **Write an optimized listing.** Produces a title, bullets, description, and backend keywords tuned to each marketplace's style rules, aimed at the gaps competitors leave open.
4. **Recommend a price.** Calculates landed cost (unit + freight + duty), break-even, and the minimum price for a target margin, then positions it against the competitor price distribution.
5. **Draft supplier emails.** Writes a clear negotiation email to overseas vendors, with optional Simplified Chinese or Malay translation.

## Screenshots

**Market snapshot:** competitor pricing, ratings, and title keywords
![Market snapshot](marketplace_screenshots/market.png)

**Customer insights:** top complaints and unmet needs from competitor reviews
![Customer insights](marketplace_screenshots/insights.png)

**Optimized listing:** top competitor vs. AI-optimized listing
![Optimized listing](marketplace_screenshots/listing.png)

**Pricing:** landed cost, break-even, and recommended price
![Pricing](marketplace_screenshots/pricing.png)
> **Design choice:** AI handles language tasks (review analysis, copywriting, translation). All pricing math is deterministic Python, because numbers need to be exact and auditable.

## Architecture

```
Streamlit UI (app.py)
      │
Pipeline orchestrator (pipeline.py)
      ├── modules/fetcher.py          competitor listings + reviews (sample CSV or Rainforest API)
      ├── modules/review_analyzer.py  Claude → structured JSON insights
      ├── modules/listing_writer.py   Claude → listing copy + vendor emails
      └── modules/pricing.py          landed cost, margin, price recommendation
      │
SQLite cache (db.py)                  API responses + saved runs
```

Prompts live in `prompts/` as plain text, so they can be tuned without touching code.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # add your ANTHROPIC_API_KEY (optional)
streamlit run app.py
```

- **No API key?** The app runs in offline demo mode with keyword-based analysis and template copy, so you can explore the UI for free.
- **Live data:** Set `RAINFOREST_API_KEY` and choose the `rainforest` source in the sidebar. Responses are cached in SQLite to save credits.
- **Terminal smoke test:** `python pipeline.py`

## Project structure

```
app.py               Streamlit UI (5 tabs: market, insights, listing, pricing, vendor email)
pipeline.py          Orchestrator; also runnable from the terminal
db.py                SQLite cache and run history
modules/             Fetcher, Claude wrapper, analyzer, writer, pricing engine
prompts/             Prompt templates
data/sample/         Sample phone-stand listings and reviews for offline demos
```

## Roadmap

- Track competitor prices over time (daily snapshot + alert on price drops)
- Inventory reorder calculator (lead time from China/Malaysia + safety stock)
- Freight mode comparison (small parcel vs LTL vs FTL cost per unit)
- Batch mode: optimize a whole catalog from a CSV

## Notes

Marketplace fee percentages in `modules/pricing.py` are approximations. Check each marketplace's current fee schedule before relying on them.
