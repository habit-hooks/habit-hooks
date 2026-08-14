import { createRequire } from "node:module";
import path from "node:path";

// This file is read from wherever habit-hooks is installed — for a consumer, a
// Python site-packages tree with no node_modules anywhere above it — so a bare
// `import` here resolves against THAT directory and dies with
// ERR_MODULE_NOT_FOUND. eslint itself comes from the project's own
// node_modules, so its parser and plugin are resolved from the project too.
const fromProject = createRequire(path.join(process.cwd(), "eslint.config.mjs"));

// This config runs only because the project has written none of its own, so the
// project has no reason to have typescript-eslint either — and eslint's own
// answer for that is a module-loader stack trace naming a package the reader
// never asked for. Say which config is running and what it needs instead.
const MISSING_TYPESCRIPT_ESLINT =
  "habit-hooks is linting with its own eslint config, because this project has " +
  "none. That config needs typescript-eslint in the project: npm install " +
  "--save-dev @typescript-eslint/parser @typescript-eslint/eslint-plugin";

function required(name) {
  try {
    return fromProject(name);
  } catch (error) {
    if (error.code !== "MODULE_NOT_FOUND") throw error;
    throw new Error(MISSING_TYPESCRIPT_ESLINT);
  }
}

const tseslint = required("@typescript-eslint/eslint-plugin");
const tsparser = required("@typescript-eslint/parser");

export default [
  {
    ignores: ["dist", "coverage", "tests/fixtures/**"],
  },
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.mjs", "**/*.cjs"],
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
      "max-depth": ["error", { max: 4 }],
      "max-lines": ["error", { max: 200, skipBlankLines: false, skipComments: false }],
      // Base off, TypeScript on — typescript-eslint's documented pairing. The
      // base rule cannot see type positions, so it reads an interface's method
      // parameter names as unused variables, and removing them is not valid
      // TypeScript.
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
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
];
