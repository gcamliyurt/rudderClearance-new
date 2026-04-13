from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _resolve_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def loa_bin(v: float) -> str:
    if pd.isna(v):
        return "unknown"
    x = float(v)
    if x < 100:
        return "<100m"
    if x < 150:
        return "100-149m"
    if x < 200:
        return "150-199m"
    if x < 250:
        return "200-249m"
    return ">=250m"


def pct(s: pd.Series, q: float) -> float:
    y = pd.to_numeric(s, errors="coerce").dropna()
    if y.empty:
        return float("nan")
    return float(np.percentile(y, q))


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    external_64 = root.parent / "6.0 meetingPoint" / "6.4 pilotManuveringTrajectory" / "outputs"

    enriched_csv = root / "outputs/event_clearance_results_enriched.csv"
    mob_csv = _resolve_existing_path(
        external_64 / "mob_analysis_all_events.csv",
        root / "data/imports/6.4/mob_analysis_all_events.csv",
    )

    out_all = root / "outputs/operational_percentiles_all.csv"
    out_group = root / "outputs/operational_percentiles_by_class_loa_side.csv"

    df = pd.read_csv(enriched_csv)
    mob = pd.read_csv(mob_csv, usecols=["event_id", "vessel_ship_type_class", "loa_m", "draft_m", "fall_side"])

    df = df.rename(columns={"scenario_id": "event_id"})
    df = df.merge(mob, on="event_id", how="left")

    # Coalesce potential duplicated columns after merge.
    if "loa_m_x" in df.columns or "loa_m_y" in df.columns:
        loa_x = pd.to_numeric(df["loa_m_x"], errors="coerce") if "loa_m_x" in df.columns else pd.Series(np.nan, index=df.index)
        loa_y = pd.to_numeric(df["loa_m_y"], errors="coerce") if "loa_m_y" in df.columns else pd.Series(np.nan, index=df.index)
        df["loa_m"] = loa_x.fillna(loa_y)
    if "draft_m_x" in df.columns or "draft_m_y" in df.columns:
        dr_x = pd.to_numeric(df["draft_m_x"], errors="coerce") if "draft_m_x" in df.columns else pd.Series(np.nan, index=df.index)
        dr_y = pd.to_numeric(df["draft_m_y"], errors="coerce") if "draft_m_y" in df.columns else pd.Series(np.nan, index=df.index)
        df["draft_m"] = dr_x.fillna(dr_y)
    if "fall_side_x" in df.columns or "fall_side_y" in df.columns:
        fs_x = df["fall_side_x"] if "fall_side_x" in df.columns else pd.Series([None] * len(df), index=df.index)
        fs_y = df["fall_side_y"] if "fall_side_y" in df.columns else pd.Series([None] * len(df), index=df.index)
        df["fall_side"] = fs_x.fillna(fs_y)

    df["tau_clear_s"] = pd.to_numeric(df["tau_clear_s"], errors="coerce")
    df["tau_nonzero_s"] = df["tau_clear_s"].where(df["tau_clear_s"] > 0)
    df["loa_bin"] = df["loa_m"].apply(loa_bin)
    df["fall_side_group"] = df["fall_side"].fillna("unknown").str.lower()
    df["ship_class"] = df["vessel_ship_type_class"].fillna("unknown")

    scopes: list[tuple[str, pd.DataFrame]] = [("analysis_scope", df)]
    if "decision" in df.columns:
        eligible = df[df["decision"] == "ALLOW_WITH_EMERGENCY_PLAN"]
        banned = df[df["decision"] == "BAN"]
        if len(eligible) != len(df):
            scopes.append(("eligible_events", eligible))
        if not banned.empty:
            scopes.append(("banned_events", banned))

    overall = pd.DataFrame([
        {
            "scope": name,
            "n_total": len(g),
            "n_solved": int(g["tau_clear_s"].notna().sum()),
            "n_nonzero": int(g["tau_nonzero_s"].notna().sum()),
            "p10_nonzero_s": pct(g["tau_nonzero_s"], 10),
            "p50_nonzero_s": pct(g["tau_nonzero_s"], 50),
            "p90_nonzero_s": pct(g["tau_nonzero_s"], 90),
            "p95_nonzero_s": pct(g["tau_nonzero_s"], 95),
        }
        for name, g in scopes
    ])

    group_df = df[df["decision"] == "ALLOW_WITH_EMERGENCY_PLAN"].copy() if "decision" in df.columns else df.copy()

    group = (
        group_df.groupby(["ship_class", "loa_bin", "fall_side_group"], dropna=False)
        .apply(
            lambda g: pd.Series(
                {
                    "n_total": len(g),
                    "n_nonzero": int(g["tau_nonzero_s"].notna().sum()),
                    "p10_nonzero_s": pct(g["tau_nonzero_s"], 10),
                    "p50_nonzero_s": pct(g["tau_nonzero_s"], 50),
                    "p90_nonzero_s": pct(g["tau_nonzero_s"], 90),
                    "p95_nonzero_s": pct(g["tau_nonzero_s"], 95),
                    "median_draft_m": float(pd.to_numeric(g["draft_m"], errors="coerce").median()),
                    "median_loa_m": float(pd.to_numeric(g["loa_m"], errors="coerce").median()),
                }
            )
        )
        .reset_index()
        .sort_values(["ship_class", "loa_bin", "fall_side_group"])
    )

    overall.to_csv(out_all, index=False)
    group.to_csv(out_group, index=False)

    print(f"Wrote: {out_all}")
    print(f"Wrote: {out_group}")
    print(overall.to_string(index=False))


if __name__ == "__main__":
    main()
