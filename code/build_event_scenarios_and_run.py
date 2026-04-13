from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

from stern_clearance_model import find_tau_clear, parse_scenarios, write_results


def _resolve_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _is_valid_deg(v: float) -> bool:
    return not math.isnan(v)


def _vector_en_from_course(speed: float, course_deg_cw_from_n: float) -> tuple[float, float]:
    th = math.radians(course_deg_cw_from_n % 360.0)
    v_e = speed * math.sin(th)
    v_n = speed * math.cos(th)
    return v_e, v_n


def _en_to_body(v_e: float, v_n: float, heading_deg_cw_from_n: float) -> tuple[float, float]:
    h = math.radians(heading_deg_cw_from_n % 360.0)
    # x: forward, y: starboard
    x_fwd = v_e * math.sin(h) + v_n * math.cos(h)
    y_stbd = v_e * math.cos(h) - v_n * math.sin(h)
    return x_fwd, y_stbd


def _loading_multipliers(draft_m: float, loa_m: float) -> tuple[float, float, str, float]:
    # Draft-ratio proxy for loading state.
    # Returns (K_multiplier, T_r_multiplier, load_state, draft_ratio)
    ratio = draft_m / max(loa_m, 1.0)
    if ratio < 0.035:
        return 1.10, 0.85, "ballast_like", ratio
    if ratio < 0.050:
        return 1.00, 1.00, "mid_load", ratio
    return 0.90, 1.15, "loaded_like", ratio


