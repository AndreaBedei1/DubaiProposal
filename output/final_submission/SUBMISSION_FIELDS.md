# BrineWatch — paste-ready submission fields

## Project Name

BrineWatch

## Project Phase

Initial Prototype or Model

## One-line pitch

BrineWatch turns one robotic outfall inspection into an uncertainty-aware plume map that directs certified sampling to the locations that matter.

## Short project summary

BrineWatch is an underwater monitoring prototype for desalination outfalls. A BlueROV2 uses the Omniscan 450 FS forward-looking imaging-sonar concept to localise the diffuser, then a planned conductivity-temperature payload samples the surrounding water. Adaptive planning concentrates limited survey time where measurements can best resolve the plume boundary. A 2-D and 3-D Gaussian-process model converts the samples into a map, uncertainty estimate and CLEAR / REVIEW / POSSIBLE EXCEEDANCE screening result. Each mission updates a digital site history so operators can compare conditions over time and target accredited follow-up sampling. The current Initial Prototype or Model has completed an isolated, collision-free custom-HoloOcean mission and a high-contrast simulation demonstration; the next step is calibrated CT integration and controlled-water validation.

## Project Description

Desalination is essential in water-stressed regions, but the concentrated brine returned to the sea can be difficult to monitor as a spatial, changing plume. Sparse fixed stations and a few CT casts can verify conditions only where they are placed, leaving the boundary between affected and background water under-resolved.

BrineWatch is an Initial Prototype or Model that combines infrastructure inspection and environmental screening in one repeatable robotic workflow. A BlueROV2 first uses the Omniscan 450 FS forward-looking imaging-sonar concept to locate the outfall diffuser from multiple aspects without an oracle position. A conductivity-temperature payload is then intended to sample salinity while adaptive planning moves the vehicle toward locations that reduce uncertainty or clarify the plume boundary. One coherent Gaussian-process model reconstructs the field in 2-D and 3-D, while a three-state screen returns CLEAR when the evidence supports it, POSSIBLE EXCEEDANCE when a threshold exceedance is probable, and REVIEW when uncertainty remains too high. Maps, uncertainty, trajectory, sonar anchor, verdict and mission history are stored in a digital twin that recommends the next follow-up location.

The prototype has already completed a real custom-HoloOcean vehicle and sonar mission with 395 m of in-engine travel, 564 simulated CT readings and zero collisions. In an explicitly labelled, demo-optimised analytic plume scenario, its adaptive 2-D reconstruction achieved 0.342 PSU RMSE, 0.947 boundary F1 and 0.900 boundary IoU with a correct conclusive screening outcome. In an eight-seed equal-evidence comparison using 48 readings and the same 300 m budget, adaptive sampling was conclusive and correct in 8/8 runs, versus 4/8 for a regular survey and 0/8 for sparse fixed stations. A four-altitude 3-D mission achieved 0.805 volume IoU.

BrineWatch does not claim to replace accredited monitoring. It is designed to provide more informative same-day spatial evidence under constrained survey time and to direct certified/manual samples toward the locations that matter. Support would enable calibrated CT integration, controlled-water trials and a supervised nearshore pilot with independent reference samples.

## Milestones achieved to date

- Built the Locate → Sense → Adapt → Reconstruct → Act software workflow around a BlueROV2 / Omniscan 450 FS concept.
- Preserved and integrated the accepted multiport outfall structure in a custom-HoloOcean scene.
- Demonstrated native simulated imaging-sonar visibility and multi-radius localisation without oracle input or silent fallback.
- Achieved a 2.35 m scored centre error with a 1.67 m uncertainty radius and 5/5 valid non-fallback prior-perturbation fits.
- Completed an isolated custom-HoloOcean mission with 395 m of travel, 564 simulated CT readings and zero collisions.
- Produced a correct, conclusive high-contrast flagship screen with 0.342 PSU plume RMSE, 0.947 boundary F1 and 0.900 boundary IoU.
- Benchmarked sparse fixed stations, a regular survey and adaptive sampling under the same 48-reading / 300 m evidence budget across eight seeds.
- Built one anisotropic 3-D Gaussian-process reconstruction across four altitude bands, reaching 0.805 volume IoU.
- Implemented a digital-twin dashboard containing site map, uncertainty, trajectory, localisation, verdict, history and recommended follow-up.
- Produced a genuine continuous 1080p custom-HoloOcean approach and inspection capture, a 3-D progressive reconstruction and a competition report.
- Defined transparent new-build, incremental and per-survey cost ranges plus a gated controlled-water-to-nearshore roadmap.

## Awards, Prizes and Featured Publications

No awards, prizes or featured publications to date. BrineWatch is being presented as an Initial Prototype or Model, with the immediate objective of converting the simulation-led evidence into calibrated controlled-water and nearshore validation.

## Project Video

Main competition film: `BrineWatch_PFH2026_Final_1080p.mp4` — 51 seconds, 1920 × 1080, 30 fps. Publish the file on the submission-approved video host and replace the placeholder below with the public link.

**Video link:** [INSERT PUBLIC VIDEO URL]

Disclosure: the opening 20.8 seconds are 625 consecutive RGB frames from a dedicated custom-HoloOcean cinematic capture. The camera path is smooth and genuine to the simulated scene, but it is not a telemetry-synchronised replay of the scientific survey. The progressive 3-D sequence is generated from the validated volumetric reconstruction outputs.

## Supporting upload note

The 13-page competition report presents the problem, system, in-engine evidence, localisation, fair equal-evidence comparison, flagship 2-D and 3-D reconstruction, digital twin, screening limitations, transparent cost model and deployment roadmap. All performance claims are labelled as simulation results; the high-contrast flagship is identified as a demo-optimised analytic surrogate rather than CFD or field truth.

## What support would enable next

Funding, technical mentorship and pilot access would enable a calibrated conductivity-temperature payload, traceable time synchronisation, controlled-water truth experiments and a supervised nearshore deployment with independent certified samples. This would establish error bounds, validate the operational workflow and determine when repeat robotic surveys create practical and economic value.

