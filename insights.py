"""Module D: crop insights and analytics from the historical dataset."""
import pandas as pd
import streamlit as st
from utils.ui import hero, note, load_or_stop
from utils import plots


def render():
    data, _ = load_or_stop()
    t = data["table"]
    t = t[t["Valid"] & ~t["Is_Aggregate"]]
    hero("Crop Insights & Analytics", "Historical crop performance by district, crop, season and year (valid records only).", "📊")
    seasons = sorted(t["Season"].unique())
    c = st.columns(4)
    districts = c[0].multiselect("District(s)", data["districts"], default=[])
    all_crops = sorted(t["Crop"].unique())
    crops = c[1].multiselect("Crop(s)", all_crops, default=[x for x in ("Wheat", "Rice") if x in all_crops])
    season = c[2].selectbox("Season", ["All"] + seasons)
    y0, y1 = int(t["Year_Start"].min()), int(t["Year_Start"].max())
    yr = c[3].slider("Years (season start)", y0, y1, (y0, y1))
    f = t[t["Year_Start"].between(*yr)]
    if districts:
        f = f[f["District"].isin(districts)]
    if season != "All":
        f = f[f["Season"] == season]
    scope = ", ".join(districts) if districts else "all Punjab districts"
    if not crops:
        st.info("Select at least one crop to see crop trends.")
    fc = f[f["Crop"].isin(crops)]
    if f.empty or (crops and fc.empty):
        st.warning("No valid historical records match these filters.")
        return
    st.caption(f"{len(fc):,} district-crop-year records for {scope}. Figures are historical, not forecasts.")
    tabs = st.tabs(["Production trend", "Yield trend", "Area comparison", "Districts", "Rabi vs Kharif", "Top crops"])
    with tabs[0]:
        if crops:
            w = fc.groupby(["Year_Start", "Crop"])["Production_t"].sum().unstack() / 1e3
            st.pyplot(plots.lines(w, f"Production by year — {scope}", "thousand tonnes"))
    with tabs[1]:
        if crops:
            g = fc.groupby(["Year_Start", "Crop"]).agg(p=("Production_t", "sum"), a=("Area_Harvested_ha", "sum"))
            st.pyplot(plots.lines((g["p"] / g["a"]).unstack(), f"Yield (production ÷ harvested area) — {scope}", "t/ha"))
    with tabs[2]:
        if crops:
            a = fc.groupby("Crop")["Area_Harvested_ha"].sum() / fc["Year_Start"].nunique() / 1e3
            st.pyplot(plots.bar(a.index, a.values, "Mean annual harvested area", "thousand ha"))
    with tabs[3]:
        if crops:
            one = st.selectbox("Crop for district comparison", crops)
            d = f[f["Crop"] == one].groupby("District").agg(p=("Production_t", "mean"), y=("Yield_t_ha", "median")).sort_values("p", ascending=False).head(15)
            l, r = st.columns(2)
            l.pyplot(plots.bar(d.index, d["p"] / 1e3, f"{one}: mean annual production", "thousand tonnes", horizontal=True))
            r.pyplot(plots.bar(d.sort_values("y", ascending=False).index, d.sort_values("y", ascending=False)["y"], f"{one}: median yield", "t/ha", color="#f9a825", horizontal=True))
    with tabs[4]:
        s = f[f["Season"].isin(["Rabi", "Kharif"])]
        if s.empty:
            st.info("No Rabi/Kharif records for these filters.")
        else:
            w = s.groupby(["Year_Start", "Season"])["Production_t"].sum().unstack() / 1e6
            st.pyplot(plots.lines(w, "Total production by season", "million tonnes"))
            st.caption("Season labels come from the dataset; 'Annual' (e.g. sugarcane) and perennial crops are not part of this comparison.")
    with tabs[5]:
        dd = [d for d in districts] or [None]
        rows = []
        for dist in (districts or data["districts"][:1]):
            sub = f[f["District"] == dist]
            top = sub.groupby("Crop").agg(mean_prod_t=("Production_t", "mean"), median_yield=("Yield_t_ha", "median"), years=("Year_Start", "nunique"))
            top = top[top["years"] >= 3].sort_values("mean_prod_t", ascending=False).head(5).reset_index()
            top.insert(0, "District", dist)
            rows.append(top)
        res = pd.concat(rows) if rows else pd.DataFrame()
        st.markdown("**Metric:** mean annual production (tonnes) over the selected years, for crops with ≥ 3 valid years. "
                    "Tonnes of different crops are not comparable in economic value." + ("" if districts else " (Showing the first district; select districts above.)"))
        st.dataframe(res.round(2), hide_index=True, use_container_width=True)
    note("Historical performance does not guarantee future suitability. Records with missing values or implausible yields were excluded.")
