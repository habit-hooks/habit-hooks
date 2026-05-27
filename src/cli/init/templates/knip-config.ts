export const KNIP_CONFIG_FILENAME = 'knip.json';

export const KNIP_CONFIG_TEMPLATE = `{
  "$schema": "https://unpkg.com/knip@5/schema.json",
  "entry": ["src/index.ts", "src/cli.ts"],
  "project": ["src/**/*.ts"],
  "ignore": ["dist/**", "coverage/**"]
}
`;
