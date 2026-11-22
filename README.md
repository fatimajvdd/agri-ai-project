# AI-Based Agricultural Advisory and Smart Crop Planning System — Punjab, Pakistan

Streamlit website with three course algorithms in one pipeline: **Propositional Logic** (advisory), **CSP** (feasibility/validation),
**Genetic Algorithm** (land-allocation optimisation). Scope: Punjab only. No external LLM or API.

## Run
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py                                   # website
python -m unittest discover -s tests -v                # 55 tests (pytest also works)
python -m evaluation.experiments                       # real experiments -> results/ (about 40 s)
python docs/make_architecture_diagram.py               # redraw the diagram
```
The three CSV files must be in `data/` (included). Pages: Dashboard, Agricultural Advisor, Smart Crop Planner, Crop Insights.


## Run in VS Code (Windows / macOS / Linux)
1. Install Python 3.10+ and VS Code (with the "Python" extension). Open this folder: **File > Open Folder**.
2. Terminal > New Terminal, then:
   - Windows: `py -m venv .venv` then `.venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv .venv` then `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. If VS Code asks which interpreter to use, choose the one inside `.venv`
   (Ctrl+Shift+P > "Python: Select Interpreter").
5. `streamlit run app.py` - the browser opens at http://localhost:8501 (or press F5 and pick "Streamlit: run app.py").

## Structure
```
app.py  integration.py            entry point / the integrated pipeline
algorithms/  propositional_logic.py  csp.py  genetic_algorithm.py
utils/       data_loader.py preprocessing.py validation.py calculations.py ui.py plots.py
views/       dashboard.py advisor.py planner.py insights.py
evaluation/  baseline.py metrics.py experiments.py advisory_testset.py advisory_eval.py
tests/       test_algorithms.py (48 tests)  test_ui_smoke.py (7 page tests with a fake Streamlit)
results/     charts/ evaluation_results/        docs/  architecture, algorithms, audit, results, viva questions
```

## Design decisions (made after the data audit)
1. **District level only** — tehsil rows in the historical file are estimated splits of district totals.
2. **Integration** — KB crop-belt entries -> CSP blocked-crop constraint (optional strict mode) or warning; rice water-use rule -> warning when the farmer reports low water;
   rule base -> guidance for planned crops. Pest/disease rules do **not** restrict land (that would be invented).
3. **Water** is categorical in the data, so it is context/warning, not a numeric constraint.
4. **Cotton yield** is shown as reported; the unit (lint vs seed cotton) is unconfirmed — please check with the data source.
5. **Season** — the farmer plans one season (Kharif or Rabi); sugarcane (Annual) competes in both. Rotation restriction = crops that must not be planted this season.
6. **Fitness** mixes tonnage with a yield-performance index (adjustable) because tonnes of different crops are not comparable.

## Honest results summary (details: `docs/results.md`)
216 held-out scenarios: GA beats equal split / historical-share / CSP-only on held-out production in 99.5% / 98.6% / 97.2% of scenarios, but the gain is largely a tonnage effect (sugarcane).
Advisory: ~100% on our hand-written paraphrases, **70%** on a harder farmer-style set. UI pages were smoke-tested with a fake Streamlit; run `streamlit run app.py` to check the real rendering.

## Ethics and limitations
Advice is limited to the knowledge base and carries its source; no doses, prices or diagnoses are generated. Plans are optimisations of historical yields, not forecasts or economic advice.
Limitations: keyword matching misses synonyms; KB covers 40 of 86 crops; soil P/K are estimates; no market prices or crop-rotation agronomy beyond user restrictions.
Farmer inputs live only in the session.

## Data sources and citations
Historical crop data: Crop Reporting Service Punjab (as supplied). Soil: ISRIC SoilGrids 2.0. Climate: NASA POWER. Knowledge base sources are listed per row in the `Source`
column (CABI Plantwise, AARI Faisalabad, Soil Fertility Research Institute Lahore, CCRI Multan, Punjab Agriculture Dept., ...). Please add the course textbook and any extra references in the report.

## AI-assistance disclosure
This code base was developed with the help of an AI coding assistant (Claude, Anthropic) from the team's master prompt and datasets. The team must read, run and be able to explain
all code; state this disclosure in the report as the course requires. Individual contribution statements are to be written by each team member.
