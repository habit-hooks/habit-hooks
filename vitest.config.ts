import { defineConfig } from 'vitest/config';

// testTimeout is raised above vitest's 5s default (agent decision): many
// tests spawn a real git repo and run real eslint/knip/jscpd, which exceeds
// 5s under parallel CPU contention. The higher bound still catches genuine
// hangs while removing the flakes.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
    exclude: ['**/node_modules/**', '**/dist/**', 'tests/fixtures/**'],
    testTimeout: 30_000,
  },
});
