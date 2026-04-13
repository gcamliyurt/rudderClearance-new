# Method Notes: Immediate Rudder Action for MOB Propeller Clearance

## Problem framing

This study isolates **Phase 1 (first 10–30 s)** after MOB detection:
- objective: protect casualty from stern/propeller zone,
- not yet full recovery maneuver geometry (Anderson/Williamson).

Pilot-transfer application assumption:
- casualty is typically near **midship transfer area** at fall moment (`xc0_m = 0` in body frame),
- with side sign from `fall_side`.

Bridge/actuation timing now represented by:
- `t_response_s` (detection/report + master decision + order + helmsman action),
- `t_rudder_s` (rudder travel to commanded angle; baseline now uses an IMO/SOLAS steering-gear benchmark proxy, i.e. about 15.1 s from midship to 35$^{\circ}$ hard-over).

Suggested interpretation for the manuscript:

- $t_{\mathrm{bridge}} = t_{\mathrm{detect/report}} + t_{\mathrm{master\ decision}} + t_{\mathrm{order}} + t_{\mathrm{helmsman}}$
- $t_{\mathrm{ship\ response}} = t_{\mathrm{bridge}} + t_{\mathrm{rudder}}$
- Pilot fall-to-hazard time is **not** a fixed input; it emerges from relative kinematics between casualty drift and stern-hazard motion.
## Decision output

For each vessel-condition scenario:
- `tau_clear` (s): minimum hard-over duration needed,
- `psi_clear` (deg): heading at `tau_clear`.

## Practical envelope to test

- Rudder: `delta = 20°...35°`
- Hazard radius: `R_h = 1.5D_p ... 3.0D_p`
- Drift assumptions:
  - still water (`u_c=v_c=0`),
  - conservative current/wind drift,
  - optional wash-induced drift term.

## Proposed safety reporting style

- **Minimum safe hold time** under conservative `R_h` and drift.
- **Associated heading change** (not standalone criterion, but practical bridge proxy).
- **Sensitivity bands** by loading condition (`K`, `T_r`) and speed.

## Calibration path for later trajectory handoff

For the broader study sequence:
1. Extract helm command timestamp and ROT curve.
2. Fit `r(t)=r_inf(1-exp(-t/T_r))`.
3. Set `K*delta = r_inf`, infer `K` from known `delta`.
4. Use fitted `K`, `T_r` in the `6.2` clearance simulation.
5. Hand `tau_clear_s` and `psi_clear_deg` forward to the later `6.4` emergency-turn study.

## Current dataset caveat

The current executable prototype still uses parked compatibility imports under `data/imports/6.4/`. In those files, the maneuver-plan timestamps do not align with the eligible MOB-event timestamps, so the reproducible baseline run uses a documented `35 deg` hard-over fallback. The code still retains optional pathways for maneuver-plan matching and metocean drift projection when a compatible dataset becomes available. This is a prototype convenience, not the intended conceptual chronology of the research sequence.

## Limitation statement for manuscript

Model captures early protection phase only. It omits reverse thrust transients, shallow-water interaction, twin-screw asymmetry, and detailed nonuniform wake topology.
