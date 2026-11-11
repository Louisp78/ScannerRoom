# Underwater coastal mapping — Product specification

## Vision

A web application for viewing the world's coastal seabeds as an **"underwater Street View"**: a world map where every scanned stretch of coast can be explored in 3D, with continuous scrolling. The data is captured once (transect video), then presented differently depending on the audience.

---

## Target users

| Profile | Main need |
|---------|-----------|
| **Scientist / researcher** | Access detailed 3D models and metrics (rugosity, benthic cover), compare how a site evolves over time, export the raw data. |
| **Scuba diver** | Scout a site before a dive: depth, relief, visible marine life, difficulty. |
| **Snorkeler** | See at a glance whether a coastal spot is worth the trip (access, shallow depth, visual interest). |
| **Educational setting (teacher, outreach officer, student)** | Illustrate marine ecosystems, let people "visit" a seabed without diving, interactive course material. |

---

## Features & User stories

### 1. World coastline map

- **US-1.1** — As a user, I want to see a world map with scanned sites shown as points, so that I can spot where data exists.
- **US-1.2** — As a user, I want to click a point to open a light preview of the site (thumbnail, depth, marine life tags), so that I can decide whether to explore it.
- **US-1.3** — As a user, I want to filter sites (depth, audience, presence of coral/turtles/etc.), so that I can find what matches my need.
- **US-1.4** — As a user, I want only the points visible on screen to be loaded, so that the app stays smooth.

### 2. Scrollable 3D viewer

- **US-2.1** — As a user, I want to open a site's 3D reconstruction and navigate inside it, so that I can see the seabed.
- **US-2.2** — As a user, I want to move forward along the coast with continuous scrolling (like Street View), so that I can explore without switching "scenes".
- **US-2.3** — As a user, I want the heavy 3D model to load only on demand, so that I avoid needless loading times.
- **US-2.4** — As a scientist, I want to switch to a detailed view (metrics, history, export), so that I can use the data scientifically.

### 3. Tiling (streaming)

- **US-3.1** — As a user, I want the 3D scene to load in chunks (tiles) based on my virtual position, so that I can navigate long distances without downloading everything.
- **US-3.2** — As a user, I want an adaptive level of detail (LOD) depending on zoom, so that it is smooth from afar and precise up close.
- **US-3.3** — As a contributor, I want to upload a geolocated transect video, so that it is reconstructed and added to the map.

### 4. Accounts and access

- **US-4.1** — As a contributor, I want to sign in (ORCID or Google), so that only I (or an admin) can add and edit the biome areas of the transects I added, and so that my name is shown in the transect viewer. See [us-4.1-contributor-accounts.md](./us-4.1-contributor-accounts.md).
- **US-4.2** — As the project owner, I want the atlas and the transect viewer to be reserved to signed-in users, so that the data is shared with known people only.

---

## MVP scope

MVP goal: **validate the "underwater scroll" feel on a single transect**, with a minimal map.

### In the MVP

- **US-1.1** — World map with site points.
- **US-1.2** — Light preview when clicking a point.
- **US-2.1** — 3D viewer of a site.
- **US-2.2** — Scrolling along a predefined path (a single transect).
- **US-2.3** — On-demand loading of the 3D model.

### Out of the MVP (later versions)

- **US-1.3 / US-1.4** — Advanced filters and loading by area.
- **US-2.4** — Detailed scientific view + export.
- **US-3.1 / US-3.2** — Real tiling system + LOD at planetary scale.
- **US-3.3** — Automated upload and reconstruction pipeline.

---

## Technical notes (indicative)

- **3D rendering**: WebGL / Three.js in the browser.
- **Reconstruction method**: Gaussian Splatting preferred for high-resolution photorealistic rendering (a classic mesh, e.g. Meshroom, is possible for a first pass).
- **Streaming, eventually**: geo-indexed 3D tile format (e.g. a Cesium 3D Tiles approach) for continuous navigation.
- **Guiding principle**: a single raw data source, two presentation layers (lightweight for the general public / detailed for scientists).
