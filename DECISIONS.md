# DECISIONS

Reversible design calls made by the autonomous loop while driving GOAL.md.
Each is labelled _agent decision_ per the working agreement.

## Phase 1 — Smell-key decoupling (TS, internal)

- **Routing keys become canonical smell keys.** _(agent decision)_ Each `Rule.id`
  and each `Violation.ruleId` is now a kebab-case smell key (e.g.
  `too-many-parameters`) instead of a tool-prefixed key (`eslint:max-params`).
  Tool-prefixed strings survive **only** as (a) the raw→smell translation tables
  owned by each wrap and (b) provenance written to `Violation.source`.

- **`Violation.source` added for provenance.** _(agent decision)_ Carries the raw
  tool key (`eslint:max-params`, `knip:classMembers`, `jscpd:duplication`,
  `comment:non-essential`). It is shown in the reporter's _Uncoached_ section so
  today's behaviour — surfacing the originating tool/rule for unknown findings —
  is preserved. Maps cleanly onto the future `Issue.details.source` (docs).

- **Unmapped raw keys pass through as their bare key.** _(agent decision)_ An
  eslint rule with no smell mapping (e.g. `no-console`) routes as `no-console`;
  an unknown knip issue type (e.g. `unlistedPeerDependencies`) routes under its
  bare key. No tool prefix leaks into the routing key; the finding still surfaces
  as uncoached with full provenance in `source`.

- **Catalogue content preserved verbatim.** _(agent decision)_ Titles,
  descriptions, and severities are copied unchanged from the old tool-keyed rules
  to guarantee output parity. Aligning titles with `docs/smell-vocabulary.md`
  (e.g. "Non-essential comment") is deferred as a separate content change.

- **`parse-error` stays a supplemental prompt** (no default `Rule`), exactly as
  the old `eslint:fatal` did — it has a tuned template but no catalogue entry.

## Phase 2 — Sensor contract + runner (leaf-only)

- **Phase 2 split into 2a + 2b.** *(agent decision)* 2a introduces the `Sensor` /
  `Issue` / `SensorContext` contract (`src/sensors/types.ts`) and a `SensorRunner`
  (`src/sensors/runner.ts`) that registers sensors, orders them by dependency, and
  merges issues — fully unit-tested in isolation, no pipeline integration yet. 2b
  makes the four wraps registered sensor plugins and wires them into `run()` with
  `Issue` <-> `Violation` conversion, preserving golden parity. The split keeps
  each commit small and reviewable, and de-risks the parity-sensitive integration.

- **`SensorRunner.run` returns `Issue[]`** per docs. *(agent decision)* Dependency
  ordering uses a stable topological sort (registration order preserved among
  ready sensors); unsatisfiable `dependsOn` smells and cycles throw at
  construction (startup error), per docs/sensors.md. Leaf-only is exercised by the
  preset; multi-sensor ordering/`ctx.deps` is implemented and tested with fakes but
  no multi sensor ships (out of scope).

- **2b integration: detect over all files, filter per smell afterwards.**
  *(agent decision)* `run()` runs every preset sensor over the full discovered
  file set via `SensorRunner`, then `filterViolations` keeps a violation only if
  its smell's rule allows the file (uncoached smells with no rule are never
  file-filtered). This replaces the old per-source dispatch (eslint union +
  `filterEslintViolations`, group-by-file-set for the rest) and lets the sensor
  stage stay a pure detector — the rule-scoped filtering is the seam the Phase 3
  mapper will own. Verified parity: CLI golden output byte-identical, full suite
  green. `src/eslint-runner.ts` deleted (its union/post-filter folded in).

- **Known, accepted divergence: knip findings are now baseline-filtered.**
  *(agent decision)* The old code never file-filtered knip output (knip runs
  whole-project); the new uniform filter drops a knip finding for a
  baseline-snoozed file (the `unused-class-member` rule has `changedFilesOnly:
  false`, so scope is unaffected; only baseline can drop it). This is unreachable
  by any existing test and not promised by the docs; treating a snoozed file as
  snoozed for every sensor is the more consistent behaviour, so it is accepted.
