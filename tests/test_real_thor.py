from pathlib import Path
import json
import pandas as pd


def test_real_thor_processed_contract():
    root = Path(__file__).resolve().parents[1]
    csv_path = root / "data" / "real" / "quang_tri" / "thor_quang_tri_missions.csv"
    summary_path = root / "data" / "real" / "quang_tri" / "thor_quang_tri_summary.json"

    df = pd.read_csv(csv_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    required = {
        "record_x",
        "record_y",
        "record_n_bombs",
        "record_mission_id",
        "recorded_tonnage_t",
    }
    assert required.issubset(df.columns)
    assert len(df) > 0
    assert (df["record_n_bombs"] > 0).all()
    assert (df["recorded_tonnage_t"] > 0).all()

    bbox = summary["study_bbox_wgs84"]
    assert bbox["west"] < bbox["east"]
    assert bbox["south"] < bbox["north"]
    assert summary["raw_target_records_in_demine_bbox"] >= len(df)
