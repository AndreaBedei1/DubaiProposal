# Feasibility: official predefined levels under the custom engine fork

Requirement under investigation (consolidation work order §1): run the final
demonstration on an **official predefined HoloOcean level** using the
**custom fork engine** (runtime octree rebuild).

## Findings (verified 2026-07-17 on this machine)

1. **Ocean-package worlds ship only as cooked, packaged builds of the
   OFFICIAL engine.** The installed Ocean package
   (`%LOCALAPPDATA%/holoocean/…/worlds/Ocean`) is a WindowsNoEditor build:
   its maps cannot be opened by the fork's UE 5.3 editor, and the fork's
   octree-rebuild C++ cannot be injected into the packaged official binary.
2. **The engine SOURCE distribution does not include the Ocean worlds.**
   Two independent local checkouts were inspected —
   the custom fork (`client/`, `engine/`) and an official `HoloOcean-2.3.0`
   source checkout. Both contain exactly two maps:
   `Content/ExampleLevel.umap` and
   `Content/StarterContent/TestWorld/Maps/TestWorld.umap`. There is no
   `Worlds/` content, no PierHarbor/Dam/SimpleUnderwater/OpenWater source.
3. **Upstream cannot be fetched autonomously.** Neither checkout is a git
   repository (no `.git`, no LFS pointers). The BYU engine repository is
   EULA-gated (HTTP 404 anonymously; the org's only public repos are
   `holoocean-ros` and `holoocean-docs`).
4. **The fork's `ExampleLevel` is a MODIFIED copy of the upstream example
   level** (SHA256 differs from the official checkout; 72,598 vs 67,526
   bytes). The unmodified BYU-distributed `ExampleLevel.umap` exists in the
   official source checkout and is loadable by the fork engine (same UE 5.3
   Holodeck project layout).

## Conclusion

Running PierHarbor/FlatUnderwater/etc. under the custom fork is **not
technically achievable with the resources available on this machine**, and
not autonomously obtainable (EULA-gated upstream). This is a distribution
constraint of HoloOcean, not an integration failure.

## Adopted plan (best honest compromise)

Two-track demonstration with ONE authoritative outfall geometry:

- **Visual evidence + official-engine mission** — an official Ocean-package
  world (selection over the installed worlds, see the level evaluation).
- **Acoustic evidence + custom-engine mission** — the **unmodified,
  BYU-distributed `ExampleLevel`** (copied from the official 2.3.0 source
  checkout into the fork project), NOT the fork's locally modified variant.
  This level is engine-source content distributed by BYU: it is predefined,
  reproducible from the official distribution, and not purpose-built for
  this project. Its native clutter is measured explicitly (the modified
  variant used in the preliminary experiments is retired).

Final claim wording: *BrineWatch's visual scenes run in official Ocean-package
worlds on the unmodified HoloOcean engine; acoustic runtime-rebuild
experiments run on the BYU-distributed engine-source example level under the
custom fork, because Ocean worlds are distributed only as cooked builds of
the official engine.*

**Escalation path to full unification** (requires user action): obtain the
EULA-gated BYU engine repository with world sources (the fork's maintainers
had such access) — then the same Ocean world can host both tracks. The
adapter/geometry layer already supports this with no code changes.
