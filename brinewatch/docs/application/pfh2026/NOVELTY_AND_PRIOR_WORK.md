# Novelty positioning and prior work

## What is NOT new

Measuring outfall plumes with marine robots is established research.
Existing work has demonstrated that robotic brine/outfall plume mapping is
technically possible. BrineWatch makes **no claim of being the first**
underwater robot to measure a discharge plume, and no claim of the first
3-D brine map. The honest positioning is:

> Existing research has demonstrated that robotic brine-plume mapping is
> technically possible. BrineWatch focuses on making this capability
> repeatable, adaptive, uncertainty-aware, accessible and transferable to an
> existing low-cost ROV.

## Prior-work table (verified sources only)

| Source | Platform | Measured | Mapping method | Field/Sim | What it proves | What BrineWatch adds |
|---|---|---|---|---|---|---|
| Rogowski et al. 2012, *J. Geophys. Res. Oceans* 117, doi:10.1029/2011JC007804 — "Mapping ocean outfall plumes and their mixing using autonomous underwater vehicles" | REMUS-class AUV | CTD + CDOM | pre-planned transects, post-hoc analysis | Field (Point Loma wastewater outfall) | AUVs can map outfall plumes and estimate dilution far better than cast-based sampling | boundary-aware *adaptive* sampling; on-mission GP with uncertainty; low-cost ROV-class platform; screening output |
| Rogowski et al. 2013, PubMed 23306274 — "Ocean outfall plume characterization using an Autonomous Underwater Vehicle" | REMUS-class AUV | CTD + optics | transect surveys | Field | plume characterization workflow with AUVs | same as above |
| Ramos 2013, doi:10.5772/56644 — "Geostatistical Prediction of Ocean Outfall Plume Characteristics Based on an AUV" | AUV | CTD | geostatistics (kriging) post-hoc | Field | geostatistical reconstruction of outfall plumes from AUV data | online GP during the mission drives *where to sample next*; explicit three-state screening |
| "Combining AUV missions with velocity and salinity measurements for the evaluation of a submerged offshore SWRO concentrate discharge" (ResearchGate 273379246) `[JOURNAL/AUTHORS TO VERIFY]` | AUV + ADCP | salinity, velocity | transects | Field (SWRO brine) | AUV surveys of an actual desalination concentrate discharge | accessibility (BlueROV2 retrofit), repeatable mission records, uncertainty-aware screening |
| "Observing, Monitoring and Evaluating the Effects of Discharge Plumes in Coastal Regions", Springer, doi:10.1007/978-3-319-13203-7_22 | review | — | — | Review | state of practice for discharge-plume monitoring | an integrated, reproducible open implementation |
| Hitz et al. 2017, *J. Field Robotics* 34(8) — adaptive continuous-space informative path planning | ASV | chlorophyll | GP-based adaptive sampling | Field (lake) | adaptive GP sampling beats fixed patterns in aquatic monitoring | applies the idea to the brine mixing-zone problem with a boundary-aware acquisition and screening output |

## The defensible contribution: integration and accessibility

1. **Accessible platform**: a retrofit for an existing BlueROV2-class ROV
   (vehicle already owned by the team) instead of REMUS-class AUVs;
2. **near-seabed conductivity–temperature sampling** where the dense brine
   layer actually lives;
3. **boundary-aware adaptive survey planner** (Gaussian-process acquisition
   weighing posterior uncertainty, proximity to the regulatory isohaline,
   travel and turn cost) — not formal expected information gain, and not
   claimed as such;
4. **GP reconstruction with explicit uncertainty**, exposed to the user;
5. **uncertainty-aware three-state screening** (CLEAR / REVIEW / POSSIBLE
   EXCEEDANCE) relative to a configurable mixing zone — screening, not
   certification;
6. **mission-updated digital record** that can be regenerated after every
   survey;
7. **simulator-agnostic architecture**: the mission layer sees an abstract
   backend, so the transfer path to the physical BlueROV2 (MAVLink/ArduSub)
   is a backend swap, not a rewrite;
8. **open, reproducible implementation** on standard, unmodified HoloOcean
   and its official Ocean package.

Target users who currently cannot run frequent vessel campaigns: small
utilities, municipalities, environmental regulators and university
laboratories in desalination-dependent regions.
