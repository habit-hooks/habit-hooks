---
name: release-habit-hooks
description: "Cut a new release of the habit-hooks packages. Use when asked to release, publish, or bump the version. Reviews what lands, enforces the in-sync versioning rule, validates the changelog, and drives the tag-triggered PyPI publish."
---

# Release Habit Hooks

Five packages ship from this repo: `habit-hooks` (core), `habit-hooks-generic`,
`habit-hooks-python`, `habit-hooks-typescript`, `habit-hooks-php`. A `v*` tag
triggers `.github/workflows/release.yml`, which builds all five and publishes
each with `skip-existing: true` — so an unchanged package at an already-published
version is simply skipped. Publishing is irreversible: **never tag or push
without Ivett's explicit go-ahead.**

## 1. Review what lands

```
git describe --tags --abbrev=0            # last release tag
git log <lastTag>..HEAD --oneline
```

For each package, diff since the tag matching its *current* version and decide
if it changed:

```
git diff --stat <lastTag>..HEAD -- src/                    # core
git diff --stat <tagForItsVersion>..HEAD -- plugins/<name>/
```

A plugin's shipped package data (`eslint.config.mjs`, `knip.json`, `.jscpd.json`,
`ruff.toml`, sensors/guides) is consumer-facing — a change there means that
plugin changed. Read every diff; classify each as consumer-facing vs internal.

## 2. Versioning — all released packages stay in sync

- The new version is `max(all current package versions)` plus the appropriate
  semver bump. Decide the bump from what actually landed: **patch** for
  fixes/internal, **minor** only for genuinely new backward-compatible features.
- Bump **only the packages that changed** to that shared version (they may jump
  more than one patch to reach it — that's expected). Unchanged packages keep
  their current version and are skipped at publish time.
- Bump `version` in each changed package's `pyproject.toml`, then `uv lock` and
  confirm the lock shows the new versions. Core pins plugins as `~=1.0`, so a
  patch/minor bump needs no dependency-pin edits.

## 3. Validate the changelog

`CHANGELOG.md` must have a heading for **every** released version — no lingering
`## Unreleased` content that has actually shipped (this has bitten us: 1.0.0–1.0.2
all sat under a stale "Unreleased"). Before releasing:

- Every version between the last documented one and the new tag has its own
  `## X.Y.Z` section.
- The new version's section records the consumer-facing changes from step 1.
- Nothing under a version heading is actually unreleased.

## 4. Verify, then hand off

```
uv run pytest -q
uv build --all-packages --out-dir dist/_relcheck   # mirrors release.yml; check artifact versions
```

All green. Then present the tag command as a ⚠️ checkpoint for Ivett to run —
do not tag or push yourself:

```
git tag vX.Y.Z && git push origin main --tags
```
