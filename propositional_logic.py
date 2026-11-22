"""Propositional-logic advisory engine built from the Agricultural Knowledge Base.

Every KB row i is compiled into Horn clauses over atomic propositions, e.g.

    CROP:wheat                      user asks about wheat
    SYM:stripe                      the user's description contains the (stemmed) word "stripe"
    CAT:disease / STAGE:tiller      optional filters chosen by the user
    DIST:attock                     optional district

    R1  CROP:c_i                  -> CROP_OK:i          (axiom for rows that apply to "All crops")
    R2  CROP_OK:i  AND SYM:k      -> HIT:i              (one clause per keyword k of row i)
    R3  CROP_OK:i AND CAT:cat_i AND MODE:BROWSE -> HIT:i   (category browsing, no symptom words)
    R4  HIT:i AND CAT_OK:i AND STAGE_OK:i -> CAUSE:i
    R5  CAUSE:i -> ACTION:i,  CAUSE:i -> PREVENT:i,  CAUSE:i -> SOURCE:i
    R6  DIST:d -> REGION_MATCH:i   (d in the row's district list)

Inference = forward chaining (modus ponens) until no new fact can be derived.
Nothing is generated: all conclusions are text copied from the KB row that fired.
"""
import math
import re
from dataclasses import dataclass, field

STOPWORDS = set("""a an the and or of in on at to for from with without by is are was were be been it its this that
these those as into onto than then there their they them what which who whom how when where why can could should would
may might will do does did not no yes any some most more less very also about after before during between over under up
down out off per each other such many much often usually common commonly cause causes causing caused problem problems
crop crops plant plants farmer farmers please tell me my our we you your i have has had get gets getting having see seen
affect affecting affected relevant practices practice consider precautions take""".split())
IRREGULAR = {"leaves": "leaf", "drying": "dry", "dried": "dry", "dries": "dry", "lodging": "lodge",
             "shedding": "shed", "flies": "fly", "mites": "mite", "larvae": "larva"}
CATEGORY_WORDS = {
    "disease": "Disease", "pest": "Pest", "insect": "Pest", "weed": "Weed",
    "fertilizer": "Nutrient Deficiency", "fertiliser": "Nutrient Deficiency", "nutrient": "Nutrient Deficiency",
    "deficiency": "Nutrient Deficiency", "stress": "Abiotic Stress", "drought": "Abiotic Stress",
    "soil": "Soil Problem", "management": "Management", "disorder": "Physiological Disorder",
}
# Questions the KB cannot answer (we refuse instead of inventing): doses, prices, weather, finance
UNSUPPORTED_INTENT = re.compile(
    r"\b(dosage|dose|how much|kg per|per acre|per hectare|per kanal|quantity of|price|market rate|rate of|"
    r"forecast|weather|rain tomorrow|profit|loan|subsidy|insurance|tractor|joke)\b", re.I)
MIN_TOTAL_IDF, MIN_STRONG_IDF = 2.0, 3.0      # evidence thresholds (set a priori, see docs)


