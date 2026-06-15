# GOAL — Multi-language Habit Hooks (TypeScript + Python)

Operational North Star for the autonomous loop. Read this every iteration.
Stop when every box in **Definition of done** is checked.

## Mission

Refactor the existing TypeScript-only system into the
`sensor → mapper → guide` architecture in [`docs/`](docs/), and prove
multi-language support by adding a **Python preset** alongside the refactored
**TypeScript preset**. Prompts are **Nunjucks templates**.

The point is to validate that one prompt/mapper vocabulary serves multiple
languages by swapping only the sensor layer.

## Definition of done

Every item must be verifiable by a deterministic gate (test / grep / script).

**Architecture**
- [ ] Routing keys are canonical smell keys (kebab-case). No tool-prefixed
      keys (`eslint:` / `knip:` / `jscpd:`) survive as routing keys — they
      appear only inside sensor translation tables. (grep gate)
- [ ] `Sensor` contract + a **runner** that registers active sensors and
      merges their issues, per [`docs/sensors.md`](docs/sensors.md).
- [ ] Mapper is a pure `smell → fix` function with the `smells` config and
      the `fix` resolution chain, per [`docs/mapper.md`](docs/mapper.md).
- [ ] Guide renders **Nunjucks** templates per smell, per
      [`docs/guide.md`](docs/guide.md).

**TypeScript preset (parity with today)**
- [ ] `eslint`, `knip`, `jscpd`, `comment` refactored to the new contract,
      emitting smell keys per the translation table in
      [`docs/smell-vocabulary.md`](docs/smell-vocabulary.md).
- [ ] Parity test: every smell the old system fired still fires.

**Python preset (new)**
- [ ] `ruff` sensor → `high-complexity`, `too-many-parameters`,
      `oversized-function`, `unused-variable`, … (mapping below).
- [ ] `jscpd` → `duplicated-code` on `.py`.
- [ ] `deptry` → `unused-dependency`.
- [ ] `init` selects the language; only that language's sensors are active.

**Templating**
- [ ] All prompts render through Nunjucks (a static `.md` is the degenerate
      case).
- [ ] At least one smell (e.g. `oversized-function` grouped by file, or
      `duplicated-code` grouped by block) demonstrates real per-smell
      grouping over multiple issues.

**Quality gates**
- [ ] Full test suite green, zero warnings.
- [ ] `pnpm build` passes.
- [ ] e2e: a small **TS fixture repo** → expected smells (snapshot).
- [ ] e2e: a small **Python fixture repo** → expected smells (snapshot).
- [ ] CLI clean-run banner + violation-run output snapshots, both languages.

## Out of scope — do NOT build

- Multi / composite sensors and dependency resolution in the runner. Leaf
  sensors only; `dependsOn` / `ctx.deps` may exist in the types but stay
  unimplemented.
- Bash `command` fixes. Template/prompt fixes only.
- Repo rename, `npm publish`, merging to `main`.

## Phase plan

Run each phase through the full cycle from `CLAUDE.md`:
**implementer → lint/test → reviewer sub-agent → commit**. Never bundle
phases. Split any phase that looks like >50 implementer tool calls.

1. **Smell-key decoupling (TS, internal).** Add the smell key; move each
   wrap's raw→smell table in; rekey rule + prompt registries; rename prompt
   files to smell slugs. No behaviour change — snapshot parity.
2. **Sensor contract + runner (leaf-only).** Extract the `Sensor` interface;
   make the four TS wraps plugins; runner registers + merges.
3. **Mapper `smells` config + `fix` resolution.** Replace tool-keyed `rules`
   with smell-keyed `smells`; implement the `fix` chain.
4. **Nunjucks templating in the guide.** Render per smell over its issues;
   prove grouping on one smell.
5. **Declarative adapter + Python preset.** Build the adapter
   (`command`/`items`/`group`/`fields`/`map`); ruff + jscpd + deptry sensors.
6. **`init` language selection + e2e fixtures + hardening.**

**De-risk early:** before phase 5 build-out, validate the declarative adapter
against *live* `ruff --output-format=json` output **and** a captured ESLint
JSON sample (nested `group`/`items`). If the two-level model can't express
them, stop and flag — don't build the preset on an unproven adapter.

## Python smell mapping (starting point)

Refine and **label additions as agent decisions** in `DECISIONS.md`.

| Source            | Smell                  |
|-------------------|------------------------|
| ruff `C901`       | `high-complexity`      |
| ruff `PLR0913`    | `too-many-parameters`  |
| ruff `PLR0915`    | `oversized-function`   |
| ruff `F841`       | `unused-variable`      |
| jscpd             | `duplicated-code`      |
| deptry            | `unused-dependency`    |

Notes:
- TS-only smells (`explicit-any`, `var-declaration`, `non-const-binding`,
  `non-null-assertion`, `redundant-type-annotation`, `duplicate-import`)
  simply won't appear in the Python preset — expected.
- `oversized-file` has no clean ruff rule; best-effort (pylint `C0302`) or
  defer — agent decision.
- New general smells discovered (e.g. `unused-import` from ruff `F401`) may
  be added to the vocabulary; new Python-specific smells (e.g.
  `mutable-default-argument` from ruff `B006`) only if cheap.

## Environment setup (first action)

Verify and provision the toolchain; fail fast with a clear message if it
can't be:
- node + pnpm (`pnpm i`).
- python3 + pip (`pip install ruff deptry`).
- jscpd (`pnpm add -D jscpd` if absent).

## Working agreement

- Branch `goal/multi-language`. Commit per completed phase. Do not merge to
  `main`, push to a release, or publish.
- TDD throughout; reviewer sub-agent each phase before committing.
- Make reversible design calls and log them in `DECISIONS.md` labelled
  *agent decision*. Stop and wait on anything irreversible or expensive.
- Keep change sets small and reviewable.
