"""Module B: agricultural advisor (propositional-logic inference over the knowledge base)."""
import streamlit as st
from utils.ui import hero, note, section, load_or_stop
from integration import district_context


def render():
    data, rb = load_or_stop()
    hero("Agricultural Advisory System",
         "Answers come only from the verified knowledge base through propositional-logic rules — no external AI, no invented doses.", "🩺")
    section("⚡", "Try an example (one click)")
    examples = [("🌾 Wheat yellow rust", dict(crop="Wheat", symptoms="orange powdery stripes along the veins of leaves")),
                ("🍚 Rice stem borer", dict(crop="Rice", symptoms="central shoot dries and white empty panicles")),
                ("☁️ Cotton bollworm", dict(crop="Cotton", symptoms="pink larvae inside bolls and rosette flowers")),
                ("🦠 Rice diseases", dict(crop="Rice", cats=["Disease"])),
                ("🚫 Urea dose (refused)", dict(crop="Rice", question="how much urea per acre for rice"))]
    for i, (col, (label, ex)) in enumerate(zip(st.columns(len(examples)), examples)):
        if col.button(label, key=f"adv_ex{i}", use_container_width=True):
            st.session_state.update(adv_question=ex.get("question", ""), adv_crop=ex.get("crop", "Any"), adv_cats=ex.get("cats", []),
                                    adv_stage="Any", adv_district="Any", adv_symptoms=ex.get("symptoms", ""), adv_auto=True)
    section("🔎", "Or ask your own question")
    with st.form("advisor_form"):
        question = st.text_input("Question", key="adv_question", placeholder="e.g. What are common causes of yellow leaves in wheat?")
        c = st.columns(4)
        crop = c[0].selectbox("Crop", ["Any"] + sorted(rb.kb_crops), key="adv_crop")
        cats = c[1].multiselect("Category", rb.categories, key="adv_cats")
        stage = c[2].selectbox("Growth stage (optional)", ["Any"] + rb.stage_options, key="adv_stage")
        district = c[3].selectbox("District (optional)", ["Any"] + data["districts"], key="adv_district")
        symptoms = st.text_input("Symptoms / conditions you observe", key="adv_symptoms",
                                 placeholder="e.g. orange powder on leaves, stunted plants")
        submitted = st.form_submit_button("🩺 Get advice", type="primary")
    go = submitted or st.session_state.pop("adv_auto", False)
    if not go:
        note("Tip: choose a crop and category to browse (e.g. Rice + Disease), or describe symptoms. "
             "Questions about doses, prices or weather are intentionally not answered.")
        return
    dist = None if district == "Any" else district
    env = {}
    if dist:
        ctx = district_context(data, dist, 2000, 2024)
        if ctx:
            env = {"HIGH_PH": ctx["soil_ph"] > 8.5, "SANDY_SOIL": "sand" in ctx["soil_type"].lower()}
            with st.expander(f"Environmental context for {dist} (soil/climate file)"):
                m = st.columns(4)
                m[0].metric("Soil type", ctx["soil_type"]); m[1].metric("Soil pH", f"{ctx['soil_ph']:.2f}")
                m[2].metric("Water availability", ctx["water"]); m[3].metric("Mean rainfall (mm)", f"{ctx['rainfall_mm']:.0f}")
                st.caption("Soil P and K values in the source are estimates; context only.")
    a = rb.answer(question=question, crop=None if crop == "Any" else crop, categories=cats,
                  stage=None if stage == "Any" else stage, symptoms=symptoms, district=dist, env=env)
    if not a["supported"]:
        st.warning(a["message"])
    else:
        st.success(a["message"])
        for m in a["matches"]:
            with st.expander(f"{m['crop']} · {m['category']} · {m['cause']}   (evidence score {m['score']})", expanded=m is a["matches"][0]):
                st.markdown(f"**Observed symptoms in KB:** {m['symptoms']}")
                st.markdown(f"**Possible cause:** {m['cause']}")
                if m["conditions"]:
                    st.markdown(f"**Relevant conditions:** {m['conditions']}")
                st.markdown(f"**Recommended action:** {m['action']}")
                st.markdown(f"**Prevention:** {m['prevention']}")
                st.markdown(f"**Growth stage:** {m['stage']} · **Applicable region:** {m['region']}")
                st.caption(f"Source: {m['source']} (KB entry {m['kb_id']})")
                if m["region_note"]:
                    st.info(m["region_note"])
                st.markdown(f"**Why this rule fired** ({m['mode']}; matched words: {', '.join(m['matched_words']) or 'category match'})")
                st.code("\n".join(m["trace"]), language="text")
    for n in a["env_notes"]:
        st.info(f"Environmental rule fired: {n['rule']} → {n['cause']}: {n['action']} (Source: {n['source']})")
    with st.expander("Facts extracted from your input (propositions)"):
        st.write(f"Detected crops: {a['parsed']['crops'] or '—'} · categories: {a['parsed']['categories'] or '—'} · "
                 f"symptom words: {a['parsed']['symptom_words'] or '—'}")
        st.code(", ".join(a["facts"]), language="text")
        st.caption(f"{a['n_rules']:,} Horn clauses compiled from {len(rb.kb)} knowledge-base entries; inference = forward chaining.")
    note("Guidance is limited to what the knowledge base states. It is not a diagnosis; consult a local agriculture extension officer for confirmation.")
