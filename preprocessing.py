"""Data cleaning for the three project datasets (Punjab, Pakistan only).

Nothing here invents data: rows are only standardised, flagged or dropped, and
every drop/flag is counted so it can be reported (see quality_report).
"""
import re
import numpy as np
import pandas as pd

# Crop rows that are *groups* of crops, not single crops -> never planned/allocated.
AGGREGATE_CROPS = {
    "Fodders Total", "Other Rabi Vegetables", "Other Kharif Vegetables",
    "Other Rabi Fruits", "Other Kharif Fruits", "OK Pulses", "OR Pulses",
    "R&M Seed", "Citrus Fruit",
}
_SPECIAL_CROPS = {
    "ok pulses": "OK Pulses", "or pulses": "OR Pulses", "r&m seed": "R&M Seed",
    "canola (r&m seed)": "R&M Seed", "all crops": "All crops",
}
OUTLIER_FACTOR = 5.0   # a district yield > 5 x the Punjab median of that crop is flagged


def normalise_text(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def standardise_crop(name) -> str:
    """'potato' / 'Potato' / 'POTATO' -> 'Potato'; keeps known special labels."""
    n = normalise_text(name)
    return _SPECIAL_CROPS.get(n.lower(), n.title())


def clean_historical(raw: pd.DataFrame) -> pd.DataFrame:
    """Punjab-only filter, name standardisation, placeholder removal."""
    df = raw.copy()
    df["Province"] = df["Province"].map(normalise_text)
    df = df[df["Province"].str.lower() == "punjab"]
    for col in ("District", "Tehsil", "Season"):
        df[col] = df[col].map(normalise_text)
    df["Crop"] = df["Crop"].map(standardise_crop)
    df = df[~df["Crop"].str.lower().str.startswith("unnamed crop")]          # unidentified crops
    df["Year_Start"] = df["Year"].astype(str).str[:4].astype(int)  # '1981-82' -> 1981
    return df.reset_index(drop=True)


def district_crop_year(clean: pd.DataFrame) -> pd.DataFrame:
    """Collapse the (estimated) tehsil rows back to the real resolution: district.

    The tehsil rows are district totals split by Tehsil_Share_Pct, so district
    totals = sum over tehsils. Yield is recomputed as Production / Area_Harvested.
    """
    g = clean.groupby(["District", "Year", "Year_Start", "Crop"], as_index=False).agg(
        Season=("Season", "first"),
        Area_Sown_ha=("Area_Sown", lambda s: s.sum(min_count=1)),
        Area_Harvested_ha=("Area_Harvested", lambda s: s.sum(min_count=1)),
        Production_t=("Production", lambda s: s.sum(min_count=1)),
    )
    ok = (g["Area_Harvested_ha"] > 0) & (g["Production_t"] > 0)
    g["Yield_t_ha"] = np.where(ok, g["Production_t"] / g["Area_Harvested_ha"].where(ok), np.nan)
    crop_median = g.groupby("Crop")["Yield_t_ha"].transform("median")
    g["Outlier"] = g["Yield_t_ha"] > OUTLIER_FACTOR * crop_median
    g["Valid"] = g["Yield_t_ha"].notna() & ~g["Outlier"]
    g["Is_Aggregate"] = g["Crop"].isin(AGGREGATE_CROPS)
    return g


def clean_soil(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df = df[df["Province"].map(normalise_text).str.lower() == "punjab"]
    for col in ("District", "Tehsil", "Soil_Type", "Irrigation_Availability", "Water_Availability"):
        df[col] = df[col].map(normalise_text)
    return df.reset_index(drop=True)


def soil_district_year(soil: pd.DataFrame) -> pd.DataFrame:
    """Tehsil -> district (mean of numeric columns, mode of categorical ones)."""
    num = ["Soil_pH", "Nitrogen", "Phosphorus", "Potassium", "Rainfall", "Temperature", "Humidity"]
    mode = lambda s: s.mode().iat[0]
    return soil.groupby(["District", "Year"], as_index=False).agg(
        **{c: (c, "mean") for c in num},
        Soil_Type=("Soil_Type", mode),
        Irrigation_Availability=("Irrigation_Availability", mode),
        Water_Availability=("Water_Availability", mode),
    )


# ----------------------------------------------------------------- knowledge base
_BELT_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]*?)\s+(?:belt|areas)\s*:", re.I)


