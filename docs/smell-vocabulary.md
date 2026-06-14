# Smell vocabulary

The canonical, tool-independent catalogue of code smells Habit Hooks can
coach. Smell keys are the routing vocabulary: sensors translate raw tool
output *into* these keys, and the mapper routes *from* them to guidance.

## Naming rules

- **kebab-case**, lowercase, no namespace prefix (`too-many-parameters`,
  not `size/too-many-parameters` or `eslint:max-params`).
- Name the **smell**, never the tool or the tool's rule ID.
- A key may be language-specific (`explicit-any`) but must not be
  tool-specific.
- The default prompt file for a smell is `<smell>.md` (the key, verbatim).

## Catalogue

Each smell has a key, a human title, a one-line description, and a default
severity (`enforced` blocks the commit; `suggested` coaches but exits 0).
Severity is a default the mapper config can override per project.

| Smell key | Title | Default severity |
|---|---|---|
| `oversized-function` | Oversized function | enforced |
| `too-many-parameters` | Too many parameters | enforced |
| `high-complexity` | High cyclomatic complexity | enforced |
| `oversized-file` | Oversized file | enforced |
| `unused-variable` | Unused variable | enforced |
| `loose-equality` | Loose equality | enforced |
| `var-declaration` | `var` declaration | enforced |
| `non-const-binding` | Reassignable binding never reassigned | enforced |
| `duplicate-import` | Duplicate import | enforced |
| `warning-comment` | Warning comment (TODO/FIXME/…) | suggested |
| `explicit-any` | Explicit `any` | suggested |
| `non-null-assertion` | Non-null assertion | suggested |
| `redundant-type-annotation` | Redundant type annotation | enforced |
| `non-essential-comment` | Non-essential comment | suggested |
| `duplicated-code` | Duplicated code | suggested |
| `unused-class-member` | Unused class member | enforced |
| `unused-file` | Unused file | enforced |
| `unused-export` | Unused export | enforced |
| `unused-dependency` | Unused dependency | enforced |
| `parse-error` | Parse / config error | enforced |

## Migration from today's tool-prefixed keys

The current rule IDs map 1:1 onto smell keys. This table is the source of
truth for Phase 1's rekey and for the built-in sensors' translation tables.

| Old key (tool:rule) | Smell key |
|---|---|
| `eslint:max-lines-per-function` | `oversized-function` |
| `eslint:max-params` | `too-many-parameters` |
| `eslint:complexity` | `high-complexity` |
| `eslint:max-lines` | `oversized-file` |
| `eslint:no-unused-vars` | `unused-variable` |
| `eslint:eqeqeq` | `loose-equality` |
| `eslint:no-var` | `var-declaration` |
| `eslint:prefer-const` | `non-const-binding` |
| `eslint:no-duplicate-imports` | `duplicate-import` |
| `eslint:no-warning-comments` | `warning-comment` |
| `eslint:@typescript-eslint/no-explicit-any` | `explicit-any` |
| `eslint:@typescript-eslint/no-non-null-assertion` | `non-null-assertion` |
| `eslint:@typescript-eslint/no-inferrable-types` | `redundant-type-annotation` |
| `comment:non-essential` | `non-essential-comment` |
| `jscpd:duplication` | `duplicated-code` |
| `knip:classMembers` | `unused-class-member` |
| `knip:files` | `unused-file` |
| `knip:exports` | `unused-export` |
| `knip:dependencies` | `unused-dependency` |
| `eslint:fatal` | `parse-error` |

## Uncoached smells

A smell key that reaches the mapper with no configured guidance falls
through to an **uncoached** bucket rather than being dropped. The mapping is
intentionally total, so a new tool or sensor that emits an unknown smell is
surfaced (and tells us to add a prompt) rather than silently swallowed.
