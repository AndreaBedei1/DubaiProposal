# BrineWatch - competition submission fields

## Project Name

BrineWatch

## Project Phase

Initial Prototype or Model

## Project Description

BrineWatch is an autonomous underwater monitoring prototype for desalination outfalls. It addresses a practical blind spot: brine is discharged below the surface, where visibility is variable, plume boundaries move and sparse manual samples may not explain what is happening across the site.

The system combines a compact ROV, imaging sonar, conductivity-temperature sensing, adaptive mission planning and a continuously updated digital twin. A mission begins from a chart prior. The ROV acquires the diffuser from multiple sonar viewpoints, runs a collision-aware baseline survey, then spends its remaining travel budget on plume boundaries and areas of high uncertainty. Each new sample updates a salinity reconstruction, a 3-D plume estimate and an uncertainty-aware screening state: CLEAR, REVIEW or POSSIBLE EXCEEDANCE. REVIEW is a deliberate safety feature: the prototype abstains when the evidence is insufficient instead of presenting false certainty.

BrineWatch already runs as an end-to-end prototype in a custom HoloOcean environment. In the strongest in-engine mission, native simulated sonar localized the diffuser centre to 1.65 m without ground-truth position input. The vehicle completed a 220 m survey with 271 samples, zero collisions and 3.49 m minimum structure clearance. A separate multi-altitude mission generated a 3-D plume estimate from 1,770 simulated samples. Across 192 equal-budget benchmark evaluations, the screening logic produced no wrong conclusive outputs; in a dynamic plume at 50% travel budget, adaptive sampling reduced in-plume RMSE by 18.7% and improved boundary F1 by 14.2% relative to a lawnmower route. Dense full-budget coverage remains stronger with the regular route, and that limitation is retained transparently.

The team already owns a BlueROV2 and Omniscan sonar. The next milestone is a calibrated conductivity-temperature payload, controlled-water validation and an independently sampled nearshore pilot. BrineWatch is designed as a fast, repeatable screening and planning layer - not yet as a replacement for certified regulatory sampling.

## Milestones your project has achieved to-date

- Built a configurable, visually complete underwater outfall scene with 105 components and a custom HoloOcean workflow in which the structure is visible to native simulated sonar.
- Implemented sonar localization from a chart prior using 16 viewpoints and no ground-truth position input; best in-engine centre error: 1.65 m.
- Completed a collision-aware 220 m in-engine survey with 271 samples, zero collisions, two safe detours and 3.49 m minimum structure clearance.
- Delivered adaptive sampling, Gaussian-process salinity reconstruction, uncertainty maps and CLEAR / REVIEW / POSSIBLE EXCEEDANCE screening.
- Generated a 3-D plume estimate from 1,770 simulated samples across three sampling altitudes.
- Ran 192 equal-budget validation evaluations across static and dynamic plume scenarios. At 50% budget in the dynamic case, adaptive sampling achieved 18.7% lower in-plume RMSE and 14.2% higher relative boundary F1 than a lawnmower route; no evaluation produced a wrong conclusive screening output.
- Built a presentation-ready digital-twin dashboard, competition video, costed feasibility pathway and controlled-water deployment roadmap.
- Established a process-isolated custom-engine runner so BrineWatch can coexist safely with other HoloOcean workflows without sharing IPC names, octree caches, temp folders or logs.

## Awards, Prizes and Featured Publications

None to date. BrineWatch is being submitted as an initial prototype and has not previously received an award, prize or featured publication.

## Project Video

**Recommended title:** BrineWatch - Autonomous Brine-Plume Screening

**Public link:** [ADD PUBLIC VIDEO LINK AFTER UPLOAD]

**Field description:** A smooth 48-second overview of the BrineWatch simulation prototype: the ROV descends into the outfall site, approaches the diffuser, localizes the structure by sonar, maps salinity with adaptive sampling and updates a 3-D digital twin and uncertainty-aware screening dashboard. The cinematic section is assembled from genuine HoloOcean RGB captures; the technical panels use recorded mission outputs. All performance values shown are simulation results.

**Local master:** `video/BrineWatch_PFH2026_Final.mp4`

**Short alternative:** `video/BrineWatch_PFH2026_Short.mp4`

## Supporting PDF / upload note

Upload `../pdf/BrineWatch_PFH2026_Competition_Report.pdf` as the single project PDF. It is an 11-page presentation deck below the 20 MB target and includes prototype evidence, honest limitations, indicative costs, deployment workflow and roadmap.

## Short project summary (about 75 words)

BrineWatch is an autonomous ROV prototype that finds desalination outfalls by sonar, maps brine with adaptive conductivity-temperature sampling and updates an uncertainty-aware digital twin. In custom HoloOcean it localized a diffuser to 1.65 m, completed a collision-free 220 m mission and generated a 3-D plume estimate from 1,770 simulated samples. With the base ROV and sonar already owned, the next step is calibrated CT integration and controlled-water validation.

## One-line pitch

BrineWatch turns an underwater ROV mission into a living map of where desalination brine goes - and where more evidence is still needed.

## Suggested image captions

- **Hero structure:** BrineWatch approaches a configurable desalination diffuser in HoloOcean; the accepted structure geometry is preserved.
- **Sonar localization:** Sixteen native simulated sonar viewpoints localize the diffuser to 1.65 m without ground-truth position input.
- **Adaptive mission:** The route concentrates samples around the reconstructed plume while keeping model uncertainty visible.
- **3-D plume:** A simulation-based volumetric twin reconstructed from 1,770 samples across three altitudes.
- **Dashboard:** Mission evidence, mapping quality and the conservative REVIEW state in one operational view.

## Evidence disclaimer

BrineWatch is not field validated or certified for regulatory compliance. The current plume is an analytic simulation surrogate, not CFD or measured environmental ground truth. The project is positioned as an initial prototype and a rapid screening / mission-planning layer.
