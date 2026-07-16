# Visual asset manifest

All assets under `docs/application/pfh2026/assets/`. Every file is a genuine
artifact: an official-HoloOcean capture, or a matplotlib render of real run
data. No stock or AI-generated imagery. "Family": B = beauty (page-1 grade),
T = technical evidence.

| File | Family | Shows | Origin (command) | Genuine sim output? | Plume physical? |
|---|---|---|---|---|---|
| scene/pier_structure_camera.png | B | survey-site structures over the seabed | scripts/explore_pierharbor.py (RGBCamera) | yes | n/a (no plume rendered) |
| scene/site_bathymetry.png | T | RangeFinder bathymetry of the site | scripts/explore_pierharbor.py | render of measured data | n/a |
| scene/scene_* (final gallery) | B/T | outfall geometry views (overview/side/approach/risers/clean/context) | scripts/capture_scene_views.py | yes | analytic only (never rendered) |
| sonar/pier_sonar_aimed.png | T | ImagingSonar frame of stock structures | scripts/explore_pierharbor.py | yes | n/a |
| sonar/pier_sonar_openwater_control.png | T | zero-return control frame | scripts/explore_pierharbor.py | yes | n/a |
| sonar/gate/* | T | present/absent octree experiment (bit-identical) | scripts/validate_sonar_visibility.py | yes | n/a |
| sonar/detector_eval.png/.json | T | structure-vs-clutter strengths, PR curve on recorded mission | scripts/evaluate_sonar_detector.py | render of recorded data | n/a |
| results/learning_curves_static.png / _dynamic.png | T | 20-seed benchmark curves | scripts/run_benchmark.py | render of run data | analytic surrogate |
| results/benchmark_records_*.csv, benchmark_summary_*.json | T | raw benchmark records | scripts/run_benchmark.py | data | analytic surrogate |
| results/site_history_trend.png + site_history_ledger.jsonl | T | simulated 6-mission campaign trend | scripts/build_site_history_demo.py | render of run data (labelled simulated) | analytic surrogate |
| results/pfh_mission_maps* (final run) | T | truth vs GP mean vs uncertainty; screening map | scripts/run_pfh2026_demo.py | render of run data | analytic surrogate |

Captions for the scene gallery: `assets/scene/captions.md` (written when the
gallery is generated). Missing by design: a photo of the physical BlueROV2
— must come from the team; never substitute stock imagery.
