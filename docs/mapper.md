# Mapper

The mapper **routes a smell to guidance**. It is a pure function:

```
smell key  ──►  GuideAction
```

One smell in, one action out. Everything tool- and language-specific was
already resolved by the sensor layer into a [smell key](smell-vocabulary.md).

## Config format

Mapping lives under `smells` in `habit-hooks.config.*`, keyed by smell:

```jsonc
{
  "smells": {
    "too-many-parameters": {
      "severity": "enforced",        // override the catalogue default
      "changedFilesOnly": false,
      "include": ["src/**"],
      "exclude": ["**/*.test.ts"]
    },

    "non-essential-comment": {
      "severity": "suggested"
    },

    "redundant-type-annotation": {
      "fix": "shared/style-nit.md"   // reuse a common template instead of <smell>.md
    },

    "warning-comment": {
      "disabled": true
    }
  }
}
```

Per-smell fields:

| Field                 | Meaning                                                                                                |
|-----------------------|--------------------------------------------------------------------------------------------------------|
| `severity`            | `enforced` (fails the run, exit 1) or `suggested` (coaches, exits 0). Defaults to the catalogue value. |
| `changedFilesOnly`    | Restrict to git-changed files.                                                                         |
| `include` / `exclude` | Glob filters (relative to config dir).                                                                 |
| `disabled`            | Drop this smell entirely.                                                                              |
| `fix`                 | Override the fix file. A `.md` file is rendered as a template; anything else is run as a script.       |

## GuideAction

The mapper groups the bag by smell and resolves each group to one action,
carrying its issues:

```ts
interface GuideAction {
  smell: string;
  severity: Severity;
  issues: Issue[];                          // every issue for this smell
  action:
    | { kind: 'prompt';  templatePath: string }   // rendered once over all issues
    | { kind: 'command'; scriptPath: string };    // run once, whole bag on stdin
}
```

## Fix resolution

The fix for a smell is the first of these that exists:

1. the `fix` setting, if set;
2. `<smell>.md` — rendered as a template;
3. the `<smell>` script — executed.

When both `<smell>.md` and a `<smell>` script exist with no `fix` set, the
markdown wins. The extension decides the action kind: `.md` is rendered,
anything else is executed.

Files are looked up first in the consumer's override dir (config `prompts`),
then the packaged default dir. A `fix` that names a missing file is a
configuration error surfaced at load time, not a silent skip.

## Totality

Every smell resolves to *something*. One with no fix (no setting, no
`<smell>.md`, no `<smell>` script) falls through to the **uncoached** bucket
(see [smell-vocabulary.md](smell-vocabulary.md)) rather than being dropped.
