# Transect sources

Where to find videos that can be published as transects, so that the project
does not depend on a single archive.

## What a good source needs

1. **Video quality**: continuous footage (not stills only), HD or better,
   steady motion along the seabed, clear water. Still-image sequences with
   strong overlap (one frame every second or less) can work too, but they are a
   second choice: the pipeline is built for video.
2. **Position**: a georeferenced track, the more precise the better. From best
   to worst:
   - **per-frame position** (RTK/differential GNSS on a surface camera, or USBL
     acoustic positioning on an ROV or towed sled): the transect can be placed
     on the map metre by metre;
   - **time-stamped boat or float GPS track** that can be synced with the video;
   - **one point per transect or per site**: enough for the map, not for
     aligning the reconstruction with the real world.
3. **Scientific origin**: a published dataset (DOI, metadata, method), from a
   research institute or agency, with a licence that allows reuse
   (public domain, CC0, CC BY; CC BY-NC is fine for a non-commercial project
   but must be checked).

## Sources

Status: **in use** (already published), **to check** (looks suitable, the
files, licence and track precision have not been verified yet), **unlikely**
(listed so it is not searched again).

### Diver or surface video over shallow reefs

| Source | Video | Position | Licence | Status |
| --- | --- | --- | --- | --- |
| [NOAA NCEI accession 0172858](https://www.ncei.noaa.gov/archive/accession/0172858): diver-swum reef transects, west Hawaii Island, 2017 (Seattle Aquarium) | MP4, ~10-12 min per transect, clear water | one point per site (~2 m), no track | US public domain | in use |
| [USGS DS 735](https://pubs.usgs.gov/publication/ds735): towed and drop camera video, Hawaiian nearshore waters, 2000s | digitised analog tapes, low resolution | boat GPS written onto the video; boat-to-camera offset unknown | US public domain | to check (quality likely too low) |
| [USGS Kona coast underwater images](https://cmgds.marine.usgs.gov/data-releases/datarelease/10.5066-P13ZPWNS): 2003, 2004 and 2022 surveys | stills; 2022 from a modern camera | differential GPS per image (2022) | US public domain | to check (stills) |
| [DeepReefMap example data](https://zenodo.org/record/10624794) (EPFL): diver ego-motion video for 3D reef mapping, Red Sea | GoPro Hero 10, made for 3D reconstruction | transect end points from marker buoys, if any are included | see Zenodo record | to check (position) |
| [XL Catlin Seaview Survey](https://web.library.uq.edu.au/research-tools-techniques/digital-researcher-lab/seaview-survey) (University of Queensland): km-scale reef surveys, worldwide | 360° and downward stills every few seconds, from a diver-propelled rig | GPS / USBL per image, according to the survey description | open access (check per dataset) | to check (stills) |
| [AIMS Long-term Monitoring Program, video and photo transects](https://eatlas.org.au/geonetwork/srv/api/records/5a8a4b00-4ade-11dc-8f56-00008a07204e), Great Barrier Reef | 50 m transects; stills every metre since 2007 | site coordinates | on request to the AIMS Data Centre (exclusive access periods) | unlikely (short, stills, restricted) |

### Towed camera arrays and AUVs (precise position)

| Source | Video | Position | Licence | Status |
| --- | --- | --- | --- | --- |
| [USGS SQUID-5, Looe Key, Florida](https://cmgds.marine.usgs.gov/data-releases/datarelease/10.5066-P9WSF09G) and [Eastern Dry Rocks](https://www.usgs.gov/data/overlapping-seabed-images-and-location-data-acquired-using-squid-5-system-eastern-dry-rocks): towed multi-camera array over coral reef | ~100 k overlapping stills per site, built for photogrammetry | GNSS per image (time, lat, lon, altitude) | US public domain | to check: the best position found so far |
| [USGS ATRIS, Crocker Reef, Florida](https://www.usgs.gov/data/atris-seafloor-images-crocker-reef-florida-2014) | ~25 k stills from a boat-towed shallow camera | GPS per image | CC0 | to check (stills) |
| [IMOS AUV imagery via Squidle+](https://data.gov.au/data/dataset/aeb48573-734c-4253-becc-d8c26db601c2) (Australia) | stereo stills from AUVs, plus towed, ROV and BRUV deployments | navigation track per deployment | CC BY 4.0 (one mirror says "not specified") | to check (stills, often deeper than reefs) |

### ROV and deep-sea video

Deep footage is lit by the vehicle's lamps, not by the sun: the scene looks
very different from shallow reefs, and the pipeline has not been tried on it.

| Source | Video | Position | Licence | Status |
| --- | --- | --- | --- | --- |
| [NOAA Ocean Exploration, Okeanos Explorer](https://oceanexplorer.noaa.gov/data/access-tools/) ROV dives (NCEI landing page per expedition, video portal) | HD ROV video | ROV navigation files per dive (USBL) | US public domain | to check |
| [Schmidt Ocean Institute, ROV SuBastian](https://docs.schmidtocean.org/Data-279cea10c32e8004aa87f15b44c30916) | 4K ROV video | vehicle and ship navigation per dive | CC BY-NC-SA 4.0 | to check |
| [PANGAEA](https://www.pangaea.de/) towed-camera and ROV video, e.g. RV Meteor cruise M182 (XOFOS, 4K, 25 fps, 13-15 min transects) | 4K towed video | ship USBL on several cruises | mostly CC BY 4.0; some under moratorium | to check |
| [Eiffel Tower dataset, Ifremer (SEANOE)](https://seanoe.org/data/00810/92226): hydrothermal vent revisited in 2015-2020 | images from ROV Victor6000 HD/4K cameras | navigation per image (lat, lon, altitude) | see SEANOE record | unlikely (one vent, very deep) |

## Leads not followed

- **NOAA PIFSC towed-diver surveys** (Pacific RAMP): boat GPS tracks every
  5 s are published ([NCEI 0189889](https://ncei.noaa.gov/archive/accession/0189889)),
  but the matching video does not appear to be archived.
- **Hawaii CRAMP video transects** (NCEI 0000671, 0001732): published as
  frame grabs only.
- **FLSea** (University of Haifa, Kaggle): visual-inertial image sets from the
  Mediterranean and Red Sea, built for SLAM; no geographic position.

## Next steps

1. Download one SQUID-5 site and see whether its image sequence reconstructs
   as well as video: it would give the most precise placement available.
2. Check the DeepReefMap data for GPS: it is the closest to our video
   (diver, GoPro, reef) outside NOAA.
3. Check one Okeanos Explorer dive end to end (video + USBL track), to learn
   whether deep ROV footage is worth supporting.
