"""Abstract simulation backend.

The mission layer never talks to HoloOcean (or any simulator) directly: it
sees only this interface. That is what will later let the same mission code
drive a real BlueROV2 through a MAVLink backend.
"""
from __future__ import annotations

import abc

from ..utils.types import VehicleState, Waypoint


class SimulatorBackend(abc.ABC):
    """Contract:

    - :meth:`reset` (re)initializes the vehicle and returns the initial state.
    - :meth:`step_toward` advances the simulation by exactly one control
      period (:attr:`control_period_s` simulated seconds) while steering
      toward the given waypoint, and returns the new state.
    - Backends do not track budget or samples; the mission runner does.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def control_period_s(self) -> float: ...

    @abc.abstractmethod
    def reset(self) -> VehicleState: ...

    @abc.abstractmethod
    def step_toward(self, waypoint: Waypoint) -> VehicleState: ...

    def close(self) -> None:  # pragma: no cover - trivial default
        """Release simulator resources (default: nothing to do)."""

    def __enter__(self) -> "SimulatorBackend":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
