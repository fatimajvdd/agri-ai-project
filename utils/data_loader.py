"""Loads and cleans all three datasets. The CSV files are the source of truth."""
from pathlib import Path
import pandas as pd
from utils import preprocessing as pp

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FILES = {
    "hist": "historical_crop_data.csv",
    "soil": "soil_environmental_data.csv",
    "kb": "agricultural_knowledge_base.csv",
}


def load_all(data_dir=None) -> dict:
    d = Path(data_dir) if data_dir else DATA_DIR
    for name in FILES.values():
        if not (d / name).exists():
            raise FileNotFoundError(f"Missing dataset file: {d / name}")
    raw_hist = pd.read_csv(d / FILES["hist"])
    raw_soil = pd.read_csv(d / FILES["soil"])
    raw_kb = pd.read_csv(d / FILES["kb"])

    hist_clean = pp.clean_historical(raw_hist)
    table = pp.district_crop_year(hist_clean)
    soil_clean = pp.clean_soil(raw_soil)
    districts = sorted(table["District"].unique())
    kb = pp.clean_kb(raw_kb, districts)
    return {
        "table": table,                                   # district x year x crop
        "soil": pp.soil_district_year(soil_clean),        # district x year
        "kb": kb,
        "belts": pp.kb_crop_belts(kb, set(table["Crop"])),
        "districts": districts,
        "quality": pp.quality_report(raw_hist, raw_soil, raw_kb),
    }


def match_report(data: dict) -> dict:
    """How well the three datasets connect (reported in the audit)."""
    t, s, kb = data["table"], data["soil"], data["kb"]
    th = set(zip(t["District"], t["Year_Start"]))
    ss = set(zip(s["District"], s["Year"]))
    kb_crops = set(kb["Crop"]) - {"All crops"}
    hist_crops = set(t["Crop"])
    return {
        "district_year_keys_hist": len(th), "matched_in_soil": len(th & ss),
        "districts_hist_only": sorted(set(t["District"]) - set(s["District"])),
        "districts_soil_only": sorted(set(s["District"]) - set(t["District"])),
        "kb_crops_without_hist": sorted(kb_crops - hist_crops),
        "hist_crops_with_kb": len(hist_crops & kb_crops), "hist_crops_total": len(hist_crops),
    }
