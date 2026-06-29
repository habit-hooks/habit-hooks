import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";

export default [
  {
    ignores: ["dist", "coverage", "tests/fixtures/**"],
  },
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsparser,
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      "max-lines-per-function": [
        "error",
        { max: 12, skipBlankLines: false, skipComments: false, IIFEs: true },
      ],
      "max-params": ["error", 3],
      complexity: ["error", 10],
      "max-lines": ["error", { max: 200, skipBlankLines: false, skipComments: false }],
      "no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/no-unused-vars": "off",
      eqeqeq: ["error", "always"],
      "no-var": "error",
      "prefer-const": "error",
      "no-duplicate-imports": "error",
      "no-warning-comments": [
        "warn",
        { terms: ["todo", "fixme", "xxx", "hack"], location: "anywhere" },
      ],
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-non-null-assertion": "warn",
      "@typescript-eslint/no-inferrable-types": "error",
    },
  },
  {
    files: ["**/*.test.ts", "**/*.spec.ts", "tests/**"],
    rules: {
      "max-lines-per-function": "off",
      "max-lines": "off",
    },
  },
];