def _event_start_from_id(event_id: str) -> pd.Timestamp | None:
    m = re.match(r"^INT_\d+_\d+_(\d{8})_(\d{4})$", str(event_id))
    if not m:
        return None
    d, hm = m.group(1), m.group(2)
    ts = pd.to_datetime(f"{d}{hm}", format="%Y%m%d%H%M", utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def _safe_float(v, default: float) -> float:
    try:
        x = float(v)
        if math.isnan(x):
            return default
        return x
    except Exception:
        return default


def _resolve_fall_side(row: pd.Series) -> tuple[str, str, bool]:
    """Return (normalized_side, source, missing_flag)."""
    candidates = [
        ("fall_side_x", row.get("fall_side_x")),
        ("fall_side_y", row.get("fall_side_y")),
        ("fall_side", row.get("fall_side")),
    ]
    for name, v in candidates:
        if pd.isna(v):
            continue
        s = str(v).strip().lower()
        if not s:
            continue
        if "starboard" in s or s in {"stbd", "sb", "starboard"}:
            return "starboard", name, False
        if "port" in s:
            return "port", name, False

    # Explicit fallback instead of silent behavior.
    return "port", "fallback_missing", True


def build_scenarios(
    mob_csv: Path,
    maneuver_csv: Path,
    output_csv: Path,
    rh_factor: float = 2.5,
    dt_s: float = 0.2,
    t_max_s: float = 180.0,
    eligible_only: bool = True,
) -> pd.DataFrame:
    mob = pd.read_csv(mob_csv)
    man = pd.read_csv(maneuver_csv)
    workspace_root = Path(__file__).resolve().parents[1]
    project_root = workspace_root.parent
    external_60 = project_root / "6.0 meetingPoint" / "pilot_boat_analysis"

    mob["meeting_time"] = pd.to_datetime(mob["meeting_time"], utc=True, errors="coerce")
    mob["event_start_time"] = mob["event_id"].apply(_event_start_from_id)

    man["timestamp"] = pd.to_datetime(man["timestamp"], utc=True, errors="coerce")
    man = man.rename(columns={"mother_mmsi": "vessel_mmsi"})

    mob["vessel_mmsi"] = mob["vessel_mmsi"].astype("string")
    man["vessel_mmsi"] = man["vessel_mmsi"].astype("string")

    metocean_csv = _resolve_existing_path(
        external_60 / "Extra supported documents" / "weather_tides_merged_and_smart_interpolated.csv",
        external_60 / "Sample_data_&_trial_codes" / "dataSet" / "weather_data" / "weather_tides_merged_and_smart_interpolated.csv",
    )
    metocean = pd.read_csv(metocean_csv)
    metocean["Date_Time"] = pd.to_datetime(metocean["Date_Time"], errors="coerce", utc=True)
    metocean = metocean.rename(
        columns={
            "Date_Time": "metocean_time_bridge",
            "Wind_Speed_mps": "wind_speed_mps_bridge",
            "Wind_Direction_deg": "wind_dir_deg_bridge",
            "Gust_Speed_mps": "gust_speed_mps_bridge",
            "Significant_Wave_Height_m": "wave_height_m_bridge",
            "Wave_Period_sec": "wave_period_sec_bridge",
            "Wave_Direction_deg": "wave_dir_deg_bridge",
            "Height (m)": "tide_height_m_bridge",
        }
    )
    metocean = metocean.sort_values("metocean_time_bridge").reset_index(drop=True)

    interaction_root = external_60 / "data" / "processed" / "interactions"
    context_frames = []
    for f in sorted(interaction_root.glob("event_context_enriched_*geometry_v2_nopilotcollision.csv")):
        try:
            df = pd.read_csv(
                f,
                usecols=[
                    "event_id",
                    "wind_speed_mps",
                    "wind_dir_deg",
                    "wave_height_m",
                    "tide_height_m",
                    "visibility_km",
                ],
            )
            context_frames.append(df)
        except Exception:
            continue
    event_context = pd.concat(context_frames, ignore_index=True).drop_duplicates(subset=["event_id"]) if context_frames else pd.DataFrame()

    # Keep smallest payload for join operations.
    man2 = man[[
        "timestamp",
        "vessel_mmsi",
        "emergency_delta_deg",
        "propeller_clearance_time_s",
        "fall_side",
    ]].copy()

    mob = mob.dropna(subset=["meeting_time", "vessel_mmsi"]).copy()
    man2 = man2.dropna(subset=["timestamp", "vessel_mmsi"]).copy()

    mob = mob.sort_values(["meeting_time", "vessel_mmsi"]).reset_index(drop=True)
    man2 = man2.sort_values(["timestamp", "vessel_mmsi"]).reset_index(drop=True)

    # Nearest-time join by vessel MMSI to obtain event-specific rudder angle.
    merged = pd.merge_asof(
        mob,
        man2,
        left_on="meeting_time",
        right_on="timestamp",
        by="vessel_mmsi",
        direction="nearest",
        tolerance=pd.Timedelta("12h"),
    )
    merged = pd.merge_asof(
        merged.sort_values("meeting_time"),
        metocean,
        left_on="meeting_time",
        right_on="metocean_time_bridge",
        direction="nearest",
        tolerance=pd.Timedelta("2h"),
    ).sort_values("meeting_time").reset_index(drop=True)
    if not event_context.empty:
        merged = merged.merge(event_context, on="event_id", how="left", suffixes=("", "_ctx"))

    merged["maneuver_match_found"] = merged["timestamp"].notna()
    if merged["maneuver_match_found"].any():
        dt_h = (
            merged.loc[merged["maneuver_match_found"], "meeting_time"]
            - merged.loc[merged["maneuver_match_found"], "timestamp"]
        ).abs().dt.total_seconds() / 3600.0
        merged.loc[merged["maneuver_match_found"], "maneuver_match_abs_hours"] = dt_h
    else:
        merged["maneuver_match_abs_hours"] = math.nan

    rows = []
    for _, r in merged.iterrows():
        event_id = str(r["event_id"])
        decision = str(r.get("decision") or "")
        ban_reason = str(r.get("ban_reason") or "")

        if eligible_only and decision != "ALLOW_WITH_EMERGENCY_PLAN":
            continue

        loa = _safe_float(r.get("loa_m"), 150.0)
        loa = min(400.0, max(60.0, loa))

        beam = _safe_float(r.get("beam_m"), 24.0)
        beam = min(70.0, max(8.0, beam))

        dim_b = _safe_float(r.get("dim_b_m"), max(0.12 * loa, 10.0))
        dim_b = min(0.30 * loa, max(6.0, dim_b))
        sog_kn = _safe_float(r.get("vessel_sog_kn"), 5.0)
        draft_m = _safe_float(r.get("draft_m"), 7.0)
        turn_r_raw = _safe_float(r.get("turning_radius_m"), float("nan"))
        turn_r_default_used = math.isnan(turn_r_raw) or turn_r_raw <= 0.0
        turn_r = 2.5 * loa if turn_r_default_used else turn_r_raw

        # Rudder angle from maneuver file if available, else hard-over default.
        matched_delta = _safe_float(r.get("emergency_delta_deg"), -1.0)
        delta_source = "matched_maneuver_plan" if matched_delta > 0.0 else "default_hardover_fallback"
        delta_deg = 35.0 if matched_delta <= 0.0 else matched_delta
        if delta_deg <= 0:
            delta_deg = 35.0
        delta_max_deg = 35.0
        delta_deg = min(delta_deg, delta_max_deg)

        # Ship-response heuristics (can be replaced by calibrated values later).
        v_mps = max(0.2, sog_kn * 0.514444)
        r_inf = max(0.001, v_mps / max(turn_r, 20.0))
        k = max(0.005, r_inf / max(math.radians(delta_deg), math.radians(10.0)))
        t_r_s = min(25.0, max(4.0, 0.65 * loa / max(v_mps, 0.5)))

        k_mul, tr_mul, load_state, draft_ratio = _loading_multipliers(draft_m, loa)
        k = max(0.003, k * k_mul)
        t_r_s = min(35.0, max(3.0, t_r_s * tr_mul))

        # Geometry assumptions.
        x_s_m = max(8.0, min(0.30 * loa, dim_b + 5.0))
        # Deliberate fixed stern lever-arm fraction for baseline geometry.
        l_s_m = 0.65 * loa

        # Casualty side and initial body-fixed coordinates.
        # Pilot transfer is assumed around midship (user requirement).
        side, side_source, side_missing = _resolve_fall_side(r)
        yc0_mag = max(beam / 2.0 + 1.5, 4.0)
        yc0 = yc0_mag if "starboard" in side else -yc0_mag
        xc0 = 0.0

        # Drift and relative approach in ship-fixed frame.
        # 1) Surge-relative effect: casualty moves aft in body frame as vessel keeps way on.
        uc_rel_mps = -0.90 * v_mps

        # 2) Environment vector terms projected into body frame.
        #    - Current: explicit if available.
        #    - Wind: leeway proxy (1.5% of true wind speed), with wind direction treated as
        #      meteorological "from" direction -> converted to drift "to" direction.
        #    - Wave: Stokes-drift proxy proportional to significant wave height.
        vessel_cog_deg = _safe_float(r.get("vessel_cog_deg"), 0.0)

        current_speed_mps = _safe_float(r.get("current_speed_mps"), 0.0)
        current_dir_deg = _safe_float(r.get("current_dir_deg"), float("nan"))

        wind = _safe_float(r.get("wind_speed_mps"), _safe_float(r.get("wind_speed_mps_bridge"), 0.0))
        if pd.notna(r.get("wind_speed_mps_ctx")):
            wind = _safe_float(r.get("wind_speed_mps_ctx"), wind)

        wind_dir_from_deg = _safe_float(r.get("wind_dir_deg"), _safe_float(r.get("wind_dir_deg_bridge"), float("nan")))
        if pd.notna(r.get("wind_dir_deg_ctx")):
            wind_dir_from_deg = _safe_float(r.get("wind_dir_deg_ctx"), wind_dir_from_deg)
        wind_leeway_mps = min(0.60, 0.015 * max(0.0, wind))

        wave_height_m = _safe_float(r.get("wave_height_m"), _safe_float(r.get("wave_height_m_bridge"), 0.0))
        if pd.notna(r.get("wave_height_m_ctx")):
            wave_height_m = _safe_float(r.get("wave_height_m_ctx"), wave_height_m)

        wave_dir_deg = _safe_float(r.get("wave_dir_deg"), _safe_float(r.get("wave_dir_deg_bridge"), float("nan")))
        wave_period_sec = _safe_float(r.get("wave_period_sec_bridge"), _safe_float(r.get("wave_period_sec"), float("nan")))
        # Conservative Stokes-drift proxy used for sensitivity-safe baseline.
        wave_drift_factor = 0.10
        wave_drift_mps = min(0.35, wave_drift_factor * max(0.0, wave_height_m))

        tide_height_m = _safe_float(r.get("tide_height_m"), _safe_float(r.get("tide_height_m_bridge"), float("nan")))
        if pd.notna(r.get("tide_height_m_ctx")):
            tide_height_m = _safe_float(r.get("tide_height_m_ctx"), tide_height_m)

        u_env = 0.0
        v_env = 0.0

        if current_speed_mps > 0.0 and _is_valid_deg(current_dir_deg):
            ce, cn = _vector_en_from_course(current_speed_mps, current_dir_deg)
            ux, vy = _en_to_body(ce, cn, vessel_cog_deg)
            u_env += ux
            v_env += vy

        if wind_leeway_mps > 0.0 and _is_valid_deg(wind_dir_from_deg):
            wind_to_deg = (wind_dir_from_deg + 180.0) % 360.0
            we, wn = _vector_en_from_course(wind_leeway_mps, wind_to_deg)
            ux, vy = _en_to_body(we, wn, vessel_cog_deg)
            u_env += ux
            v_env += vy

        if wave_drift_mps > 0.0 and _is_valid_deg(wave_dir_deg):
            # Assumption: wave_dir_deg already represents propagation direction.
            ae, an = _vector_en_from_course(wave_drift_mps, wave_dir_deg)
            ux, vy = _en_to_body(ae, an, vessel_cog_deg)
            u_env += ux
            v_env += vy

        uc_mps = uc_rel_mps + u_env
        vc_mps = v_env

        # 3) Human + steering system delay terms.
        #    Baseline is a high-readiness bridge assumption; can be overridden from data.
        t_detect_report_s = _safe_float(r.get("t_detect_report_s"), 1.0)
        t_master_decide_s = _safe_float(r.get("t_master_decide_s"), 1.5)
        t_order_helm_s = _safe_float(r.get("t_order_helm_s"), 0.8)
        t_helmsman_ack_s = _safe_float(r.get("t_helmsman_ack_s"), 1.2)
        t_response_s = _safe_float(
            r.get("t_response_s"),
            t_detect_report_s + t_master_decide_s + t_order_helm_s + t_helmsman_ack_s,
        )

        # IMO/SOLAS steering-gear benchmark proxy:
        # 35 deg on one side to 30 deg on the other in <= 28 s.
        # Assuming near-constant average rudder rate, midship to 35 deg is about 15.1 s.
        t_rudder_s = 35.0 * 28.0 / 65.0

        # Propeller hazard radius estimate from LOA-based propeller diameter proxy.
        # D_p ~= 0.045*LOA, R_h = rh_factor * D_p
        d_p = max(3.0, 0.045 * loa)
        r_h = max(6.0, rh_factor * d_p)

        rows.append(
            {
                "scenario_id": event_id,
                "decision": decision,
                "ban_reason": ban_reason,
                "fall_side": side,
                "fall_side_source": side_source,
                "fall_side_missing": side_missing,
                "K": round(k, 6),
                "T_r_s": round(t_r_s, 3),
                "turning_radius_m": round(turn_r, 3),
                "turning_radius_default_used": bool(turn_r_default_used),
                "delta_deg": round(delta_deg, 2),
                "delta_source": delta_source,
                "maneuver_match_found": bool(r.get("maneuver_match_found", False)),
                "maneuver_match_abs_hours": round(_safe_float(r.get("maneuver_match_abs_hours"), math.nan), 3),
                "l_s_m": round(l_s_m, 2),
                "x_s_m": round(x_s_m, 2),
                "xc0_m": round(xc0, 2),
                "yc0_m": round(yc0, 2),
                "uc_mps": round(uc_mps, 3),
                "vc_mps": round(vc_mps, 3),
                "R_h_m": round(r_h, 2),
                "current_active": bool(current_speed_mps > 0.0 and _is_valid_deg(current_dir_deg)),
                "wind_active": bool(wind_leeway_mps > 0.0 and _is_valid_deg(wind_dir_from_deg)),
                "wave_active": bool(wave_drift_mps > 0.0 and _is_valid_deg(wave_dir_deg)),
                "metocean_bridge_found": pd.notna(r.get("metocean_time_bridge")),
                "event_context_bridge_found": pd.notna(r.get("wind_speed_mps_ctx")) or pd.notna(r.get("wave_height_m_ctx")),
                "delta_max_deg": delta_max_deg,
                "t_detect_report_s": round(t_detect_report_s, 3),
                "t_master_decide_s": round(t_master_decide_s, 3),
                "t_order_helm_s": round(t_order_helm_s, 3),
                "t_helmsman_ack_s": round(t_helmsman_ack_s, 3),
                "t_response_s": round(t_response_s, 2),
                "t_rudder_s": round(t_rudder_s, 2),
                "draft_m": round(draft_m, 2),
                "draft_ratio": round(draft_ratio, 5),
                "load_state": load_state,
                "K_multiplier": round(k_mul, 3),
                "T_r_multiplier": round(tr_mul, 3),
                "vessel_sog_kn": round(sog_kn, 3),
                "vessel_cog_deg": round(vessel_cog_deg, 3),
                "current_speed_mps": round(current_speed_mps, 3),
                "current_dir_deg": current_dir_deg,
                "wind_speed_mps": round(wind, 3),
                "wind_dir_deg": wind_dir_from_deg,
                "wave_height_m": wave_height_m,
                "wave_drift_factor": wave_drift_factor,
                "wave_period_sec": wave_period_sec,
                "wave_dir_deg": wave_dir_deg,
                "tide_height_m": tide_height_m,
                "t_max_s": t_max_s,
                "dt_s": dt_s,
            }
        )

    scenario_df = pd.DataFrame(rows)
    scenario_df.to_csv(output_csv, index=False)
    return scenario_df


def run_batch(scenario_csv: Path, results_csv: Path) -> pd.DataFrame:
    scenarios = parse_scenarios(scenario_csv)
    results = [find_tau_clear(s) for s in scenarios]
    write_results(results, results_csv)
    return pd.read_csv(results_csv)


def write_source_coverage_summary(
    root: Path,
    mob_csv: Path,
    maneuver_csv: Path,
    summary_csv: Path,
) -> None:
    rows: list[dict[str, object]] = []

    def add_row(source_name: str, path: Path, n_rows: int | None = None) -> None:
        rows.append(
            {
                "source_name": source_name,
                "path": str(path),
                "exists": path.exists(),
                "n_rows": n_rows,
            }
        )

    project_root = root.parent
    external_60 = project_root / "6.0 meetingPoint" / "pilot_boat_analysis"
    external_61 = project_root / "6.1. shipDomain"

    p60_exchange = external_60 / "exchange_points_cleaned.csv"
    p61_prox = external_61 / "pilot_boat_proximity_events.csv"
    p61_sessions = external_61 / "pilot_boat_assistance_sessions.csv"

    for name, path in [
        ("6.0_exchange_points", p60_exchange),
        ("6.1_proximity_events", p61_prox),
        ("6.1_assistance_sessions", p61_sessions),
        ("6.2_prototype_event_file", mob_csv),
        ("6.2_prototype_maneuver_file", maneuver_csv),
    ]:
        n_rows = None
        if path.exists():
            try:
                n_rows = int(sum(1 for _ in path.open("r", encoding="utf-8")) - 1)
            except Exception:
                n_rows = None
        add_row(name, path, n_rows)

    mob = None
    try:
        mob = pd.read_csv(mob_csv, usecols=["event_id", "meeting_time", "vessel_mmsi", "decision"])
        mob["meeting_time"] = pd.to_datetime(mob["meeting_time"], utc=True, errors="coerce")
        mob["vessel_mmsi"] = mob["vessel_mmsi"].astype("Int64").astype(str)
        eligible = mob[mob["decision"] == "ALLOW_WITH_EMERGENCY_PLAN"].copy()
        add_row("6.2_eligible_event_subset", mob_csv, int(len(eligible)))
    except Exception:
        eligible = None

    if eligible is not None:
        try:
            scenarios = pd.read_csv(root / "data" / "event_scenarios_from_6_4.csv")
            if "metocean_bridge_found" in scenarios.columns:
                add_row("6.0_metocean_bridge_to_6.2_eligible", mob_csv, int(scenarios["metocean_bridge_found"].sum()))
            if "event_context_bridge_found" in scenarios.columns:
                add_row("6.0_event_context_bridge_to_6.2_eligible", mob_csv, int(scenarios["event_context_bridge_found"].sum()))
        except Exception:
            pass

        try:
            prox = pd.read_csv(
                p61_prox,
                usecols=["timestamp", "vessel_mmsi"],
            )
            prox["timestamp"] = pd.to_datetime(prox["timestamp"], utc=True, errors="coerce")
            prox["vessel_mmsi"] = prox["vessel_mmsi"].astype("Int64").astype(str)
            merged = pd.merge_asof(
                eligible.sort_values("meeting_time"),
                prox.sort_values("timestamp"),
                left_on="meeting_time",
                right_on="timestamp",
                by="vessel_mmsi",
                direction="nearest",
                tolerance=pd.Timedelta("10min"),
            )
            add_row("6.1_overlap_with_6.2_eligible_within_10min", p61_prox, int(merged["timestamp"].notna().sum()))
        except Exception:
            pass

        try:
            sessions = pd.read_csv(
                p61_sessions,
                usecols=["vessel_mmsi", "start_time", "end_time"],
            )
            sessions["start_time"] = pd.to_datetime(sessions["start_time"], utc=True, errors="coerce")
            sessions["end_time"] = pd.to_datetime(sessions["end_time"], utc=True, errors="coerce")
            sessions["vessel_mmsi"] = sessions["vessel_mmsi"].astype("Int64").astype(str)
            merged = eligible.merge(sessions, on="vessel_mmsi", how="left")
            contained = merged[
                (merged["meeting_time"] >= merged["start_time"])
                & (merged["meeting_time"] <= merged["end_time"])
            ]
            add_row("6.1_session_overlap_with_6.2_eligible", p61_sessions, int(contained["event_id"].nunique()))
        except Exception:
            pass

    summary = pd.DataFrame(rows)
    summary.to_csv(summary_csv, index=False)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    external_64 = root.parent / "6.0 meetingPoint" / "6.4 pilotManuveringTrajectory" / "outputs"

    mob_csv = _resolve_existing_path(
        external_64 / "mob_analysis_all_events.csv",
        root / "data/imports/6.4/mob_analysis_all_events.csv",
    )
    maneuver_csv = _resolve_existing_path(
        external_64 / "maneuver_plan_per_event.csv",
        root / "data/imports/6.4/maneuver_plan_per_event.csv",
    )

    scenarios_csv = root / "data/event_scenarios_from_6_4.csv"
    results_csv = root / "outputs/event_clearance_results.csv"
    merged_csv = root / "outputs/event_clearance_results_enriched.csv"
    source_summary_csv = root / "outputs/source_data_coverage_summary.csv"

    scenario_df = build_scenarios(mob_csv, maneuver_csv, scenarios_csv)
    result_df = run_batch(scenarios_csv, results_csv)
    write_source_coverage_summary(root, mob_csv, maneuver_csv, source_summary_csv)

    enriched = scenario_df.merge(result_df, on="scenario_id", how="left")
    enriched["tau_clear_s"] = pd.to_numeric(enriched["tau_clear_s"], errors="coerce")

    enriched.to_csv(merged_csv, index=False)

    n_total = len(enriched)
    n_ok = enriched["tau_clear_s"].notna().sum()
    med_tau = enriched["tau_clear_s"].median()
    matched_count = int(enriched["maneuver_match_found"].fillna(False).sum()) if "maneuver_match_found" in enriched.columns else 0

    print(f"Scenarios built: {n_total}")
    print(f"Clearance solved: {n_ok}")
    print(f"Maneuver-plan matches used: {matched_count}")
    print(f"Median tau_clear [s]: {med_tau:.2f}" if pd.notna(med_tau) else "Median tau_clear [s]: n/a")
    print(f"Scenario table: {scenarios_csv}")
    print(f"Batch results : {results_csv}")
    print(f"Enriched file : {merged_csv}")
    print(f"Source summary: {source_summary_csv}")


if __name__ == "__main__":
    main()
