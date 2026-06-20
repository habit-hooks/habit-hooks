export const KNIP_CONFIG_FILENAME = 'knip.json';

export const KNIP_CONFIG_TEMPLATE = `{
  "entry": ["src/index.ts!", "src/cli.ts!", "tests/**/*.test.ts"],
  "project": ["src/**/*.ts!", "tests/**/*.ts"],
  "ignore": ["dist/**", "coverage/**"]
}
`;
