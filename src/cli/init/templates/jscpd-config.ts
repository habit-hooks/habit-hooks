export const JSCPD_CONFIG_FILENAME = '.jscpd.json';

export const JSCPD_CONFIG_TEMPLATE = `{
  "threshold": 0,
  "minTokens": 50,
  "minLines": 5,
  "ignore": ["**/node_modules/**", "**/dist/**", "**/*.test.ts", "**/*.spec.ts"]
}
`;
