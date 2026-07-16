# Limitations — stated plainly

BrineWatch is an **Initial Prototype or Model**. The following limitations
are real, known and (where possible) measured. None of them is hidden in the
application material.

1. **The plume is an analytic surrogate, not CFD.** The salinity/temperature
   field is a controlled analytic surrogate that reproduces the main
   qualitative structure of a negatively buoyant discharge (near-field rise,
   collapse, diluting bottom-hugging gravity current, tidal advection). Its
   role is to provide exact, seedable ground truth so sampling strategies
   and reconstructions can be scored. Absolute PSU values and dilution
   distances must not be read as predictions for any real site.

2. **Water properties are virtual.** HoloOcean simulates vehicles, terrain
   and acoustics — not salinity. The virtual CT sensor samples the analytic
   field at the vehicle's pose with configurable noise. A physical
   conductivity–temperature payload exists only as a specified retrofit
   (see PHYSICAL_VALIDATION_PROTOCOL.md); it has not been built yet.

3. **Runtime-spawned geometry is not acoustically visible in official
   HoloOcean.** Verified by a controlled experiment (bit-identical sonar
   frames with and without spawned props, octree cache cleared per
   condition). The acoustic localization target in the official
   demonstration is therefore a stock world structure (PierHarbor pier
   pilings) standing in for the diffuser; the spawned outfall geometry is
   visual/collision only. The sonar pipeline itself (detection,
   range-bearing extraction, world-frame fusion, no-ground-truth
   localization) is validated against that official static target.

4. **Simulated-sonar-to-real-sonar domain gap.** HoloOcean's ray-cast
   ImagingSonar is not a physical Omniscan SS450. The detector's
   normalization and gating were tuned on simulated returns; thresholds will
   need re-tuning on real acoustics. What transfers is the architecture:
   frame geometry, recording/replay, detection→fusion→localization, and the
   no-ground-truth interface.

5. **Navigation is idealized.** The simulator provides near-perfect
   positioning; a real BlueROV2 needs DVL/USBL-aided navigation, with
   metre-level error that will propagate into the map. The GP framework can
   absorb position noise, but this is untested on hardware.

6. **No accredited field validation and no regulatory status.** The
   three-state output is uncertainty-aware *screening* that prioritises
   where accredited monitoring should look. It is not certification, and no
   regulator has endorsed it.

7. **Temporal dynamics are simplified.** The GP models a quasi-static
   field; the dynamic stress benchmark quantifies the degradation under
   tidal advection. A spatio-temporal kernel is documented future work.

8. **Single vehicle, controlled-world scale.** Missions are single-ROV in
   worlds of a few hundred metres; the demo mixing zone (40 m) is scaled
   down from real permits (100–300 m) to fit the official worlds. All radii
   are configuration parameters.

9. **Screening thresholds are configuration, not policy.** The CLEAR /
   REVIEW / POSSIBLE EXCEEDANCE cut-offs (P(exceed) 0.10 / 0.50, posterior
   std 0.75 PSU) are engineering defaults that a real deployment would set
   with the responsible authority.

10. **Physical tests not completed.** The team owns a BlueROV2 and a
    Cerulean Omniscan SS450; the CT payload integration, tank test and
    harbour trial are planned (protocol written) but not yet executed.
