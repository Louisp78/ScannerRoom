/** Contract of the local ingest endpoint, shared by the dev server plugin and the page. */
export const INGEST_ROUTE = '/__ingest/job'

export type IngestStep = 'upload' | 'extract' | 'reconstruct' | 'export' | 'register'

export interface IngestJob {
  key: string
  name: string
  status: 'running' | 'done' | 'failed'
  step: IngestStep
  error?: string
  /** Tail of the pipeline scripts' output. */
  log: string[]
}
