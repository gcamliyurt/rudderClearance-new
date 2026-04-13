from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class Scenario:
    scenario_id: str
    K: float
    T_r_s: float
    delta_deg: float
    l_s_m: float
    x_s_m: float
    xc0_m: float
    yc0_m: float
    uc_mps: float
    vc_mps: float
    R_h_m: float
    t_response_s: float = 0.0
    t_rudder_s: float = 0.0
    t_max_s: float = 120.0
    dt_s: float = 0.1


@dataclass
class Result:
    scenario_id: str
    tau_clear_s: Optional[float]
    psi_clear_deg: Optional[float]
    distance_at_t0_m: float
    status: str
    entered_hazard: bool
    n_entries: int
    n_exits: int


def effective_delta_rad(t: float, sc: Scenario) -> float:
    delta_cmd = math.radians(sc.delta_deg)
    if t <= sc.t_response_s:
        return 0.0
    if sc.t_rudder_s <= 1e-9:
        return delta_cmd
    dt = t - sc.t_response_s
    if dt >= sc.t_rudder_s:
        return delta_cmd
    return delta_cmd * (dt / sc.t_rudder_s)


def _state_at_time(t: float, sc: Scenario) -> tuple[float, float, float, float]:
    """Return (x_p, y_p, psi, r) at time t using the same discrete dynamics as find_tau_clear()."""
    if t <= 0.0:
        return -sc.x_s_m, 0.0, 0.0, 0.0

    dt = max(0.01, sc.dt_s)
    psi = 0.0
    r = 0.0
    x_p = -sc.x_s_m
    y_p = 0.0

    tt = 0.0
    while tt < t - 1e-12:
        step = min(dt, t - tt)
        tt += step

        delta_eff = effective_delta_rad(tt, sc)
        r_dot = (sc.K * delta_eff - r) / max(sc.T_r_s, 1e-6)
        r += r_dot * step
        psi += r * step

        x_p = -sc.x_s_m + sc.l_s_m * (1.0 - math.cos(psi))
        y_p = -sc.l_s_m * math.sin(psi)

    return x_p, y_p, psi, r


def propeller_center(t: float, sc: Scenario) -> tuple[float, float, float]:
    # Diagnostics helper; intentionally uses the same delayed/ramped discrete dynamics as find_tau_clear().
    x_p, y_p, psi, _ = _state_at_time(t, sc)
    return x_p, y_p, psi


def casualty_position(t: float, sc: Scenario) -> tuple[float, float]:
    return sc.xc0_m + sc.uc_mps * t, sc.yc0_m + sc.vc_mps * t


def distance_cp(t: float, sc: Scenario) -> tuple[float, float]:
    x_c, y_c = casualty_position(t, sc)
    x_p, y_p, psi = propeller_center(t, sc)
    d = math.hypot(x_c - x_p, y_c - y_p)
    return d, psi


def find_tau_clear(sc: Scenario) -> Result:
    dt = max(0.01, sc.dt_s)

    psi = 0.0
    r = 0.0

    x_p = -sc.x_s_m
    y_p = 0.0
    x_c = sc.xc0_m
    y_c = sc.yc0_m
    d0 = math.hypot(x_c - x_p, y_c - y_p)

    inside_prev = d0 < sc.R_h_m
    ever_inside = inside_prev
    n_entries = 1 if inside_prev else 0
    n_exits = 0

    t = 0.0
    while t <= sc.t_max_s + 1e-12:
        t += dt

        delta_eff = effective_delta_rad(t, sc)
        r_dot = (sc.K * delta_eff - r) / max(sc.T_r_s, 1e-6)
        r += r_dot * dt
        psi += r * dt

        x_p = -sc.x_s_m + sc.l_s_m * (1.0 - math.cos(psi))
        y_p = -sc.l_s_m * math.sin(psi)

        x_c = sc.xc0_m + sc.uc_mps * t
        y_c = sc.yc0_m + sc.vc_mps * t

        d = math.hypot(x_c - x_p, y_c - y_p)
        inside_now = d < sc.R_h_m
        if not inside_prev and inside_now:
            n_entries += 1
        if inside_prev and not inside_now:
            n_exits += 1
        ever_inside = ever_inside or inside_now

        # Safety convention: return first outward crossing after any hazard entry.
        if inside_prev and not inside_now:
            return Result(
                sc.scenario_id,
                t,
                math.degrees(psi),
                d0,
                "cleared_after_entry",
                True,
                n_entries,
                n_exits,
            )

        inside_prev = inside_now

    if not ever_inside:
        return Result(sc.scenario_id, 0.0, 0.0, d0, "never_entered", False, n_entries, n_exits)

    return Result(sc.scenario_id, None, None, d0, "entered_no_clear", True, n_entries, n_exits)


def parse_scenarios(csv_path: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenarios.append(
                Scenario(
                    scenario_id=row["scenario_id"],
                    K=float(row["K"]),
                    T_r_s=float(row["T_r_s"]),
                    delta_deg=float(row["delta_deg"]),
                    l_s_m=float(row["l_s_m"]),
                    x_s_m=float(row["x_s_m"]),
                    xc0_m=float(row["xc0_m"]),
                    yc0_m=float(row["yc0_m"]),
                    uc_mps=float(row["uc_mps"]),
                    vc_mps=float(row["vc_mps"]),
                    R_h_m=float(row["R_h_m"]),
                    t_response_s=float(row.get("t_response_s", 0.0) or 0.0),
                    t_rudder_s=float(row.get("t_rudder_s", 0.0) or 0.0),
                    t_max_s=float(row.get("t_max_s", 120.0) or 120.0),
                    dt_s=float(row.get("dt_s", 0.1) or 0.1),
                )
            )
    return scenarios


def write_results(results: Iterable[Result], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "scenario_id",
            "tau_clear_s",
            "psi_clear_deg",
            "distance_at_t0_m",
            "status",
            "entered_hazard",
            "n_entries",
            "n_exits",
        ])
        for r in results:
            writer.writerow([
                r.scenario_id,
                "" if r.tau_clear_s is None else f"{r.tau_clear_s:.3f}",
                "" if r.psi_clear_deg is None else f"{r.psi_clear_deg:.3f}",
                f"{r.distance_at_t0_m:.3f}",
                r.status,
                int(r.entered_hazard),
                r.n_entries,
                r.n_exits,
            ])


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute MOB stern clearance time for scenarios.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/example_scenarios.csv"),
        help="Scenario CSV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/clearance_results.csv"),
        help="Output CSV file",
    )
    args = parser.parse_args()

    scenarios = parse_scenarios(args.input)
    results = [find_tau_clear(sc) for sc in scenarios]
    write_results(results, args.output)

    for r in results:
        if r.tau_clear_s is None:
            print(f"[{r.scenario_id}] no clearance within simulation window")
        else:
            print(
                f"[{r.scenario_id}] tau_clear={r.tau_clear_s:.2f} s, "
                f"psi_clear={r.psi_clear_deg:.2f} deg"
            )


if __name__ == "__main__":
    main()
