/** A scanned site shown on the world map (US-1.1). */
export interface Site {
  /** Transect key, i.e. the folder name under public/transects/. */
  transectKey: string
  name: string
  /** WGS84 degrees, west and south are negative. */
  lat: number
  lon: number
}

export const SITES: Site[] = [
  {
    transectKey: 'site3-transect2-south-return',
    name: 'Old Kona, site 3 — transect 2 (retour sud)',
    // Approximate: NOAA accession 0172858 only gives a dataset-wide bounding
    // box (west coast of Hawaii Island), not per-site coordinates. Placed off
    // the Old Kona Airport shoreline until the exact position is known.
    lat: 19.645,
    lon: -156.025,
  },
]
