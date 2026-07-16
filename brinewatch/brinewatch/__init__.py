"""BrineWatch: autonomous monitoring of desalination brine plumes.

A BlueROV2-style vehicle surveys a synthetic (analytic, non-CFD) brine plume
around a desalination outfall, reconstructs the 3-D salinity field with a
Gaussian-process mapper, compares fixed lawnmower vs adaptive informative
sampling, and produces compliance verdicts and digital-twin style reports.

Backends: a fast kinematic simulator (no external deps) and HoloOcean 2.x
with the native BlueROV2 agent.
"""

__version__ = "0.1.0"
