from .base import SimulatorBackend
from .kinematic import KinematicBackend

__all__ = ["SimulatorBackend", "KinematicBackend", "make_backend"]


def make_backend(name, cfg, env_cfg, outfall_cfg, start_position, seed=0):
    """Factory: build a simulation backend by name ("kinematic" | "holoocean").

    HoloOcean is imported lazily so the rest of the package works without it.
    """
    if name == "kinematic":
        return KinematicBackend(cfg, env_cfg, start_position, seed=seed)
    if name == "holoocean":
        from .holoocean_backend import HoloOceanBackend

        return HoloOceanBackend(cfg, env_cfg, outfall_cfg, start_position, seed=seed)
    raise ValueError(f"Unknown backend '{name}' (expected 'kinematic' or 'holoocean')")
