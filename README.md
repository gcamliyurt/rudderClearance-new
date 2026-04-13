# Rudder Clearance Study (MOB Immediate Protection)

This workspace is prepared for your new study on **initial hard-over rudder action** to reduce propeller strike risk in immediate-sight MOB cases.

## Core variable to estimate

- `tau_clear`: earliest time when casualty exits the moving propeller hazard zone.

$$
\tau_{\text{clear}}=\inf\left\{t>0:\ \|\mathbf r_c(t)-\mathbf r_p(t)\|\ge R_h\right\}
$$

## Implemented model

- First-order yaw response:
  $$
  \dot r=\frac{K\delta-r}{T_r},\quad
  \psi(t)=K\delta\left[t-T_r\left(1-e^{-t/T_r}\right)\right]
  $$
- Propeller hazard center motion from stern swing:
  $$
  \mathbf r_p(t)=
  \begin{bmatrix}
  -x_s+l_s(1-\cos\psi(t))\\
  -l_s\sin\psi(t)
  \end{bmatrix}
  $$
- Casualty drift:
  $$
  \mathbf r_c(t)=\mathbf r_c(0)+\begin{bmatrix}u_c\\v_c\end{bmatrix}t
  $$

## Folder structure

- `code/stern_clearance_model.py`: main simulation and sensitivity runner
- `code/calibrate_from_rot.py`: estimate `K`, `T_r` from ROT time-series
- `data/example_scenarios.csv`: template scenarios
- `docs/method_notes.md`: paper-ready framing and parameter guidance
- `outputs/`: generated results

## Current analysis scope

- Default batch build now resolves the available real project files first, especially the current `6.4 pilotManuveringTrajectory/outputs` event and maneuver tables.
- The run keeps only `ALLOW_WITH_EMERGENCY_PLAN` events from that executable event table.
- If maneuver-plan timestamps do not match those eligible events, the batch run records the miss and falls back to `35 deg` hard-over.
- The code can project wind/wave/current drift, but the current executable event table lacks the magnitudes needed to activate those terms in the baseline run.

## Intended study order

- `6.0 meetingPoint / pilot_boat_analysis` and `6.1 shipDomain` provide upstream operational context.
- `6.2 rudderClearance` defines the initial CW-MOB trigger variables:
  `tau_clear_s` and `psi_clear_deg`.
- `6.4 pilotManuveringTrajectory` is the later downstream study that should use the `6.2` outputs in full emergency-turn calculations.

Local copies under `data/imports/6.4/` are retained as workspace backups, but the executable pipeline now attempts to read the real external project files first. This still does not mean that `6.4` conceptually precedes `6.2`; it only reflects the current executable data bridge.

## Suggested workflow

1. Put initial trial/AIS-derived scenarios into `data/example_scenarios.csv`.
2. Fit `K` and `T_r` from available ROT traces.
3. Run sensitivity on rudder angle (`20°`, `25°`, `30°`, `35°`) and speed conditions.
4. Report operational decision threshold as:
   - minimum hold time at hard-over, and
   - minimum heading change (`psi_clear`) for conservative separation.

## External data source

Your referenced source directory:

/Users/gokhancamliyurt/Desktop/1. posDoc/6.0 meetingPoint/6.4 pilotManuveringTrajectory

You can copy/export needed trajectory and ROT data into this workspace `data/` folder for direct use.