def stem(tok: str) -> str:
    tok = IRREGULAR.get(tok, tok)
    if tok.endswith("ies") and len(tok) > 4:
        return tok[:-3] + "y"
    if tok.endswith("sses"):
        return tok[:-2]
    if tok.endswith("s") and not tok.endswith(("ss", "us", "is")) and len(tok) > 3:
        tok = tok[:-1]
    for suf in ("ing", "ish", "ed"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 4:
            return tok[:-len(suf)]
    return tok


def tokens(text, drop=frozenset()):
    out = []
    for w in re.findall(r"[a-z]+", str(text).lower()):
        if len(w) >= 3 and w not in STOPWORDS:
            s = stem(w)
            if s not in drop and s not in STOPWORDS:
                out.append(s)
    return out


@dataclass(frozen=True)
class Rule:
    rid: str
    premises: tuple
    conclusion: str
    kind: str
    kb_id: int
    key: str = ""

    def __str__(self):
        left = " AND ".join(self.premises) if self.premises else "TRUE"
        return f"{self.rid}: {left}  =>  {self.conclusion}"


class KnowledgeRuleBase:
    """Compiles KB rows to rules and answers queries by forward chaining."""

    def __init__(self, kb, extra_crops=()):
        self.kb = kb.reset_index(drop=True)
        self.rows = {int(r.KB_ID): r for r in self.kb.itertuples()}
        self.crops = sorted(set(self.kb["Crop"]) - {"All crops"} | set(extra_crops))
        self.kb_crops = set(self.kb["Crop"]) - {"All crops"}
        # Only single-word crop names are removed from symptom words; parts of names such as
        # "Water Melon" must not hide ordinary words like "water" (multi-word crops are found by detect_crops).
        self.crop_tokens = {t for c in self.crops if " " not in c for t in tokens(c)}
        self.categories = sorted(self.kb["Category"].unique())
        self.rules, self.keywords = [], {}
        self._compile()

    # ------------------------------------------------------------------ compile
    def _row_keywords(self, r):
        return sorted(set(tokens(f"{r.Symptoms} {r.Possible_Cause}", self.crop_tokens)))

    def _compile(self):
        df_count = {}
        for i, r in self.rows.items():
            self.keywords[i] = self._row_keywords(r)
            for k in self.keywords[i]:
                df_count[k] = df_count.get(k, 0) + 1
        n = len(self.rows)
        self.idf = {k: math.log(n / v) for k, v in df_count.items()}
        add = self.rules.append
        stage_vocab = set()
        for i, r in self.rows.items():
            add(Rule(f"R1.{i}", () if r.Crop == "All crops" else (f"CROP:{r.Crop}",), f"CROP_OK:{i}", "crop", i))
            if r.Crop != "All crops":
                add(Rule(f"R1b.{i}", ("CROP:ANY",), f"CROP_OK:{i}", "crop", i))
            for k in self.keywords[i]:
                add(Rule(f"R2.{i}.{k}", (f"CROP_OK:{i}", f"SYM:{k}"), f"HIT:{i}", "symptom", i, k))
            add(Rule(f"R3.{i}", (f"CROP_OK:{i}", f"CAT:{r.Category}", "MODE:BROWSE"), f"HIT:{i}", "browse", i))
            add(Rule(f"R4cat.{i}a", (f"CAT:{r.Category}",), f"CAT_OK:{i}", "filter", i))
            add(Rule(f"R4cat.{i}b", ("CAT:ANY",), f"CAT_OK:{i}", "filter", i))
            stage_tokens = {t for t in tokens(r.Growth_Stage) if t not in ("whole", "season", "year")}
            stage_vocab |= stage_tokens
            if not stage_tokens:
                add(Rule(f"R4st.{i}", (), f"STAGE_OK:{i}", "filter", i))
            add(Rule(f"R4st.{i}b", ("STAGE:ANY",), f"STAGE_OK:{i}", "filter", i))
            for s in sorted(stage_tokens):
                add(Rule(f"R4st.{i}.{s}", (f"STAGE:{s}",), f"STAGE_OK:{i}", "filter", i, s))
            add(Rule(f"R4.{i}", (f"HIT:{i}", f"CAT_OK:{i}", f"STAGE_OK:{i}"), f"CAUSE:{i}", "cause", i))
            for out in ("ACTION", "PREVENT", "SOURCE"):
                add(Rule(f"R5.{out}.{i}", (f"CAUSE:{i}",), f"{out}:{i}", "output", i))
            if r.Region_Kind == "all":
                add(Rule(f"R6.{i}", (), f"REGION_MATCH:{i}", "region", i))
            for d in r.Region_Districts:
                add(Rule(f"R6.{i}.{d}", (f"DIST:{d}",), f"REGION_MATCH:{i}", "region", i, d))
        self.stage_options = sorted(stage_vocab)
        # environmental rules (facts come from File 2): they cite KB entries about soil problems
        for i, r in self.rows.items():
            cause = r.Possible_Cause.lower()
            if r.Crop == "All crops" and "sodicity" in cause:
                add(Rule(f"R7.{i}", ("ENV:HIGH_PH",), f"ENVHIT:{i}", "environment", i))
            if r.Crop == "All crops" and "sandy" in cause:
                add(Rule(f"R7.{i}", ("ENV:SANDY_SOIL",), f"ENVHIT:{i}", "environment", i))

    # ------------------------------------------------------------------ inference
    def forward_chain(self, facts):
        """Return (derived_fact_set, fired_rules): fixpoint of modus ponens."""
        known = set(facts)
        changed = True
        while changed:
            changed = False
            for r in self.rules:
                if r.conclusion not in known and all(p in known for p in r.premises):
                    known.add(r.conclusion)
                    changed = True
        fired = [r for r in self.rules if all(p in known for p in r.premises)]
        return known, fired

    # ------------------------------------------------------------------ query -> facts
    def detect_crops(self, text):
        found = []
        for c in self.crops:
            if re.search(r"\b" + re.escape(c.lower()) + r"(e?s)?\b", text.lower()):
                found.append(c)
        return found

    def detect_categories(self, text):
        cats = {CATEGORY_WORDS[w] for w in re.findall(r"[a-z]+", text.lower()) if w in CATEGORY_WORDS}
        cats |= {CATEGORY_WORDS[stem(w)] for w in re.findall(r"[a-z]+", text.lower()) if stem(w) in CATEGORY_WORDS}
        return sorted(cats)

    def build_facts(self, question="", crop=None, categories=(), stage=None, symptoms="", district=None, env=None):
        text = f"{question} {symptoms}"
        crops = [crop] if crop else self.detect_crops(text)
        cats = list(categories) or self.detect_categories(text)
        sym = sorted(set(tokens(text, self.crop_tokens | set(CATEGORY_WORDS))))
        facts = {f"CROP:{c}" for c in crops}
        facts |= {f"CAT:{c}" for c in cats} or {"CAT:ANY"}
        facts.add(f"STAGE:{stem(stage.lower())}" if stage else "STAGE:ANY")
        facts |= {f"SYM:{s}" for s in sym}
        if sym:
            if not crops:
                facts.add("CROP:ANY")                 # symptom-only question: search all crops
        elif cats:
            facts.add("MODE:BROWSE")                  # category browsing for a crop / all-crop entries
        if district:
            facts.add(f"DIST:{district}")
        for k, v in (env or {}).items():
            if v:
                facts.add(f"ENV:{k}")
        return facts, {"crops": crops, "categories": cats, "symptom_words": sym}

    # ------------------------------------------------------------------ answer
    def answer(self, question="", crop=None, categories=(), stage=None, symptoms="", district=None, env=None, top_k=5):
        text = f"{question} {symptoms}"
        facts, parsed = self.build_facts(question, crop, categories, stage, symptoms, district, env)
        base = {"supported": False, "message": "", "matches": [], "env_notes": [], "parsed": parsed,
                "facts": sorted(facts), "n_rules": len(self.rules)}
        if UNSUPPORTED_INTENT.search(text):
            base["message"] = ("This question asks for something the knowledge base does not contain (doses, prices, "
                               "weather, finance or similar). No answer is generated; please consult a local agriculture "
                               "extension officer.")
            return base
        if not parsed["symptom_words"] and not parsed["categories"]:
            base["message"] = ("Not enough information: please select a crop and a category, or describe the symptoms "
                               "or conditions you are seeing.")
            return base
        known, fired = self.forward_chain(facts)
        by_row = {}
        for r in fired:
            by_row.setdefault(r.kb_id, []).append(r)
        for i in sorted(by_row):
            if f"CAUSE:{i}" not in known:
                continue
            row = self.rows[i]
            sym_rules = [r for r in by_row[i] if r.kind == "symptom"]
            matched = sorted(r.key for r in sym_rules)
            ev = sum(self.idf[k] for k in matched)
            browse = any(r.kind == "browse" for r in by_row[i])
            if not browse:
                strong = max((self.idf[k] for k in matched), default=0)
                if not (ev >= MIN_TOTAL_IDF and len(matched) >= 2 or strong >= MIN_STRONG_IDF):
                    continue                       # evidence too weak -> rule is not accepted
            region_ok = f"REGION_MATCH:{i}" in known
            score = (1.0 if browse else ev) + (0.25 if row.Crop != "All crops" else 0) + (0.25 if district and region_ok else 0)
            base["matches"].append({
                "kb_id": i, "crop": row.Crop, "category": row.Category, "stage": row.Growth_Stage,
                "symptoms": row.Symptoms, "cause": row.Possible_Cause, "conditions": row.Relevant_Conditions,
                "action": row.Recommended_Action, "prevention": row.Prevention, "source": row.Source,
                "region": row.Applicable_District_Region, "score": round(score, 2), "matched_words": matched,
                "mode": "category browse" if browse else "symptom match",
                "region_note": ("" if not district or region_ok else
                                f"Note: this KB entry is listed mainly for other districts ({row.Applicable_District_Region}), not {district}."),
                "trace": [str(r) for r in by_row[i] if r.kind in ("crop", "symptom", "browse", "cause", "output")
                          and (r.kind != "crop" or r.premises == () or r.premises[0] in facts)],
            })
        base["matches"].sort(key=lambda m: (-m["score"], m["kb_id"]))
        base["matches"] = base["matches"][:top_k]
        for i in sorted(by_row):                                   # environmental (File 2) rules
            if f"ENVHIT:{i}" in known:
                row = self.rows[i]
                base["env_notes"].append({"kb_id": i, "cause": row.Possible_Cause, "action": row.Recommended_Action,
                                          "source": row.Source, "rule": next(str(r) for r in by_row[i] if r.kind == "environment")})
        if base["matches"]:
            base["supported"] = True
            base["message"] = f"{len(base['matches'])} supported conclusion(s) derived from the knowledge base."
        else:
            kb_note = ""
            if parsed["crops"] and not any(c in self.kb_crops for c in parsed["crops"]):
                kb_note = f" The knowledge base has no entries specific to {', '.join(parsed['crops'])}."
            base["message"] = ("The available knowledge base does not contain enough information to answer this "
                               "question reliably." + kb_note)
        return base
