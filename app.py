"""Streamlit UI. Run with:  streamlit run app.py"""
import pandas as pd
import plotly.express as px
import streamlit as st

from modules import listing_writer, pricing
from modules.llm import has_api_key
from pipeline import ProductInput, run_pipeline

st.set_page_config(page_title="Marketplace Copilot", layout="wide")
st.title("Marketplace Copilot")
st.caption("Competitor research, review insights, listing copy, and pricing in one pass.")

if not has_api_key():
    st.info("Running in offline demo mode. Add ANTHROPIC_API_KEY to your .env file for Claude-powered analysis.")

# ---------------- Sidebar inputs ----------------
with st.sidebar:
    st.header("Product")
    query = st.text_input("Search query (what shoppers type)", "adjustable phone stand")
    description = st.text_area(
        "Our product (real specs only)",
        "Aluminum adjustable phone stand with weighted steel base, fits phones in cases up to 6mm thick, "
        "built-in cable channel, anti-scratch silicone padding.",
        height=120,
    )
    marketplace = st.selectbox("Marketplace", ["amazon", "walmart", "ebay"])
    source = st.selectbox("Data source", ["sample", "rainforest"], help="'sample' uses bundled data; 'rainforest' needs an API key")

    st.header("Costs (per unit, USD)")
    unit_cost = st.number_input("Supplier unit cost", 0.0, value=3.20, step=0.10)
    freight = st.number_input("Freight per unit", 0.0, value=0.60, step=0.05)
    duty = st.number_input("Duty rate (%)", 0.0, 100.0, value=25.0, step=1.0) / 100
    fulfillment = st.number_input("Fulfillment fee", 0.0, value=3.22, step=0.10)
    target_margin = st.slider("Target net margin (%)", 5, 60, 30) / 100

    run = st.button("Run analysis", type="primary", width="stretch")

costs = pricing.CostInputs(unit_cost, freight, duty, fulfillment, marketplace, target_margin)

if run:
    status = st.status("Running pipeline...", expanded=True)
    try:
        st.session_state.result = run_pipeline(
            ProductInput(query, description, marketplace, source, costs), progress=status.write
        )
        status.update(label="Analysis complete", state="complete", expanded=False)
    except Exception as err:  # show a friendly error instead of a stack trace
        status.update(label="Something went wrong", state="error")
        st.error(str(err))

result = st.session_state.get("result")
if not result:
    st.write("Fill in the sidebar and click **Run analysis**.")
    st.stop()

comp: pd.DataFrame = result["competitors"]
tabs = st.tabs(["Market snapshot", "Customer insights", "Optimized listing", "Pricing", "Vendor email"])

# ---------------- Market snapshot ----------------
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Competitors", len(comp))
    c2.metric("Median price", f"${comp['price'].median():.2f}")
    c3.metric("Avg rating", f"{comp['rating'].mean():.2f}")
    c4.metric("Total reviews", f"{int(comp['review_count'].sum()):,}")

    fig = px.scatter(
        comp, x="price", y="rating", size="review_count", color="marketplace", hover_name="title",
        labels={"price": "Price ($)", "rating": "Rating"}, title="Price vs rating (bubble = review count)",
    )
    st.plotly_chart(fig, width="stretch")

    kw = pd.DataFrame(result["keywords"], columns=["keyword", "count"])
    st.plotly_chart(px.bar(kw, x="count", y="keyword", orientation="h", title="Most common title keywords")
                    .update_yaxes(autorange="reversed"), width="stretch")
    st.dataframe(comp[["marketplace", "brand", "title", "price", "rating", "review_count"]], width="stretch")

