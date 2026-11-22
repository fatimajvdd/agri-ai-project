"""Module C: Smart Crop Planner (CSP + Genetic Algorithm, with propositional-logic inputs)."""
import pandas as pd
import streamlit as st
from utils.ui import hero, note, section, load_or_stop
from utils import plots, calculations as calc
from integration import plan_crops


def plan_figures(r):
    t, comp = r["table"], r["comparison"]
    alloc = t.set_index("Crop")[["Equal split (ha)", "Historical-share (ha)", "Allocation (ha)"]]
    alloc.columns = ["Equal split", "Historical-share", "GA-optimised"]
    figs = {"allocation": plots.grouped(alloc, "Land allocation: baselines vs GA-optimised", "hectares"),
            "production": plots.bar(t["Crop"], t["Est. production (t)"], "Estimated production by crop (GA plan)", "tonnes (estimate)", color="#2e7d32"),
            "methods": plots.bar(comp["Method"], comp["Est. production (t)"], "Estimated production by method", "tonnes (estimate)", color="#f9a825")}
    h = r["ga"].history
    conv = pd.DataFrame({"best": h["best"], "mean": h["mean"]}).set_index(h["generation"])
    figs["convergence"] = plots.lines(conv, "GA fitness across generations", "fitness")
    return figs


def show_plan(r):
    for w in r["warnings"]:
        st.warning(w)
    if not r["ok"]:
        for e in r["errors"]:
            st.error(e)
        return
    s = r["settings"]
    m = st.columns(4)
    m[0].metric("Total allocated", f"{r['total_allocated_ha']:.2f} ha", f"{100*r['total_allocated_ha']/r['land_ha']:.1f}% of land")
    m[1].metric("Remaining land", f"{r['remaining_ha']:.2f} ha")
    m[2].metric("Est. production (historical yields)", f"{r['estimate']['production_t']:,.0f} t")
    ok = all(v["passed"] for v in r["validation"])
    m[3].metric("Constraints", "All satisfied ✅" if ok else "Violated ❌")

    section("✅", "Recommended allocation")
    show = r["table"][["Crop", "Allocation (ha)", "Share of land (%)", "Reference yield (t/ha)", "Est. production (t)", "Years of data"]]
    st.dataframe(show.round(2), hide_index=True, use_container_width=True)
    st.caption(f"Reference yield = median valid district yield {s['years']} (historical, not a forecast). "
               "Estimated production = allocated hectares × reference yield.")
    st.download_button("Download plan (CSV)", r["table"].round(3).to_csv(index=False), file_name="crop_plan.csv", mime="text/csv")

    f = plan_figures(r)
    a, b = st.columns(2)
    a.pyplot(f["allocation"]); b.pyplot(f["production"])
    c, d = st.columns(2)
    c.pyplot(f["methods"]); d.pyplot(f["convergence"])

    section("⚖️", "Comparison with baselines")
    st.dataframe(r["comparison"].round(3), hide_index=True, use_container_width=True)
    raw = r["raw_baseline_satisfaction"]
    st.caption("Baselines are repaired to satisfy your constraints so the comparison is fair. Before repair, the simple equal split "
               f"{'satisfied' if raw['Equal split'] else 'violated'} the constraints and the historical-share split "
               f"{'satisfied' if raw['Historical-share'] else 'violated'} them.")

    with st.expander("Constraint validation (CSP)", expanded=True):
        v = pd.DataFrame(r["validation"]).rename(columns={"constraint": "Constraint", "passed": "Result", "detail": "Detail"})
        v["Result"] = v["Result"].map({True: "✅ satisfied", False: "❌ violated"})
        st.dataframe(v, hide_index=True, use_container_width=True)
    with st.expander("How this recommendation was produced"):
        p, ga = r["problem"], r["ga"]
        st.markdown(
            f"1. **Historical data** gave each crop's reference yield for {s['district']} ({s['years']}).\n"
            f"2. **Propositional-logic / knowledge-base inputs:** " + ("; ".join(r["kb_notes"]) if r["kb_notes"] else "no KB rule restricted this plan.") + "\n"
            f"3. **CSP:** variables = land units of each crop ({p.total_units} units of {p.step_ha:.3f} ha); domains = the min–max range per crop; "
            f"constraints = total ≤ land, ≥ required utilisation, per-crop limits" + (f", ≤ {p.max_crops} crops" if p.max_crops else "") +
            f", blocked crops = 0. Backtracking with forward checking found feasible starting points ({r['csp_stats']['nodes']} nodes, "
            f"{r['csp_stats']['backtracks']} backtracks for the last search).\n"
            f"4. **Genetic Algorithm:** {len(ga.history)} generations, {ga.evaluations:,} fitness evaluations, {ga.runtime_s*1000:.0f} ms. "
            f"Fitness = {s['alpha']:.2f} × normalised production + {1-s['alpha']:.2f} × normalised yield-performance index.\n"
            f"5. **CSP validation** re-checked the final plan: {'all constraints satisfied' if ok else 'a constraint failed'}.")
    if r["advisories"]:
        with st.expander("Disease & pest guidance for the planned crops (from the knowledge base)"):
            for crop, ms in r["advisories"].items():
                st.markdown(f"**{crop}**")
                for x in ms:
                    st.markdown(f"- *{x['category']}*: {x['cause']} — {x['action']} (Source: {x['source']})")
                if not ms:
                    st.caption("No KB entries for this crop.")
    if r["context"]:
        cx = r["context"]
        st.caption(f"District context (soil/climate file): {cx['soil_type']}, pH {cx['soil_ph']:.2f}, water availability {cx['water']}, "
                   f"irrigation: {cx['irrigation']}. Water is categorical in the data, so it is shown as context rather than a numeric constraint.")
    note("The result is an optimisation of <b>historical</b> yields under your constraints. It is not a production forecast, and tonnes of "
         "different crops are not equal in economic value.")


