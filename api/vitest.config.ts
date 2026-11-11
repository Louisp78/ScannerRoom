import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    // Tests share one database: run files one after the other.
    fileParallelism: false,
    env: {
      DATABASE_URL:
        process.env.TEST_DATABASE_URL ??
        'postgres://scannerroom_api:scannerroom@127.0.0.1:5432/scannerroom_test',
    },
  },
})
