# Turn-Response Modeling Strategy Without Sea-Trial Rudder Curves

## Short answer

Yes. Using a **median reference-ship model** for Busan New Port traffic is acceptable as a baseline, provided results are reported with uncertainty bands and class/size stratification.

## Recommended approach (practical + publishable)

1. **Tier-1 Baseline (now):**
   - Build per-event parameters from available AIS/event variables (`loa_m`, `beam_m`, `draft_m`, `vessel_ship_type_class`, `vessel_sog_kn`).
   - Use first-order yaw model with delayed helm response and rudder ramp.

2. **Tier-2 Stratified reference ships:**
   - Define reference sets by `ship_type × LOA_bin × draft_ratio_bin`.
   - For each stratum, set representative `K`, `T_r_s`, `t_rudder_s` (median) and uncertainty (`P25/P75`).

3. **Tier-3 Probabilistic sensitivity:**
   - For each event, sample `K`, `T_r_s`, `R_h_m`, `t_response_s`, and environment drift terms.
   - Report `tau_clear` as percentile bands, not single value.

## Variables and data availability in current dataset

Available directly:
- `loa_m`, `beam_m`, `draft_m`, `vessel_ship_type_class`, `vessel_sog_kn`, `fall_side`, `wind_speed_mps`, `wind_dir_deg`, `wave_height_m`, `wave_dir_deg`.

Not available directly:
- sea-trial rudder travel curves,
- full ROT test records,
- block coefficient (`C_b`),
- gross tonnage in the currently merged event file.

## How to represent loading condition (loaded vs ballast)

Use draft-based proxies:
- `lambda_d = draft_m / loa_m` (or `draft_m / beam_m`).
- Higher `lambda_d` => generally larger yaw lag (`T_r_s`) and/or lower effective `K`.

Suggested first proxy mapping (to calibrate later):
- low draft ratio (ballast-like): `T_r_s` multiplier `0.85`, `K` multiplier `1.10`
- medium draft ratio: `1.00`, `1.00`
- high draft ratio (loaded-like): `1.15`, `0.90`

Implementation status:
- This mapping is now applied in scenario generation with `load_state`, `draft_ratio`,
  `K_multiplier`, and `T_r_multiplier` written to the event scenario table.

## Why median model is acceptable

- You are estimating **operational protection time envelope**, not certifying maneuvering booklet values.
- Event population is large; robust central tendency + uncertainty is more defensible than pretending exact sea-trial data.
- Explicitly disclose assumptions and perform sensitivity.

## Reporting recommendation

For each operational stratum, publish:
- `tau_clear` P10/P50/P90,
- corresponding `psi_clear` P10/P50/P90,
- sensitivity to `t_response_s`, `R_h_m`, and loaded/ballast proxy.
