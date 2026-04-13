from __future__ import annotations

import math
import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "code" / "stern_clearance_model.py"
spec = importlib.util.spec_from_file_location("stern_clearance_model", MODULE_PATH)
assert spec is not None and spec.loader is not None
_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = _mod
spec.loader.exec_module(_mod)

Scenario = _mod.Scenario
find_tau_clear = _mod.find_tau_clear


def test_linear_clearance_when_k_zero():
    # Analytic case: no yaw dynamics (K=0), propeller center fixed at origin.
    # Casualty starts at origin and moves at vc=1 m/s with Rh=5 m -> tau_clear=5 s.
    sc = Scenario(
        scenario_id="analytic_linear",
        K=0.0,
        T_r_s=10.0,
        delta_deg=35.0,
        l_s_m=0.0,
        x_s_m=0.0,
        xc0_m=0.0,
        yc0_m=0.0,
        uc_mps=0.0,
        vc_mps=1.0,
        R_h_m=5.0,
        t_response_s=0.0,
        t_rudder_s=0.0,
        t_max_s=30.0,
        dt_s=0.1,
    )

    out = find_tau_clear(sc)
    assert out.status == "cleared_after_entry"
    assert out.entered_hazard is True
    assert out.tau_clear_s is not None
    assert math.isclose(out.tau_clear_s, 5.0, abs_tol=0.11)


def test_never_entered_status_is_explicit():
    sc = Scenario(
        scenario_id="never_entered",
        K=0.0,
        T_r_s=10.0,
        delta_deg=35.0,
        l_s_m=0.0,
        x_s_m=0.0,
        xc0_m=100.0,
        yc0_m=0.0,
        uc_mps=0.0,
        vc_mps=0.0,
        R_h_m=5.0,
        t_response_s=0.0,
        t_rudder_s=0.0,
        t_max_s=10.0,
        dt_s=0.1,
    )

    out = find_tau_clear(sc)
    assert out.status == "never_entered"
    assert out.entered_hazard is False
    assert out.tau_clear_s == 0.0
