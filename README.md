# BrineWatch

BrineWatch is a research prototype for autonomous monitoring of desalination
brine plumes. It combines a BlueROV2 mission workflow, adaptive informative
sampling, Gaussian-process field reconstruction, and uncertainty-aware
mixing-zone assessment in a reproducible simulation stack.

The repository includes both the project proposal prepared for **Prototypes
for Humanity 2026** and the Python implementation used for the simulation and
benchmark experiments.

## Competition submission package

The redesigned public 2026 package is indexed in
[output/final_submission/README.md](output/final_submission/README.md). The
recommended upload is the 10-page
[competition report](output/final_submission/UPLOAD/BrineWatch_PFH2026_Public_Competition_Report.pdf)
(6.8 MB) together with the 43.9-second Full-HD
[final video](output/final_submission/UPLOAD/BrineWatch_PFH2026_Public_1080p.mp4).

The public package tells a simple purpose-first story. Complete metrics,
screening counts, assumptions and limitations are separated into the
[technical evidence ledger](output/final_submission/TECHNICAL/BrineWatch_PFH2026_Technical_Evidence_Ledger.pdf).
All headline performance values are explicitly identified as simulation results.

> **Research status:** BrineWatch is a simulation-led prototype, not a
> certified environmental monitoring or regulatory compliance system. The
> plume is an analytic surrogate rather than a CFD or field-validated model.

## What is included

- An autonomous `LOCATE -> BASELINE -> SURVEY -> REPORT` mission workflow.
- Fixed lawnmower and adaptive informative-sampling planners.
- A fast kinematic backend for reproducible experiments.
- An optional HoloOcean backend using a simulated BlueROV2.
- A **custom HoloOcean fork** backend (`holoocean_custom`) that rebuilds the
  sonar octree at runtime, so the **generated outfall is visible to sonar** and
  can be localized by real sonar with no ground truth (the unmodified official
  engine cannot see runtime-spawned geometry). See
  [SONAR_VALIDATION](brinewatch/docs/application/pfh2026/SONAR_VALIDATION.md)
  and [FINAL_REPORT](brinewatch/docs/application/pfh2026/FINAL_REPORT.md).
- Gaussian-process salinity reconstruction and compliance metrics.
- Automated figures, JSON/CSV artifacts, and self-contained HTML reports.
- Tests that run without HoloOcean or a GPU.

## Repository layout

```text
.
|-- BrineWatch_Proposal.tex   # proposal source
|-- BrineWatch_Proposal.pdf   # compiled proposal
|-- brinewatch/               # Python package and experiment code
|   |-- brinewatch/           # implementation
|   |-- configs/              # mission and benchmark configurations
|   |-- docs/                 # architecture, assumptions, and sim-to-real notes
|   |-- scripts/              # runnable entry points
|   `-- tests/                # automated test suite
|-- LICENSE
`-- README.md
```

Generated mission and benchmark results are written to `brinewatch/outputs/`.
Most of that directory is local-only, but a curated set of **committed
evidence packages** (sonar-visibility truth test, visual scene, localization,
full mission, video) is version-controlled and indexed in
[brinewatch/outputs/README.md](brinewatch/outputs/README.md). The custom
HoloOcean engine itself lives at `engine/` and is gitignored (it is large and
machine-local; auto-discovered at runtime).

## Quick start

Requirements:

- Python 3.9 or newer
- `pip`
- HoloOcean 2.x and a compatible GPU only for live simulator runs

From the repository root:

```bash
cd brinewatch
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install the package and development dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run a default adaptive mission on the kinematic backend:

```bash
python scripts/run_mission.py --config configs/mission_default.yaml
```

Run the equal-budget planner benchmark:

```bash
python scripts/run_benchmark.py --config configs/benchmark.yaml --seeds 5
```

Run the test suite:

```bash
python -m pytest
```

## Optional HoloOcean run

HoloOcean is installed separately because it is not distributed through this
package. After installing HoloOcean and its `Ocean` world package, verify the
environment and launch a mission with:

```bash
python scripts/inspect_holoocean.py --launch
python scripts/run_mission.py --config configs/holoocean_live.yaml
```

## Custom-engine sonar demos (Windows)

The custom fork engine is auto-discovered at `<repo>/engine`; only the UE 5.3
editor path is needed. See
[CUSTOM_ENGINE](brinewatch/docs/application/pfh2026/CUSTOM_ENGINE.md).

```powershell
$env:UNREAL_EDITOR_EXE = "C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor.exe"

# isolated smoke test: private UUID, IPC, octree cache, temp area and logs
conda run -n ocean python brinewatch\scripts\run_isolated_custom_session.py --client brinewatch\scripts\smoke_custom_engine.py

# isolated full mission: native sonar LOCATE + collision-safe survey
conda run -n ocean python brinewatch\scripts\run_isolated_custom_session.py --client brinewatch\scripts\run_custom_holoocean_mission.py

# rebuild the curated visuals and smooth competition video
conda run -n ocean python brinewatch\scripts\build_competition_visuals.py
conda run -n ocean python brinewatch\scripts\make_competition_video.py
```

The isolation design and process-ownership rules are documented in
[ISOLATED_EXECUTION](brinewatch/docs/application/pfh2026/ISOLATED_EXECUTION.md).

See the [implementation README](brinewatch/README.md) for experiment results,
output interpretation, simulator details, and the complete command reference.

## Documentation

- [Architecture](brinewatch/docs/architecture.md)
- [Model assumptions and limitations](brinewatch/docs/assumptions.md)
- [HoloOcean integration notes](brinewatch/docs/holoocean_notes.md)
- [Simulation-to-real roadmap](brinewatch/docs/sim_to_real.md)
- [Project proposal (PDF)](BrineWatch_Proposal.pdf)

## Building the proposal

With a LaTeX distribution installed, compile the proposal from the repository
root by running:

```bash
pdflatex BrineWatch_Proposal.tex
pdflatex BrineWatch_Proposal.tex
```

Auxiliary LaTeX files are ignored; the compiled PDF remains versioned as a
convenient public artifact.

## Contributing

Issues and focused pull requests are welcome. Please keep changes reproducible,
document new assumptions, and include tests for behavioral changes.

## License

Released under the [MIT License](LICENSE).
