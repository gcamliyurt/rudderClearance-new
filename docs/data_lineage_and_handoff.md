# Data Lineage and Handoff for 6.2 CW-MOB Study

## Study sequence

- `6.0 meetingPoint / pilot_boat_analysis`:
  transfer-point structure, pilot-boat context, and environmental attachment pathway.
- `6.1 shipDomain`:
  surrounding-traffic and domain-risk context for why immediate action is needed.
- `6.2 rudderClearance`:
  defines the new CW-MOB trigger variables.
- `6.4 pilotManuveringTrajectory`:
  later study that should consume the `6.2` trigger outputs in emergency-turn calculations.

## What 6.2 is supposed to prove

This study is the upstream proof of the first emergency action, not the full emergency turn.

Target outputs:
- `tau_clear_s`: minimum time to clear the stern/propeller hazard zone.
- `psi_clear_deg`: heading change reached when that clearance occurs.

These are the quantities intended to be handed to `6.4` as initial emergency-turn inputs or constraints.

## Intended raw-data role by parent study

### From `6.0`

Use for:
- transfer location structure,
- pilot-boat interaction context,
- weather/tide linkage pathway,
- background AIS movement support.

Candidate local files already parked in this workspace:
- `data/imports/6.0/required final data set.csv`
- `data/imports/6.0/T100k.csv`
- `data/imports/6.0/weather_tides_merged_and_smart_interpolated.csv`
- `data/imports/6.0/Static_merged_bbox_result_gokhan.csv`

### From `6.1`

Use for:
- ship-domain and surrounding-contact context,
- pilot-boat proximity logic,
- transfer-event risk framing.

Candidate local files already parked in this workspace:
- `data/imports/6.1/pilot_boat_proximity_events.csv`
- `data/imports/6.1/pilot_boat_assistance_sessions.csv`
- `data/imports/6.1/pilot_transfer_surrounding_contacts_with_motion.csv`
- `data/imports/6.1/annual_transfer_case_events_v2.csv`

### For later `6.4`

Use `6.2` outputs as:
- initial emergency response timing guidance,
- initial heading-change guidance,
- candidate trigger values for the later full-turn simulation.

## Important note on the current executable prototype

The current scripts in this workspace are still wired to parked compatibility files under `data/imports/6.4/`:
- `mob_analysis_all_events.csv`
- `maneuver_plan_per_event.csv`

That setup is acceptable for prototype code testing, but it should not be described as the conceptual study order.

For the paper narrative:
- `6.0` and `6.1` are upstream context sources,
- `6.2` is the present proof study,
- `6.4` is downstream and should consume `6.2` outputs.

## Recommended wording for the paper

Use language like:

`This paper defines the initial CW-MOB trigger envelope, expressed as time to stern-hazard clearance and heading change at clearance. These outputs are intended for later use in full emergency-turn calculations.`

Avoid language like:

`Using outputs from the previous 6.4 study...`

because that reverses the intended chronology.
