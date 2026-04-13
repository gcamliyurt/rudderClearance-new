# Kick Effect Variable Register (Pilot MOB During Transfer)

## A. Primary outcome variables

- `tau_clear_s`: time to exit propeller hazard zone.
- `psi_clear_deg`: heading change at clearance.

## B. Core explanatory variables (recommended)

### 1) Vessel-motion / maneuvering
- `vessel_sog_kn` (or $V$): ship speed at MOB.
- `delta_deg`: applied rudder command.
- `delta_max_deg`: rudder hard-over limit.
- `t_rudder_s`: time from helm order to commanded rudder achieved.
- `K`: steering gain in yaw model.
- `T_r_s`: yaw response lag.
- `turning_radius_m` or `ROT` data for calibration.

### 2) Geometry
- `loa_m`, `beam_m`, `dim_b_m`.
- `x_s_m`: CG to propeller plane aft distance.
- `l_s_m`: pivot-to-stern lever arm.
- `xc0_m`, `yc0_m`: casualty initial position in ship-fixed frame.

### 3) Environment
- Wind: `wind_speed_mps`, `wind_dir_deg`.
- Current: `current_speed_mps`, `current_dir_deg` (not yet available in imported event table).
- Waves: `wave_height_m`, optional period/direction.

### 4) Human/bridge response chain
- `t_detect_report_s`.
- `t_master_decide_s`.
- `t_order_helm_s`.
- `t_helmsman_ack_s`.
- Aggregate: `t_response_s`.

### 5) Hazard definition
- `R_h_m`: effective propeller danger radius.
- Optionally decomposed as:
  $$
  R_h = R_p + R_{wash} + R_{obs} + R_{margin}
  $$

## C. Pilot-transfer specific assumption used now

- Casualty initial longitudinal location set to **midship**:
  - `xc0_m = 0`.
- Lateral side from `fall_side`:
  - starboard => `yc0_m > 0`, port => `yc0_m < 0`.

## D. Model status check

Implemented explicitly in current code:
- `vessel_sog_kn` (used to derive body-frame relative longitudinal motion),
- `delta_deg`, `delta_max_deg`, `t_rudder_s`,
- `K`, `T_r_s`,
- `t_response_s`,
- `xc0_m`, `yc0_m`,
- `wind_speed_mps` (cross-drift proxy),
- `wind_dir_deg`,
- `wave_height_m`, `wave_dir_deg`,
- `current_speed_mps`, `current_dir_deg` (if available in source rows),
- vector projection of wind/current/wave into body-frame drift (`uc_mps`, `vc_mps`),
- `R_h_m`.

Partially represented (proxy only):
- wave period and detailed spectral sea-state forcing.

Not yet explicit in model dynamics:
- rudder rate nonlinearity by pump pressure/load,
- shallow-water or bank effects,
- twin-screw asymmetry,
- propeller wash anisotropy.
