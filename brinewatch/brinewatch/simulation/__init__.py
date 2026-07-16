from .base import SimulatorBackend
from .kinematic import KinematicBackend

__all__ = ["SimulatorBackend", "KinematicBackend", "make_backend"]


def make_backend(name, cfg, env_cfg, outfall_cfg, start_position, seed=0):
    """Factory: build a simulation backend by name.

    Names: "kinematic" | "holoocean" (official engine, visual-only props) |
    "holoocean_custom" (fork engine with runtime octree rebuild; requires
    HOLOOCEAN_CUSTOM_ENGINE_PATH and a running fork engine — fails loudly
    otherwise, never falls back to the official engine).

    HoloOcean is imported lazily so the rest of the package works without it.
    """
    if name == "kinematic":
        return KinematicBackend(cfg, env_cfg, start_position, seed=seed)
    if name == "holoocean":
        from .holoocean_backend import HoloOceanBackend

        return HoloOceanBackend(cfg, env_cfg, outfall_cfg, start_position, seed=seed)
    if name == "holoocean_custom":
        from .holoocean_backend import HoloOceanBackend

        return HoloOceanBackend(cfg, env_cfg, outfall_cfg, start_position,
                                seed=seed, custom_engine=True)
    raise ValueError(
        f"Unknown backend '{name}' "
        "(expected 'kinematic', 'holoocean' or 'holoocean_custom')"
    )
