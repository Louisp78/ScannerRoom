import sites from './sites.json'

/** A scanned site shown on the world map (US-1.1). */
export interface Site {
  /** Transect key, i.e. the folder name under public/transects/. */
  transectKey: string
  name: string
  /** WGS84 degrees, west and south are negative. */
  lat: number
  lon: number
}

// The list lives in sites.json so that the local ingest tool (vite-plugins/ingest.ts)
// can append to it. site3-transect2-south-return is placed approximately: NOAA
// accession 0172858 only gives a dataset-wide bounding box (west coast of Hawaii
// Island), not per-site coordinates, so it sits off the Old Kona Airport shoreline.
export const SITES: Site[] = sites