def parse_region(text, districts):
    """Return (kind, district_set, belt_crop).

    kind: 'all' | 'belt' | 'main' | 'other'.  belt_crop is set for '<Crop> belt/areas:' strings.
    """
    t = normalise_text(text)
    if t.lower().startswith("all punjab"):
        return "all", set(), None
    found = {d for d in districts if re.search(r"\b" + re.escape(d) + r"\b", t, re.I)}
    m = _BELT_RE.match(t)
    if m:
        return "belt", found, m.group(1).strip().title()
    if t.lower().startswith("main growing"):
        return "main", found, None
    return ("other" if found else "all"), found, None


def clean_kb(raw: pd.DataFrame, districts) -> pd.DataFrame:
    df = raw.loc[:, ~raw.columns.str.startswith("Unnamed")].copy()
    df.insert(0, "KB_ID", range(len(df)))
    df["Crop"] = df["Crop"].map(standardise_crop)
    for col in df.columns:
        if col not in ("KB_ID", "Crop") and not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].map(normalise_text)
    parsed = df["Applicable_District_Region"].map(lambda t: parse_region(t, districts))
    df["Region_Kind"] = parsed.map(lambda p: p[0])
    df["Region_Districts"] = parsed.map(lambda p: sorted(p[1]))
    df["Belt_Crop"] = parsed.map(lambda p: p[2])
    return df


def kb_crop_belts(kb: pd.DataFrame, known_crops=None) -> dict:
    """{crop: set(districts)} from '<Crop> belt/areas: ...' entries (e.g. Cotton belt).

    Labels that are not crops (e.g. 'Riverine', 'Desert Border') are ignored when
    known_crops (the crop names of File 1) is given.
    """
    belts = {}
    for _, r in kb.dropna(subset=["Belt_Crop"]).iterrows():
        if known_crops is not None and r["Belt_Crop"] not in known_crops and r["Belt_Crop"] != "Citrus":
            continue
        belts.setdefault(r["Belt_Crop"], set()).update(r["Region_Districts"])
    if "Citrus" in belts:                       # citrus belt applies to the citrus crops of File 1
        for c in ("Kinno", "Lemon", "Musambi", "Orange", "Sweet Lime", "Grape Fruit"):
            belts.setdefault(c, set()).update(belts["Citrus"])
    return belts


def quality_report(raw_hist, raw_soil, raw_kb) -> dict:
    """Numbers shown on the dashboard / data-audit page (all computed, none hard-coded)."""
    h = raw_hist
    crops_raw = h["Crop"].map(normalise_text)
    crops_std = crops_raw.map(standardise_crop)
    return {
        "hist_rows": len(h), "soil_rows": len(raw_soil), "kb_rows": len(raw_kb),
        "hist_missing": {c: int(v) for c, v in h.isna().sum().items() if v},
        "hist_duplicates": int(h.duplicated().sum()),
        "soil_duplicates": int(raw_soil.duplicated().sum()),
        "kb_duplicates": int(raw_kb.duplicated().sum()),
        "soil_missing_cells": int(raw_soil.isna().sum().sum()),
        "crop_labels_raw": int(crops_raw.nunique()), "crop_labels_clean": int(crops_std.nunique()),
        "placeholder_rows": int(crops_std.str.lower().str.startswith("unnamed crop").sum()),
        "yield_gt_100": int((h["Yield"] > 100).sum()),
        "zero_area_positive_prod": int(((h["Area_Harvested"].fillna(0) == 0) & (h["Production"].fillna(0) > 0)).sum()),
        "estimated_tehsil_rows": int(h["Data_Type"].str.contains("Estimated", na=False).sum()),
        "non_punjab_rows": int((h["Province"].map(normalise_text).str.lower() != "punjab").sum()),
    }
