# Mapper

The mapper **routes a smell to guidance**. It is a pure function:

```
smell key  ──►  GuideAction
```

No tools, no detection, no combinations — one smell in, one action out.
Everything tool- and language-specific has already been resolved by the
sensor layer into a canonical [smell key](smell-vocabulary.md).

## Config format

Mapping lives under `smells` in `habit-hooks.config.*`, keyed by smell:

```jsonc
{
  "smells": {
    "too-many-parameters": {
      "severity": "enforced",        // override the catalogue default
      "changedFilesOnly": false,
      "include": ["src/**"],
      "exclude": ["**/*.test.ts"],
      "prompt": "too-many-parameters.md"   // optional; defaults to "<smell>.md"
    },

    "non-essential-comment": {
      "severity": "suggested"
    },

    "duplicated-code": {
      "command": "scripts/dedupe-report.sh ${file}"   // override action — see guide.md
    },

    "warning-comment": {
      "disabled": true
    }
  }
}
```

Per-smell fields:

| Field | Meaning |
|---|---|
| `severity` | `enforced` (blocks) or `suggested` (coaches, exits 0). Defaults to the catalogue value. |
| `changedFilesOnly` | Restrict to git-changed files. |
| `include` / `exclude` | Glob filters (relative to config dir). |
| `disabled` | Drop this smell entirely. |
| `prompt` | Guidance markdown filename. Defaults to `<smell>.md`. |
| `command` | Override: run a command instead of emitting the prompt (lowest-priority feature; see [guide.md](guide.md)). |

`prompt` and `command` are mutually exclusive. `prompt` is the default;
omit both to get `<smell>.md`.

## GuideAction

The mapper resolves each issue to:

```ts
type GuideAction =
  | { kind: 'prompt';  smell: string; severity: Severity; guidancePath: string }
  | { kind: 'command'; smell: string; severity: Severity; command: string };
```

## Prompt resolution

A smell's prompt file is found by:

1. the consumer's override prompts dir (config `prompts`), then
2. the packaged default prompts dir,

looking for `<prompt>` (or `<smell>.md` if `prompt` is unset). A missing
file is a configuration error surfaced at load time, not a silent skip.

## Totality

Every smell that reaches the mapper resolves to *something*. A smell with no
configured entry and no default prompt falls through to the **uncoached**
bucket (see [smell-vocabulary.md](smell-vocabulary.md)) rather than being
dropped — so unknown sensor output is always visible.
