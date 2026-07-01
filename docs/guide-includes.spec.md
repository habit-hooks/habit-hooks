# Guide template includes

A guide is a Jinja2 template rendered against its finding. The old wrapper
auto-appended the offending files and lines, so the prose-only prompts never had
to render them; that is no longer true, so each guide must now list **where** the
smell occurs. To avoid repeating the same listing in every guide, a guide pulls
in a shared partial with Jinja2 `{% include %}`.

## The issue-display contract

Each issue carries, in its `details`, the fields a shared listing renders:

| Field | Meaning |
|-------|---------|
| `file` | the path — always present |
| `line` | the row, for a point-located smell |
| `content` | **optional** — a snippet that may reveal a pattern across the listing, e.g. the function signature for `too-many-parameters`. Shown after the location when present, omitted when absent. |

`content` is deliberately not the linter's message: `Too many arguments (4 > 3)`
repeated down every line says little, whereas the real signatures lined up next
to each other often expose the shared shape that wants extracting.

Not every smell is point-located, so there are **two shared listings**, each a
partial under `guides/includes/`:

| Partial | Format per issue | Smells |
|---------|------------------|--------|
| `includes/line_level_issues.md` | `{{ file }}:{{ line }}` then `  {{ content }}` if present | too-many-parameters, oversized-function, high-complexity, deep-nesting, unused-variable, unused-import, swallowed-exception, loose-equality, var-declaration, non-const-binding, duplicate-import, explicit-any, non-null-assertion, redundant-type-annotation, warning-comment, non-essential-comment |
| `includes/file_level_issues.md` | `{{ file }}` then `  {{ content }}` if present | oversized-file, unused-file, unused-export, unused-dependency, parse-error |

A **special** smell whose issues do not fit either shape — `duplicated-code`,
whose issues come in matched pairs — does **not** use a shared include; its guide
lists the pairs inline. The shared includes exist only for the two typical shapes.

Partials live in an `includes/` subdirectory so they never collide with a
smell-named guide (`guides/<smell>.md`). They resolve through the **same override
chain as guides** — project `.habit-hooks/<plugin>/guides/includes/…` before the
plugin's package default, walking the ordered `plugins` list, then the core's
built-in partials as the final fallback — so a project can re-format a listing
once and every guide that includes it follows, and any plugin can rely on the two
shared partials whether or not `generic` is configured.

## The line-level listing

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/guides/includes/line_level_issues.md
```markdown
{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }}{% if issue.details.content %}  {{ issue.details.content }}{% endif %}
{% endfor -%}
```

### A point-located guide includes the line listing, with content

`too-many-parameters` is point-located (enforced). Each issue carries the
signature as `content`, so the listing lines the signatures up under each other.

📄.habit-hooks/generic/guides/too-many-parameters.md
```markdown
These functions take more than {{ details.maxAllowed }} parameters:

{% include "includes/line_level_issues.md" %}
Bundle related arguments into an object.
```

⌨️
```json
[
  {
    "smell": "too-many-parameters",
    "details": { "maxAllowed": 3 },
    "issues": [
      { "key": "src/billing.py:2", "details": { "file": "src/billing.py", "line": 2, "content": "bill(customer, items, discount, tax)" } },
      { "key": "src/orders.py:9", "details": { "file": "src/orders.py", "line": 9, "content": "place_order(cart, user, coupon, shipping, gift_wrap)" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── too-many-parameters (2 issues) ──

These functions take more than 3 parameters:

src/billing.py:2  bill(customer, items, discount, tax)
src/orders.py:9  place_order(cart, user, coupon, shipping, gift_wrap)

Bundle related arguments into an object.
```

### A point-located guide includes the line listing, without content

When a sensor emits no `content`, the same listing renders bare `file:line`.

📄.habit-hooks/generic/guides/non-null-assertion.md
```markdown
Replace these non-null assertions with a real check:

{% include "includes/line_level_issues.md" %}
A `!` hides a missing-value case rather than handling it.
```

⌨️
```json
[
  {
    "smell": "non-null-assertion",
    "details": {},
    "issues": [
      { "key": "src/config.ts:7", "details": { "file": "src/config.ts", "line": 7 } },
      { "key": "src/config.ts:9", "details": { "file": "src/config.ts", "line": 9 } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️
```text
── non-null-assertion (2 issues) ──

Replace these non-null assertions with a real check:

src/config.ts:7
src/config.ts:9

A `!` hides a missing-value case rather than handling it.
```

## The file-level listing

📄.habit-hooks/config.toml
```toml
plugins = ["generic"]
```

📄.habit-hooks/generic/guides/includes/file_level_issues.md
```markdown
{% for issue in issues -%}
{{ issue.details.file }}{% if issue.details.content %}  {{ issue.details.content }}{% endif %}
{% endfor -%}
```

### A whole-file guide includes the file listing

`oversized-file` is whole-file (enforced); its issues carry no `line`, and here
no `content`, so the listing is just the files.

📄.habit-hooks/generic/guides/oversized-file.md
```markdown
These files are over {{ details.maxAllowed }} lines:

{% include "includes/file_level_issues.md" %}
Split each file along a real seam.
```

⌨️
```json
[
  {
    "smell": "oversized-file",
    "details": { "maxAllowed": 200 },
    "issues": [
      { "key": "src/big.ts", "details": { "file": "src/big.ts" } },
      { "key": "src/huge.ts", "details": { "file": "src/huge.ts" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️ ❌ 1
```text
── oversized-file (2 issues) ──

These files are over 200 lines:

src/big.ts
src/huge.ts

Split each file along a real seam.
```

## Includes resolve through the plugin chain

A guide in one plugin may include a partial that only a later plugin ships; the
include resolves by walking `plugins` in order, exactly like a guide.

📄.habit-hooks/config.toml
```toml
plugins = ["typescript", "generic"]
```

### A guide includes a partial shipped by a later plugin

The `typescript` guide ships no `includes/` of its own; its `{% include %}`
falls through to the listing `generic` provides.

📄.habit-hooks/generic/guides/includes/line_level_issues.md
```markdown
{% for issue in issues -%}
{{ issue.details.file }}:{{ issue.details.line }}{% if issue.details.content %}  {{ issue.details.content }}{% endif %}
{% endfor -%}
```

📄.habit-hooks/typescript/guides/explicit-any.md
```markdown
Replace these `any` annotations with precise types:

{% include "includes/line_level_issues.md" %}
`any` opts out of type-checking exactly where you need it most.
```

⌨️
```json
[
  {
    "smell": "explicit-any",
    "language": "typescript",
    "details": {},
    "issues": [
      { "key": "src/api.ts:5", "details": { "file": "src/api.ts", "line": 5, "content": "fetchUser(id): any" } }
    ]
  }
]
```

```bash
habit-mapper
```

🖥️
```text
── explicit-any (1 issue) ──

Replace these `any` annotations with precise types:

src/api.ts:5  fetchUser(id): any

`any` opts out of type-checking exactly where you need it most.
```
