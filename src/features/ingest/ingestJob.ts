/** Contract of the local ingest endpoint (vite-plugins/ingest.ts), shared with IngestView. */
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
