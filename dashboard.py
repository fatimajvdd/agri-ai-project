"""Module A: dashboard. Every number is computed from the uploaded datasets."""
import streamlit as st
from utils.ui import (hero, note, section, stat_tile, nav_card, go_button, marquee, fact, load_or_stop)
from utils import plots
from utils.data_loader import match_report

CROP_EMOJI = {"Wheat": "🌾", "Rice": "🍚", "Cotton": "☁️", "Maize": "🌽", "Sugarcane": "🎋", "Potato": "🥔",
              "Mango": "🥭", "Kinno": "🍊", "Gram": "🫘", "Tomato": "🍅", "Onion": "🧅"}


def _top_district(real, crop, year):
    s = real[(real["Crop"] == crop) & real["Valid"] & (real["Year_Start"] == year)]
    if s.empty:
        return None
    g = s.groupby("District")["Production_t"].sum()
    return g.idxmax(), g.max()


def render():
    data, _ = load_or_stop()
    t, q = data["table"], data["quality"]
    real = t[~t["Is_Aggregate"]]
    hero("AI-Based Agricultural Advisory & Smart Crop Planning — Punjab",
         "Ask farming questions, explore district crop history and plan your land with Propositional Logic, "
         "a Constraint Satisfaction Problem and a Genetic Algorithm.", "🌾")

    tiles = [("🏞️", "Districts", real["District"].nunique(), "Punjab, Pakistan"),
             ("🌱", "Crops", real["Crop"].nunique(), "single crops in the data"),
             ("📅", "Years", f"{t['Year_Start'].min()}–{t['Year_Start'].max()+1}", f"{t['Year_Start'].nunique()} seasons"),
             ("🗂️", "Records", f"{q['hist_rows']:,}", f"{len(t):,} district-crop-years"),
             ("📚", "KB entries", q["kb_rows"], "verified advisories")]
    for i, (col, tl) in enumerate(zip(st.columns(5), tiles)):
        col.markdown(stat_tile(*tl, delay=i * 0.12), unsafe_allow_html=True)

    section("🧭", "What would you like to do? (click a button)")
    cards = [("advisor", "🩺", "Agricultural Advisor", "Describe a crop problem and get rule-based guidance with its source and the logic behind it.", "#c62828", "Open the Advisor"),
             ("planner", "🌱", "Smart Crop Planner", "Split your land between crops. CSP guarantees your limits, the Genetic Algorithm optimises.", "#2e7d32", "Plan my land"),
             ("insights", "📊", "Crop Insights", "Explore yield, production and area by district, crop, season and year.", "#0288d1", "Explore the data")]
    for i, (col, c) in enumerate(zip(st.columns(3), cards)):
        key, icon, title, text, accent, label = c
        col.markdown(nav_card(icon, title, text, accent, delay=0.1 + i * 0.15), unsafe_allow_html=True)
        with col:
            go_button(key, label, icon)

    section("🚀", "How it works")
    steps = ["Choose your <b>district, season and crops</b>", "Set your <b>land and min/max limits</b>",
             "Get a <b>validated plan</b> with charts and reasons"]
    for i, (col, s) in enumerate(zip(st.columns(3), steps)):
        col.markdown(f'<div class="step" style="animation-delay:{0.2*i}s"><b class="n">{i+1}</b>{s}</div>', unsafe_allow_html=True)

    last = t["Year_Start"].max()
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    marquee([f"{CROP_EMOJI.get(c, '🌿')} {c}" for c in ["Wheat", "Rice", "Cotton", "Maize", "Sugarcane", "Potato", "Mango", "Kinno", "Gram", "Tomato", "Onion"]
             if c in set(real["Crop"])])

    # data-driven highlights (computed, never hard-coded)
    hl = []
    for crop in ("Wheat", "Rice", "Cotton"):
        for yr in (last, last - 1):
            r = _top_district(real, crop, yr)
            if r:
                hl.append(f"🏆 Largest <b>{crop}</b> producer in {yr}-{str(yr+1)[2:]}: <b>{r[0]}</b> ({r[1]/1e3:,.0f} thousand tonnes)")
                break
    if hl:
        for i, (col, h) in enumerate(zip(st.columns(len(hl)), hl)):
            with col:
                fact(h, delay=i * 0.15)

    section("📈", "Punjab at a glance (historical)")
    recent = real[(real["Year_Start"] > last - 10) & real["Valid"]]
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            top = recent.groupby(["Year_Start", "Crop"])["Production_t"].sum().groupby("Crop").mean().sort_values(ascending=False).head(10)
            st.pyplot(plots.bar(top.index, top.values / 1e6, f"Top crops by mean annual production, {last-9}–{last+1}", "million tonnes", horizontal=True))
    with right:
        with st.container(border=True):
            main = ["Wheat", "Rice", "Cotton", "Maize", "Sugarcane"]
            w = real[real["Crop"].isin(main) & real["Valid"]].groupby(["Year_Start", "Crop"])["Production_t"].sum().unstack() / 1e6
            st.pyplot(plots.lines(w, "Punjab production of major crops (historical)", "million tonnes"))

    with st.expander("Data quality summary (computed from the files)"):
        m = match_report(data)
        st.markdown(
            f"- **Historical file:** {q['hist_rows']:,} rows; {q['hist_duplicates']} duplicates; missing area/production in "
            f"{q['hist_missing'].get('Area_Sown', 0)}/{q['hist_missing'].get('Production', 0)} rows; "
            f"{q['crop_labels_raw']} raw crop labels → {q['crop_labels_clean']} after name standardisation; "
            f"{q['placeholder_rows']:,} placeholder rows (\"Unnamed crop\") removed.\n"
            f"- **Tehsil rows are estimates:** {q['estimated_tehsil_rows']:,} rows are district totals split by tehsil share, "
            f"so the project works at **district** level.\n"
            f"- **Yield checks:** {q['yield_gt_100']} rows have yield > 100 t/ha (source errors); extreme district yields are flagged "
            f"and excluded from yield statistics; {q['zero_area_positive_prod']} rows have production but zero harvested area.\n"
            f"- **Soil/environment file:** {q['soil_rows']:,} rows; {m['matched_in_soil']} of {m['district_year_keys_hist']} "
            f"district-year keys of the historical file have a match.\n"
            f"- **Knowledge base:** {m['hist_crops_with_kb']} of {m['hist_crops_total']} historical crops have KB entries.")
    note("All figures are <b>historical records</b>. Estimated outputs elsewhere in the app are calculations from historical yields, "
         "not forecasts or guarantees. Cotton yield is as reported in the source (units not confirmed as lint or seed cotton).")
