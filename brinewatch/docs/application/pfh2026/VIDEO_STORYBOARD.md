# Video storyboard — 60-70 s, silent-capable, captioned

Working title: **BrineWatch — repeatable evidence for the underwater cost of
fresh water.**

Rules: every clip is genuine output (HoloOcean capture, real figure render,
or a photo of the physical ROV). No stock footage presented as evidence; any
illustrative graphic is captioned as an illustration.

| # | Time | Shot | Source file / command | Caption | Status |
|---|---|---|---|---|---|
| 1 | 0-5 s | Title card over dark water gradient | title card (static) | "Desalination returns a dense, invisible brine layer to the seabed." | to render (trivial) |
| 2 | 5-12 s | Photo of the team's physical BlueROV2 (+ Omniscan) | team photo `[REQUIRED FROM TEAM]` | "An existing low-cost ROV, retrofitted for near-bed sensing." | needs team photo |
| 3 | 12-20 s | HoloOcean: outfall scene flyby (pier + manifold + risers) | capture via scripts/capture_scene_views.py (RGBCamera poses) | "Official HoloOcean simulation: the survey site." | after scene captures |
| 4 | 20-30 s | Real ImagingSonar frame with detection overlay animating over 3 frames | assets/sonar/ (from sonar recording + detector overlay renderer) | "The sonar sees the outfall structure; the detector localizes it — no ground truth." | after detector eval |
| 5 | 30-40 s | Top-down trajectory animation: LOCATE spiral -> baseline cross -> adaptive survey | animate from plume_maps.npz trajectory (matplotlib FuncAnimation -> mp4) | "Baseline transects, then boundary-aware adaptive sampling." | after final mission |
| 6 | 40-50 s | GP map forming: samples appearing, mean surface sharpening (3-4 keyframes) | keyframes from benchmark checkpoint refits | "Every sample sharpens the salinity map — with explicit uncertainty." | after final mission |
| 7 | 50-60 s | Screening banner: CLEAR / REVIEW / POSSIBLE EXCEEDANCE + uncertainty map | report.html capture / map_compliance.png | "The verdict is honest: when the data cannot support a conclusion, it says REVIEW." | ready (report exists) |
| 8 | 60-70 s | Mission-history strip (simulated campaign) + closing title | site_history plots | "Repeatable evidence, mission after mission. BrineWatch." | after site-history demo |

Assembly (when ffmpeg available):

    ffmpeg -framerate 30 -i frames/%04d.png -c:v libx264 -pix_fmt yuv420p brinewatch_pfh2026.mp4

Fallback if no video is submitted: the form's video link is optional; the
storyboard stays in the application folder as production-ready material.

Recommended public link metadata:
- Title: "BrineWatch — autonomous brine-plume screening (simulation prototype)"
- Description: 2 lines + repo link; explicitly says "official HoloOcean
  simulation; physical trials planned" — no implication of field footage.
