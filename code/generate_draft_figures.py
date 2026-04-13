from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import pandas as pd

from stern_clearance_model import find_tau_clear, parse_scenarios


def _resolve_existing_path(*candidates: Path) -> Path:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _style():
    plt.rcParams.update(
        {
            "figure.dpi": 160,
            "savefig.dpi": 300,
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.labelsize": 10,
        }
    )


def _save(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def fig1_research_flow(out: Path):
    fig, ax = plt.subplots(figsize=(12.0, 2.9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    stages = [
        ("1", "Problem framing"),
        ("2", "Variable design"),
        ("3", "Event-wise scenarios"),
        ("4", "Batch simulation"),
        ("5", "Percentile guidance"),
    ]
    xs = np.linspace(0.10, 0.90, len(stages))
    y = 0.52
    w, h = 0.155, 0.22

    for i, (x, (idx, txt)) in enumerate(zip(xs, stages)):
        card = patches.FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.015",
            linewidth=1.1,
            edgecolor="#334155",
            facecolor="#f8fafc",
        )
        ax.add_patch(card)
        ax.text(x, y + 0.05, f"Step {idx}", ha="center", va="center", fontsize=8.6, color="#475569")
        ax.text(x, y - 0.01, txt, ha="center", va="center", fontsize=9.2, color="#0f172a", fontweight="bold")

        if i < len(stages) - 1:
            ax.annotate(
                "",
                xy=(xs[i + 1] - w / 2 - 0.01, y),
                xytext=(x + w / 2 + 0.01, y),
                arrowprops=dict(arrowstyle="->", lw=1.2, color="#64748b"),
            )

    ax.set_title("Research flow", pad=10)
    _save(fig, out)


def fig2_algorithm_pipeline(out: Path):
    fig, ax = plt.subplots(figsize=(10.8, 13.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def pbox(x, y, w, h, txt, fc="#eef7ff", ec="#1d4e89"):
        rect = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.2,
            edgecolor=ec,
            facecolor=fc,
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=8.4)

    def dbox(cx, cy, w, h, txt, fc="#fff7ed", ec="#9a3412"):
        verts = np.array(
            [
                [cx, cy + h / 2],
                [cx + w / 2, cy],
                [cx, cy - h / 2],
                [cx - w / 2, cy],
            ]
        )
        poly = patches.Polygon(verts, closed=True, linewidth=1.2, edgecolor=ec, facecolor=fc)
        ax.add_patch(poly)
        ax.text(cx, cy, txt, ha="center", va="center", fontsize=8.1)

    def arrow(x1, y1, x2, y2, text=None, color="#334155"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="->", lw=1.2, color=color))
        if text:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.014, text, ha="center", va="bottom", fontsize=8, color=color)

    # Main vertical pipeline
    pbox(0.33, 0.92, 0.34, 0.048, "Input: MOB at t=0, x_c0=0, y_c0 by side")
    dbox(0.50, 0.84, 0.24, 0.08, "MOB detected\nand reported?")
    pbox(0.33, 0.75, 0.34, 0.060, "t_response=t_detect+t_report\n+t_master+t_order+t_helm")
    dbox(0.50, 0.67, 0.26, 0.085, "Allow helm action?\n(t_response <= SLA)")
    pbox(0.33, 0.58, 0.34, 0.060, "δ_eff(t): 0 -> ramp -> δ_hardover")
    pbox(0.33, 0.50, 0.34, 0.065, "Yaw ODE: dψ/dt=r\ndr/dt=(K·δ_eff-r)/T_r")
    pbox(0.33, 0.40, 0.34, 0.075, "λ_d=draft/LOA -> K,T_r update\nProject wind/wave/current to body frame")
    pbox(0.33, 0.31, 0.34, 0.065, "r_c(t)=r_c0+[u_c,v_c]t\nr_p(t), R_h")
    dbox(0.50, 0.22, 0.26, 0.085, "Entered hazard\n(d<R_h)?")
    dbox(0.50, 0.12, 0.28, 0.085, "Outward crossing\n(d>=R_h) before t_max?")

    # Right-side allow outputs
    pbox(0.75, 0.04, 0.21, 0.10, "ALLOW output:\nτ_clear=t_cross\nstore ψ_clear, KPIs", fc="#ecfdf3", ec="#166534")

    # Left-side ban/fail paths
    pbox(0.04, 0.79, 0.22, 0.09, "BAN:\nNo detection/report\nNo maneuver", fc="#fef2f2", ec="#991b1b")
    pbox(0.04, 0.62, 0.22, 0.09, "BAN:\nResponse too slow\nEscalate protocol", fc="#fef2f2", ec="#991b1b")
    pbox(0.04, 0.02, 0.22, 0.11, "BAN / unresolved:\nNo crossing by t_max\nHigh-risk flag", fc="#fef2f2", ec="#991b1b")
    pbox(0.75, 0.22, 0.21, 0.09, "ALLOW safe branch:\nNo hazard entry\nτ_clear=0", fc="#ecfdf3", ec="#166534")

    # Main arrows
    arrow(0.50, 0.92, 0.50, 0.88)
    arrow(0.50, 0.80, 0.50, 0.75, "Yes")
    arrow(0.50, 0.73, 0.50, 0.71)
    arrow(0.50, 0.63, 0.50, 0.61, "Yes")
    arrow(0.50, 0.58, 0.50, 0.565)
    arrow(0.50, 0.50, 0.50, 0.485)
    arrow(0.50, 0.40, 0.50, 0.385)
    arrow(0.50, 0.31, 0.50, 0.26)
    arrow(0.50, 0.16, 0.50, 0.145, "Yes")
    arrow(0.64, 0.12, 0.75, 0.09, "Yes", color="#166534")

    # Branch arrows: No/ban/allow
    arrow(0.38, 0.84, 0.26, 0.84, "No", color="#991b1b")
    arrow(0.37, 0.67, 0.26, 0.67, "No", color="#991b1b")
    arrow(0.37, 0.22, 0.75, 0.26, "No", color="#166534")
    arrow(0.36, 0.12, 0.26, 0.08, "No", color="#991b1b")

    ax.set_title("Decision-gated algorithm: MOB stern-clearance computation", pad=10)
    _save(fig, out)


def fig3_model_architecture(out: Path):
    fig, ax = plt.subplots(figsize=(11.2, 4.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, w, h, title, body, fc, ec):
        sh = patches.FancyBboxPatch(
            (x + 0.006, y - 0.006),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=0,
            facecolor="#64748b",
            alpha=0.12,
        )
        ax.add_patch(sh)
        p = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=1.4,
            edgecolor=ec,
            facecolor=fc,
        )
        ax.add_patch(p)
        ax.text(x + 0.02, y + h - 0.05, title, ha="left", va="top", fontsize=9.4, color=ec, fontweight="bold")
        ax.text(x + 0.02, y + h - 0.10, body, ha="left", va="top", fontsize=8.8, color="#0f172a")

    box(0.05, 0.58, 0.24, 0.27, "Maneuvering block", "K, T_r, δ\nBridge delay\nRudder ramp", "#fff7ed", "#c2410c")
    box(0.33, 0.58, 0.24, 0.27, "Geometry block", "l_s, x_s\nLOA, beam\nInitial side", "#eff6ff", "#1d4ed8")
    box(0.61, 0.58, 0.24, 0.27, "Environment block", "Wind / wave / current\nBody-frame projection\nDrift components", "#ecfdf5", "#047857")

    box(0.28, 0.17, 0.34, 0.26, "Hazard and crossing block", "r_c(t), r_p(t), R_h\nEntry/exit logic\nτ_clear, ψ_clear", "#faf5ff", "#7e22ce")
    box(0.73, 0.20, 0.21, 0.20, "Outputs", "Outcome class\nPercentile tables\nOperational envelope", "#f8fafc", "#334155")

    # Input arrows to hazard block
    ax.annotate("", xy=(0.40, 0.44), xytext=(0.17, 0.58), arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#64748b"))
    ax.annotate("", xy=(0.45, 0.44), xytext=(0.45, 0.58), arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#64748b"))
    ax.annotate("", xy=(0.50, 0.44), xytext=(0.73, 0.58), arrowprops=dict(arrowstyle="-|>", lw=1.4, color="#64748b"))

    # Hazard to output
    ax.annotate("", xy=(0.73, 0.30), xytext=(0.62, 0.30), arrowprops=dict(arrowstyle="-|>", lw=1.5, color="#475569"))

    ax.set_title("Model architecture and variable interactions", pad=8)
    _save(fig, out)


def fig4_tau_distribution(enriched_csv: Path, out: Path):
    df = pd.read_csv(enriched_csv)
    tau = pd.to_numeric(df["tau_clear_s"], errors="coerce")
    tau = tau[tau > 0]

    q10, q50, q90, q95 = np.percentile(tau, [10, 50, 90, 95])

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.hist(tau, bins=45, color="#5b8ff9", alpha=0.75, edgecolor="white")
    for q, c, lab in [(q10, "#2ca02c", "P10"), (q50, "#ff7f0e", "P50"), (q90, "#d62728", "P90"), (q95, "#9467bd", "P95")]:
        ax.axvline(q, color=c, linestyle="--", linewidth=1.8, label=f"{lab}={q:.1f}s")

    ax.set_xlabel("\u03c4_clear  (s)")
    ax.set_ylabel("Number of events")
    ax.set_title("Nonzero stern-clearance time distribution")
    ax.legend(frameon=False, ncol=2)
    _save(fig, out)


def fig5_stratified_heatmap(percentile_csv: Path, out: Path):
    df = pd.read_csv(percentile_csv)
    df = df[df["n_nonzero"] >= 30].copy()
    loa_order = ["<100m", "100-149m", "150-199m", "200-249m", ">=250m"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    im = None
    for ax, side in zip(axes, ["port", "starboard"]):
        d = df[df["fall_side_group"] == side]
        piv = d.pivot_table(index="ship_class", columns="loa_bin", values="p50_nonzero_s", aggfunc="mean")
        piv = piv.reindex(columns=loa_order)

        im = ax.imshow(piv.values, aspect="auto", cmap="YlOrRd")
        ax.set_xticks(range(len(piv.columns)))
        ax.set_xticklabels(piv.columns, rotation=35, ha="right")
        ax.set_yticks(range(len(piv.index)))
        ax.set_yticklabels(piv.index)
        ax.set_title(f"{side.capitalize()} side (P50)")

        for i in range(piv.shape[0]):
            for j in range(piv.shape[1]):
                v = piv.values[i, j]
                if np.isfinite(v):
                    ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8)

    if im is not None:
        cbar = fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.85)
        cbar.set_label("P50  \u03c4_clear  (s)")
    fig.suptitle("Stratified median clearance time (P50) by ship class and LOA bin", y=1.02)
    _save(fig, out)


def _nonzero_p50(scenarios):
    tau = [r.tau_clear_s for r in (find_tau_clear(sc) for sc in scenarios) if r.tau_clear_s is not None and r.tau_clear_s > 0]
    if not tau:
        return float("nan")
    return float(np.percentile(np.array(tau), 50))


def fig6_sensitivity_tornado(scenario_csv: Path, out: Path):
    scenarios = parse_scenarios(scenario_csv)
    baseline = _nonzero_p50(scenarios)

    experiments = [
        ("Hazard radius  R_h  (+20%)", lambda sc: replace(sc, R_h_m=sc.R_h_m * 1.20)),
        ("Crew response delay  t_resp  (+10 s)", lambda sc: replace(sc, t_response_s=sc.t_response_s + 10.0)),
        ("Crew response delay  t_resp  (+30 s)", lambda sc: replace(sc, t_response_s=sc.t_response_s + 30.0)),
        ("Turning gain  K  (-15%)", lambda sc: replace(sc, K=sc.K * 0.85)),
        ("Yaw lag  T_r  (+15%)", lambda sc: replace(sc, T_r_s=sc.T_r_s * 1.15)),
        ("Rudder travel  t_rud  (+2 s)", lambda sc: replace(sc, t_rudder_s=sc.t_rudder_s + 2.0)),
        ("Hard-over rudder  δ  (-5°)", lambda sc: replace(sc, delta_deg=max(5.0, sc.delta_deg - 5.0))),
    ]

    params = []
    impacts = []
    for label, transform in experiments:
        perturbed = [transform(sc) for sc in scenarios]
        p50 = _nonzero_p50(perturbed)
        params.append(label)
        impacts.append(p50 - baseline)

    impacts = np.array(impacts, dtype=float)

    order = np.argsort(np.abs(impacts))
    params = [params[i] for i in order]
    impacts = impacts[order]

    fig, ax = plt.subplots(figsize=(8.4, 4.8))
    colors = ["#ef4444" if v > 0 else "#10b981" for v in impacts]
    ax.barh(params, impacts, color=colors, alpha=0.85)
    ax.axvline(0, color="black", linewidth=1)
    ax.set_xlabel("Δ P50  τ_clear  (s)")
    ax.set_title("One-at-a-time sensitivity: shift in baseline P50 τ_clear")
    _save(fig, out)


def main() -> None:
    _style()
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "outputs/figures"

    enriched_csv = root / "outputs/event_clearance_results_enriched.csv"
    percentile_csv = root / "outputs/operational_percentiles_by_class_loa_side.csv"
    scenario_csv = root / "data/event_scenarios_from_6_4.csv"

    fig1_research_flow(out_dir / "Figure_1_research_flow.png")
    fig2_algorithm_pipeline(out_dir / "Figure_2_algorithm_pipeline.png")
    fig3_model_architecture(out_dir / "Figure_3_model_architecture.png")
    fig4_tau_distribution(enriched_csv, out_dir / "Figure_4_tau_distribution.png")
    fig5_stratified_heatmap(percentile_csv, out_dir / "Figure_5_stratified_heatmap.png")
    fig6_sensitivity_tornado(scenario_csv, out_dir / "Figure_6_sensitivity_tornado.png")

    print(f"Draft figures created in: {out_dir}")


if __name__ == "__main__":
    main()
