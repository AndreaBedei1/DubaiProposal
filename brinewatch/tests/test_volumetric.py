"""Engine-free tests for the 3-D volumetric plume reconstruction."""
import numpy as np

from brinewatch.mapping.volumetric import (
    VolumetricConfig,
    VolumetricGrid,
    metrics,
    plume_body_mask,
)


class _Survey:
    x_min, x_max, y_min, y_max = -20.0, 40.0, -20.0, 20.0


def flat_bed(x, y):
    return np.full_like(np.asarray(x, dtype=float), -50.0)


def test_grid_shape_and_terrain_following():
    g = VolumetricGrid(_Survey(), flat_bed, VolumetricConfig(nx=10, ny=8, nz=6))
    assert g.shape == (10, 8, 6)
    # bottom layer z = bed + min altitude; top layer = bed + max altitude
    assert np.allclose(g.Z[:, :, 0], -50.0 + g.cfg.z_above_bed_min_m)
    assert np.allclose(g.Z[:, :, -1], -50.0 + g.cfg.z_above_bed_max_m)
    assert g.points.shape == (10 * 8 * 6, 3)


def test_plume_body_mask_drops_isolated_cells():
    field = np.zeros((12, 12, 6))
    # a connected blob near the source
    field[2:6, 4:8, 0:3] = 45.0
    # an isolated spurious cell far away
    field[10, 10, 4] = 45.0
    body = plume_body_mask(field, threshold_psu=42.0)
    assert body[3, 5, 1]           # blob kept
    assert not body[10, 10, 4]     # isolated cell dropped
    assert body.sum() == (4 * 4 * 3)


def test_metrics_volume_area_and_uncertainty():
    g = VolumetricGrid(_Survey(), flat_bed, VolumetricConfig(nx=20, ny=20, nz=8))
    mean = np.full(g.shape, 39.0)
    # a compact plume body: high near bottom, fading up
    ix, iy = 8, 10
    for iz in range(4):
        mean[ix - 2:ix + 3, iy - 2:iy + 3, iz] = 50.0 - 2.0 * iz
    std = np.full(g.shape, 0.3)
    m = metrics(mean, std, g, threshold_psu=42.0)
    assert m.plume_volume_m3 > 0
    assert m.plume_area_bottom_m2 > 0
    assert m.peak_salinity_psu == 50.0
    assert m.plume_top_height_m > 0           # plume extends above the bed
    # volume ~ n_cells * cell volume (reported rounded to 0.1 m^3)
    cell_vol = g.dx * g.dy * g.dalt
    assert abs(m.plume_volume_m3 - m.n_plume_cells * cell_vol) < 0.1


def test_empty_field_gives_zero_plume():
    g = VolumetricGrid(_Survey(), flat_bed, VolumetricConfig(nx=8, ny=8, nz=5))
    mean = np.full(g.shape, 39.0)
    m = metrics(mean, np.full(g.shape, 0.2), g, threshold_psu=42.0)
    assert m.plume_volume_m3 == 0.0
    assert m.n_plume_cells == 0
