# Demonstration movie (Phase 7)

`mission_movie.mp4` — a ~28 s narrated walk-through of a complete BrineWatch
mission, **assembled entirely from real mission outputs**. Encoded with OpenCV
(`mp4v`); no ffmpeg / imageio in the environment.

Reproduce:

```bash
python scripts/make_mission_movie.py \
    --run outputs/custom_holoocean_mission_20260721_210559 \
    --rgb outputs/cinematic_Dam_20260719_123817/frames \
    --volumetric outputs/volumetric/adaptive_run1/volumetric_isosurface.png \
    --history site_history/site_history_trend.png \
    --out outputs/video_demo/mission_movie
```

## Stages (in order)

1. **Title**
2. **Site overview** — survey box, chart prior, sonar estimate
3. **Sonar detection & localization** — a real recorded ImagingSonar frame +
   the background-subtraction / diffuser-line result (estimate error **1.65 m**,
   no ground truth)
4. **ROV descent / approach / inspection** — genuine engine RGBCamera capture
   (the BlueROV2's own frame is visible over the seabed)
5. **Collision-safe adaptive survey** — the **real in-engine trajectory**
   animated over the GP-mean plume (0 collisions, min clearance 3.49 m, 271 CTD
   samples); the climb-over detour is visible
6. **Plume reconstruction + uncertainty** — GP mean and GP std
7. **3-D volumetric plume** — the multi-altitude iso-surface
8. **Compliance screening** — the compliance map + the three-state verdict (REVIEW)
9. **Digital-twin site history** — the repeated-mission trend record
10. **End card**

## Honesty

Every panel is genuine simulator output from the custom-HoloOcean mission
`custom_holoocean_mission_20260721_210559` (motion + sonar in the fork engine),
except the RGB flythrough, which is separate engine RGBCamera capture. The
salinity field is the documented analytic **simulation surrogate**, sampled
along the real engine trajectory — stated on the end card and in
`movie_manifest.json`.

| file | content |
|------|---------|
| `mission_movie.mp4` | the movie (1280×720, 20 fps, ~28 s) |
| `contact_sheet.png` | 12 key frames at a glance |
| `movie_manifest.json` | source run, frame count, headline metrics |
