# BrineWatch

BrineWatch is a research prototype for autonomous monitoring of desalination
brine plumes. It combines a BlueROV2 mission workflow, adaptive informative
sampling, Gaussian-process field reconstruction, and uncertainty-aware
mixing-zone assessment in a reproducible simulation stack.

The repository includes both the project proposal prepared for **Prototypes
for Humanity 2026** and the Python implementation used for the simulation and
benchmark experiments.

> **Research status:** BrineWatch is a simulation-led prototype, not a
> certified environmental monitoring or regulatory compliance system. The
> plume is an analytic surrogate rather than a CFD or field-validated model.

## What is included

- An autonomous `LOCATE -> BASELINE -> SURVEY -> REPORT` mission workflow.
- Fixed lawnmower and adaptive informative-sampling planners.
- A fast kinematic backend for reproducible experiments.
- An optional HoloOcean backend using a simulated BlueROV2 Heavy.
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

Generated mission and benchmark results are written to `brinewatch/outputs/`
and are intentionally excluded from version control.

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