def render():
    data, rb = load_or_stop()
    t = data["table"]
    hero("Smart Crop Planner", "Allocate your land between crops: CSP guarantees the constraints, the Genetic Algorithm optimises within them.", "🌱")
    section("1", "Where and when?")
    y0, y1 = int(t["Year_Start"].min()), int(t["Year_Start"].max())
    c = st.columns(3)
    district = c[0].selectbox("District", data["districts"])
    season = c[1].selectbox("Season", list(calc.SEASONS), help="Crops of the same season compete for the same land. Annual crops (sugarcane) are included in both.")
    start, end = c[2].slider("Historical reference period (season start year)", y0, y1, (max(y0, y1 - 9), y1))
    cand = calc.candidate_crops(t, district, season, start, end)
    if cand.empty:
        st.warning("No crop has enough valid historical data for this district, season and period. Try a longer period.")
        return
    section("2", "Your land")
    c = st.columns(4)
    land = c[0].number_input("Available land", min_value=0.0, value=50.0, step=1.0)
    unit = c[1].selectbox("Unit", ["hectares", "acres"])
    water = c[2].selectbox("Your water availability", ["Unknown", "High", "Medium", "Low", "Very Low"])
    util = c[3].slider("Minimum land to use (%)", 50, 100, 95)
    land_ha = calc.to_hectares(land, unit)
    section("3", "Crops and limits")
    crops = st.multiselect("Preferred crops", list(cand["Crop"]), default=list(cand["Crop"][:4]),
                           help="Only crops with ≥ 3 valid historical yield records in the chosen period are offered.")
    limits = pd.DataFrame({"Crop": crops, "Min (ha)": [0.0] * len(crops), "Max (ha)": [round(land_ha, 2)] * len(crops)})
    st.markdown("**Minimum / maximum allocation per crop (hectares)**")
    edited = st.data_editor(limits, hide_index=True, disabled=["Crop"], use_container_width=True,
                            key=f"limits_{district}_{season}_{'-'.join(crops)}_{round(land_ha, 2)}")
    with st.expander("More constraints and settings"):
        rot = st.multiselect("Crop rotation restriction: do NOT plant these this season", crops,
                             help="e.g. a crop that was grown on this land last season. They are forced to 0 ha by the CSP.")
        mc = st.number_input("Maximum number of different crops (0 = no limit)", min_value=0, value=0, step=1)
        strict = st.checkbox("Strict KB crop-belt mode: exclude crops whose knowledge-base belt does not list this district", value=False)
        alpha = st.slider("Production weight in the fitness (rest = yield-performance index)", 0.0, 1.0, 0.5, 0.05)
        seed = st.number_input("Random seed (reproducible results)", min_value=0, value=0, step=1)
        g1, g2 = st.columns(2)
        pop = g1.number_input("GA population size", 20, 300, 80, 10)
        gens = g2.number_input("GA max generations", 10, 500, 150, 10)
    section("4", "Get your plan")
    if st.button("🌱 Generate plan", type="primary", use_container_width=True):
        mins = dict(zip(edited["Crop"], edited["Min (ha)"]))
        maxs = dict(zip(edited["Crop"], edited["Max (ha)"]))
        with st.spinner("Running CSP and Genetic Algorithm..."):
            st.session_state["plan"] = plan_crops(
                data, rb, district, season, land_ha, crops, mins, maxs, start, end, rotation_blocked=rot, utilisation=util / 100,
                alpha=alpha, max_crops=int(mc) or None, strict_belt=strict, water_level=None if water == "Unknown" else water,
                seed=int(seed), ga_params={"pop_size": int(pop), "generations": int(gens)})
        if st.session_state["plan"].get("ok"):
            st.toast("Plan ready - all constraints satisfied", icon="✅")
    if st.session_state.get("plan") is not None:
        show_plan(st.session_state["plan"])
    else:
        note("Choose a district, season and crops, set your limits, then press <b>Generate plan</b>.")
