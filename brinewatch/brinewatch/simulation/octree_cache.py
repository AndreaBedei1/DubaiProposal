"""Official HoloOcean octree-cache management, wrapped safely.

HoloOcean's acoustic sensors ray-cast against a per-world octree that the
engine builds lazily and caches on disk under
``<holoocean_path>/worlds/Ocean/<OS>/Holodeck/Octrees/<world>/``.
The *official* public API to invalidate that cache is
``holoocean.delete_world_octrees(world_name)`` — this module only wraps it to
(1) restore the working directory the official function changes and leaves,
and (2) treat "no cache yet" as success instead of an exception.

Why this matters for BrineWatch: props spawned at runtime can only be baked
into octree leaves that are generated *after* the props exist. Clearing the
cached octrees before a run guarantees the engine rebuilds them from the
world state that includes our spawned outfall (see
scripts/validate_sonar_visibility.py for the controlled experiment).

No engine patches, no private APIs: cache deletion + ordinary spawn_prop.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def octree_cache_dir(world: str) -> Optional[Path]:
    """Path of the cached octree directory for ``world`` (None if absent)."""
    import holoocean.util as util

    base = Path(util.get_holoocean_path()) / "worlds" / "Ocean"
    os_dir = "Windows" if os.name == "nt" else "Linux"
    cache = base / os_dir / "Holodeck" / "Octrees" / world
    return cache if cache.exists() else None


def clear_world_octrees(world: str, verbose: bool = True) -> bool:
    """Delete the cached octrees for ``world`` via the official API.

    Returns True if a cache was deleted, False if there was nothing to delete.
    The official function chdir()s into the cache tree; we restore the cwd.
    """
    import holoocean
    from holoocean.exceptions import HoloOceanException

    if octree_cache_dir(world) is None:
        if verbose:
            print(f"[octree_cache] no cached octrees for '{world}' (already clean)")
        return False

    cwd = os.getcwd()
    try:
        holoocean.delete_world_octrees(world)
        return True
    except HoloOceanException as exc:
        if verbose:
            print(f"[octree_cache] official deletion reported: {exc}")
        return False
    finally:
        os.chdir(cwd)
