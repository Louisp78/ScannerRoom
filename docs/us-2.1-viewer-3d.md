# US-2.1 — 3D viewer of a site

> As a user, I want to open a site's 3D reconstruction and navigate inside it, so that I can see the seabed.

## Context

The 3D viewer is the core of the MVP: it must validate the "underwater scroll" feel (see specs.md). It will then be extended by US-2.2 (continuous scrolling along a transect), US-2.3 (on-demand loading), then US-2.4, US-3.1 and US-3.2 (scientific view, tiles, LOD). These next steps weighed on the choices below.

## Decisions

### GUI / 3D engine split

- **Application shell (GUI): Vue.** Handles the map, routing between the map and the viewer, panels and overlays (loading, site metadata).
- **3D engine: framework-agnostic Three.js module.** A standalone class owns the scene, camera, renderer, render loop and asset loading. Vue only mounts a canvas, instantiates the engine, destroys it on unmount, and talks to it through a light state bridge (store/callbacks: camera progress, loading state, selected site) rather than exposing individual 3D objects as reactive props.

**Why:** the rest of the roadmap (camera driven continuously along a path, tile streaming, LOD, then Gaussian Splatting rendering) is dominated by imperative, frame-by-frame systems with a lot of loading/unloading. Declarative wrappers (TresJS / React Three Fiber style) suit scenes that "react to props", not these hand-written systems — routing them through a reconciler would add a layer to fight rather than help. Moreover, Gaussian Splatting renderers are imperative by nature, with no mature declarative binding in any framework: the engine had to stay agnostic anyway.

**Implication:** the engine code (scene, camera, loaders, streaming, LOD) must stay out of Vue components. Vue components only mount/unmount the engine and relay a minimal reactive bridge. Do not introduce TresJS or an equivalent without explicitly revisiting this decision.

### 3D asset format (MVP)

- **Classic mesh (glTF/GLB)**, for instance from a Meshroom reconstruction — no Gaussian Splatting for the MVP.

**Why:** glTF/GLB benefits from mature Three.js tooling (`GLTFLoader`, Draco/meshopt compression, ready-made camera controls), which makes it quick to validate the navigation experience. Gaussian Splatting remains the long-term quality target (see specs.md) but adds tooling-immaturity risk and file weight that the MVP does not need.

## Other

- Detailed camera navigation model for US-2.1: free flight; load x tiles around the camera and, as it moves, load the matching tiles — like chunk loading in a video game.
- Folder structure / scaffolding of the Vue project:
  - eslint oxlint (use the up-to-date init command from the official site)
  - prettier
  - husky with a pre-commit lint, for conventional commit messages
  - GitHub CI with the job: build -> format, lint
