from __future__ import annotations

import argparse
import csv
import math
import warnings
from pathlib import Path
from typing import Optional

import numpy as np


def fit_first_order_rot(time_s: list[float], rot_rad_s: list[float]) -> tuple[float, float]:
    """
    Fit r(t)=r_inf*(1-exp(-t/T_r)) using log-linearization.

    Returns
    -------
    r_inf : float
        Asymptotic yaw rate [rad/s]
    T_r : float
        Response time constant [s]
    """
    if len(time_s) != len(rot_rad_s) or len(time_s) < 5:
        raise ValueError("Need at least 5 paired time/ROT samples.")

    idx_max = max(range(len(rot_rad_s)), key=lambda i: rot_rad_s[i])
    r_inf = rot_rad_s[idx_max]
    if r_inf <= 0.0:
        raise ValueError("ROT must become positive for this simple fit method.")
    if idx_max < len(rot_rad_s) - 1:
        warnings.warn(
            "Max ROT occurs before end of series; steady-state may not be reached and T_r can be biased.",
            RuntimeWarning,
        )

    t_arr = np.array(time_s, dtype=float)
    r_arr = np.array(rot_rad_s, dtype=float)

    # Prefer nonlinear least squares when SciPy is available.
    try:
        from scipy.optimize import curve_fit  # type: ignore

        def _model(t: np.ndarray, r_inf_: float, t_r_: float) -> np.ndarray:
            return r_inf_ * (1.0 - np.exp(-t / max(t_r_, 1e-6)))

        p0 = [max(r_arr), max(1.0, 0.3 * max(t_arr))]
        bounds = ([1e-6, 1e-3], [10.0 * max(r_arr), 1e5])
        popt, _ = curve_fit(_model, t_arr, r_arr, p0=p0, bounds=bounds, maxfev=20000)
        r_inf_nl, t_r_nl = float(popt[0]), float(popt[1])
        if r_inf_nl > 0.0 and t_r_nl > 0.0:
            return r_inf_nl, t_r_nl
    except Exception:
        pass

    # Fallback: original log-linearization method.
    xs: list[float] = []
    ys: list[float] = []

    for t, r in zip(time_s, rot_rad_s):
        frac = 1.0 - (r / r_inf)
        if t <= 0.0 or frac <= 0.0:
            continue
        xs.append(t)
        ys.append(math.log(frac))

    if len(xs) < 3:
        raise ValueError("Not enough valid points for fit.")

    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        raise ValueError("Degenerate data for regression.")

    slope = (n * sxy - sx * sy) / denom  # expected negative
    if slope >= 0.0:
        raise ValueError("Invalid slope; check whether ROT data is first-order-like.")

    T_r = -1.0 / slope
    return r_inf, T_r


def read_rot_csv(path: Path) -> tuple[list[float], list[float]]:
    time_s: list[float] = []
    rot_rad_s: list[float] = []

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            time_s.append(float(row["time_s"]))
            rot_rad_s.append(float(row["rot_rad_s"]))

    return time_s, rot_rad_s


def estimate_K(r_inf: float, delta_deg: float) -> Optional[float]:
    delta_rad = math.radians(delta_deg)
    if abs(delta_rad) < 1e-12:
        return None
    return r_inf / delta_rad


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate first-order yaw model from ROT data.")
    parser.add_argument("--input", type=Path, required=True, help="CSV with columns: time_s,rot_rad_s")
    parser.add_argument("--delta-deg", type=float, required=True, help="Applied rudder angle [deg]")
    args = parser.parse_args()

    t, r = read_rot_csv(args.input)
    r_inf, T_r = fit_first_order_rot(t, r)
    K = estimate_K(r_inf, args.delta_deg)

    print(f"Estimated r_inf [rad/s] : {r_inf:.6f}")
    print(f"Estimated T_r [s]       : {T_r:.3f}")
    if K is None:
        print("Estimated K [1/s/rad]   : undefined (delta=0)")
    else:
        print(f"Estimated K [1/s/rad]   : {K:.6f}")


if __name__ == "__main__":
    main()
