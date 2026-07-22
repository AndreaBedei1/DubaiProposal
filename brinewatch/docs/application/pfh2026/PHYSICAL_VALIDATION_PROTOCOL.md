# One-day controlled water test — protocol

Goal: retire the "virtual water properties" assumption with a controlled
experiment on the team's physical BlueROV2, using the same mission software
that runs in simulation (the backend and the CT reader are the only swapped
components). This protocol is written to be executable in one day at a pool
or large tank; it has NOT been executed yet.

## Equipment

| Item | Status |
|---|---|
| BlueROV2 (team-owned) + tether + topside laptop | available |
| Cerulean Omniscan 450 FS forward-looking imaging sonar | available (not needed for this test) |
| Conductivity+temperature probe (I2C EC board + probe, e.g. Atlas Scientific EZO-EC K1.0) | to purchase — `[COST TO VERIFY, indicative 200–400 EUR]` |
| Calibration solutions: 12.88 mS/cm and 80 mS/cm KCl standards | to purchase |
| 3 reference containers (fresh, brackish ~20 g/L, saline ~40 g/L NaCl) | prepare on site |
| Handheld reference conductivity meter | borrow/purchase `[TO VERIFY]` |
| Salt (NaCl), 25+ kg, for the gradient source | consumable |

## Timeline

**T0–T1 (1 h) — bench calibration.**
1. Two-point calibration of the EC probe with the KCl standards at logged
   water temperature; record coefficients in the mission config.
2. Cross-check all three reference containers against the handheld meter;
   log expected vs measured (acceptance: |err| < 3% full scale).

**T1–T2 (1 h) — sensor response time.**
3. Step-transfer the probe fresh->saline->fresh 5 times; log time constant
   (acceptance: t63 < 2 s, else lower the CT sample rate in config).

**T2–T3 (1 h) — vehicle integration check.**
4. Probe mounted at the ROV nose, wired via I2C/BlueOS extension; verify
   samples stream to the topside logger with vehicle pose timestamps
   (the `CTDSample` schema used in simulation, unchanged).

**T3–T5 (2 h) — gradient survey.**
5. Create a localized salinity anomaly: dissolve salt in a weighted,
   slow-release container at one corner of the pool (or a fresh-water hose
   inflow in a saline pool — direction irrelevant, gradient is the point).
6. Manual transects: pilot the ROV in a lawnmower pattern; log CT + pose.
7. Autonomous transects (stretch): run the mission runner's BASELINE phase
   through the MAVLink backend skeleton if ready; otherwise manual is fine.

**T5–T6 (1 h) — reference casts.**
8. Take >= 9 point measurements with the handheld meter at marked positions
   and 2 depths; these are the ground-truth casts.

**T6–T7 (1 h) — reconstruction & scoring.**
9. Run the standard BrineWatch pipeline offline on the logged samples
   (GP reconstruction + uncertainty; same code as simulation).
10. Compare the GP prediction at the 9 reference positions.

## Success criteria

- Calibration residual < 3% FS; response t63 < 2 s.
- GP map reproduces the gradient sign and shape;
  RMSE at reference positions < 1.5 PSU (first attempt) —
  tighten in later iterations.
- End-to-end log integrity: every sample carries pose + time.
- A mission report (`report.html`) is generated from real data with the
  run labelled `laboratory` (the report template already carries the
  simulated/laboratory/field label).

## Outputs to archive

Raw CT log, pose log, calibration data, reference-cast table, generated
report, photos of the setup — under `site_history/` as the first
non-simulated entry (clearly labelled laboratory, not field).
