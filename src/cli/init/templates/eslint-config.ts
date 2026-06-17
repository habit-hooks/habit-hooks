import { TEST_FILE_EXCLUDE } from '../../../config/defaults.js';

export const ESLINT_CONFIG_FILENAME = 'eslint.config.js';

const testFileGlobs = TEST_FILE_EXCLUDE.map((glob) => `'${glob}'`).join(', ');

export const ESLINT_CONFIG_TEMPLATE = `import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  {
    ignores: ['node_modules', 'dist'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
    },
    rules: {
      'max-lines-per-function': ['error', { max: 12, skipBlankLines: false, skipComments: false, IIFEs: true }],
      'max-params': ['error', { max: 3 }],
      'complexity': ['error', { max: 10 }],
      'max-depth': ['error', { max: 4 }],
      'max-lines': ['error', { max: 200, skipBlankLines: false, skipComments: false }],
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      '@typescript-eslint/no-unused-vars': 'off',
      'eqeqeq': ['error', 'always'],
      'no-var': 'error',
      'prefer-const': 'error',
      'no-duplicate-imports': 'error',
      'no-warning-comments': ['warn', { terms: ['todo', 'fixme', 'xxx', 'hack'], location: 'anywhere' }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/no-inferrable-types': 'error',
    },
  },
  {
    files: [${testFileGlobs}],
    rules: {
      'max-lines-per-function': 'off',
      'max-lines': 'off',
    },
  },
);
`;