# ---------------- Customer insights ----------------
with tabs[1]:
    ins = result["insights"]
    st.write(ins.get("summary", ""))
    left, right = st.columns(2)
    with left:
        st.subheader("Top complaints")
        if ins["top_complaints"]:
            st.plotly_chart(px.bar(pd.DataFrame(ins["top_complaints"]), x="frequency", y="theme", orientation="h")
                            .update_yaxes(autorange="reversed"), width="stretch")
            for c in ins["top_complaints"]:
                st.markdown(f"- **{c['theme']}** ({c['frequency']}): _{c['example']}_")
    with right:
        st.subheader("Top praises")
        for p in ins["top_praises"]:
            st.markdown(f"- **{p['theme']}** ({p['frequency']}): _{p['example']}_")
        st.subheader("Unmet needs (your opportunities)")
        for need in ins["unmet_needs"]:
            st.markdown(f"- {need}")

# ---------------- Optimized listing ----------------
with tabs[2]:
    lst = result["listing"]
    best = comp.sort_values("review_count", ascending=False).iloc[0]
    before, after = st.columns(2)
    with before:
        st.subheader("Top competitor listing")
        st.markdown(f"**{best['title']}**")
        for b in str(best["bullets"]).split("|"):
            if b.strip():
                st.markdown(f"- {b.strip()}")
    with after:
        st.subheader("Our optimized listing")
        st.markdown(f"**{lst['title']}**")
        st.caption(f"{len(lst['title'])} characters")
        for b in lst["bullets"]:
            st.markdown(f"- {b}")
        st.write(lst["description"])
        st.markdown("**Search keywords:** " + ", ".join(lst.get("search_keywords", [])))
    with st.expander("Why these choices?"):
        for r in lst.get("rationale", []):
            st.markdown(f"- {r}")

# ---------------- Pricing ----------------
with tabs[3]:
    pr = result["pricing"]
    a, b, c, d = st.columns(4)
    a.metric("Landed cost", f"${pr['landed_cost']:.2f}")
    b.metric("Break-even price", f"${pr['break_even_price']:.2f}")
    c.metric("Recommended price", f"${pr['recommended_price']:.2f}",
             help=f"Cheaper than {100 - pr['recommended_percentile'] * 100:.0f}% of competitors")
    d.metric("Net margin at rec.", f"{pr['at_recommended']['margin'] * 100:.1f}%")
    st.info(pr["verdict"])

    hist = px.histogram(comp, x="price", nbins=12, title="Competitor price distribution")
    hist.add_vline(x=pr["recommended_price"], line_dash="dash", annotation_text="Recommended")
    hist.add_vline(x=pr["break_even_price"], line_dash="dot", annotation_text="Break-even")
    st.plotly_chart(hist, width="stretch")

    st.subheader("Price scenarios")
    sc = result["scenarios"].copy()
    sc["margin"] = (sc["margin"] * 100).round(1).astype(str) + "%"
    sc["pct_of_competitors_cheaper"] = (sc["pct_of_competitors_cheaper"] * 100).round(0).astype(int).astype(str) + "%"
    st.dataframe(sc, width="stretch", hide_index=True)

# ---------------- Vendor email ----------------
with tabs[4]:
    st.write("Draft a message to your supplier using the pricing results.")
    suggested_target = round(unit_cost * 0.9, 2)
    col1, col2, col3 = st.columns(3)
    target_cost = col1.number_input("Target unit cost", 0.0, value=suggested_target, step=0.05)
    qty = col2.number_input("Order quantity", 1, value=2000, step=100)
    lang = col3.selectbox("Translate to", list(listing_writer.LANGUAGES))
    goal = st.text_input("Goal", "Negotiate a lower unit price for a larger order")
    if st.button("Draft email"):
        with st.spinner("Drafting..."):
            st.session_state.email = listing_writer.write_vendor_email(description, unit_cost, target_cost, qty, goal, lang)
    email = st.session_state.get("email")
    if email:
        st.markdown(f"**Subject:** {email['subject']}")
        st.text_area("English", email["body_english"], height=220)
        if email.get("body_translated"):
            st.text_area(lang, email["body_translated"], height=220)
