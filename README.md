# ScannerRoom

> **Explore the coast, one dive at a time.**

ScannerRoom is an **underwater Street View**: a world map of coastal seabeds,
where every scanned stretch of reef can be explored in 3D by scrolling along the
path the diver swam.

The data is captured once, as an ordinary video filmed by a diver along a
transect, and reconstructed into a 3D point cloud. The same data then serves
different audiences: scientists studying how a reef changes, divers and
snorkelers scouting a spot, teachers showing a seabed to people who will never
dive it.

## What it does today

- **Atlas**: a 3D globe showing the scanned sites.
- **3D viewer** of a transect: the reconstructed reef, the diver's trajectory and
  the source video, with continuous scrolling along the swim.
- **From video to 3D**: a diver's video goes through LingBot-Map, a 3D
  reconstruction model, then a cleaning and export step tuned for underwater
  footage (haze, open water, depth drift).
- **Contributor accounts** (ORCID or Google): each transect credits its
  contributor. The atlas is reserved to signed-in users, apart from a showcase
  transect on the landing page.

The first sites are 12 coral reef transects off the west coast of Hawaii Island,
from a public NOAA dataset ([accession 0172858](https://www.ncei.noaa.gov/access/metadata/landing-page/bin/iso?id=gov.noaa.nodc:0172858)).

Live at [scannerroom.louisplace.com](https://scannerroom.louisplace.com).

## How it is built

| Part | Stack |
| --- | --- |
| Web app | Vue 3, Three.js, Tailwind CSS, Vite |
| API | Node.js, Express, Drizzle ORM, PostgreSQL |
| Reconstruction | Python, [LingBot-Map](https://github.com/robbyant/lingbot-map) on Apple Silicon (MLX) |
| Hosting | Docker containers on a VPS, behind Cloudflare |

## Documentation

- [Product specification](docs/specs.md): vision, target users, user stories.
- [Brand identity](docs/brand.md).
- [Reconstruction pipeline](playground/README.md): how a video becomes a point
  cloud, and why each step is there.
- [3D viewer](docs/us-2.1-viewer-3d.md) and
  [contributor accounts](docs/us-4.1-contributor-accounts.md): design notes.
- [Contributing](CONTRIBUTING.md): local setup, conventions, adding and
  publishing a transect, deployment.
