"""AI-Based Agricultural Advisory and Smart Crop Planning System for Punjab, Pakistan.
Run with:  streamlit run app.py
"""
import streamlit as st

st.set_page_config(page_title="Punjab AgriAI", page_icon="🌾", layout="wide")

from utils import ui                                   # noqa: E402  (after set_page_config)
from views import dashboard, advisor, planner, insights   # noqa: E402

ui.apply_theme()
pages = {
    "dashboard": st.Page(dashboard.render, title="Dashboard", icon="🏠", url_path="dashboard", default=True),
    "advisor": st.Page(advisor.render, title="Agricultural Advisor", icon="🩺", url_path="advisor"),
    "planner": st.Page(planner.render, title="Smart Crop Planner", icon="🌱", url_path="planner"),
    "insights": st.Page(insights.render, title="Crop Insights", icon="📊", url_path="insights"),
}
ui.PAGES.update(pages)          # lets any page create clickable links to the others
st.sidebar.markdown('<div class="brand"><div class="b1">🌾</div><div class="b2">Punjab AgriAI</div>'
                    '<div class="b3">Propositional Logic · CSP · Genetic Algorithm</div></div>', unsafe_allow_html=True)
nav = st.navigation(list(pages.values()))
st.sidebar.divider()
st.sidebar.caption("Scope: Punjab, Pakistan only. Historical figures are not forecasts. "
                   "No external LLM is used; all answers come from the project datasets.")
nav.run()
