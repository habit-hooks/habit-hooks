---
name: release-habit-hooks
description: "Cut a new release of the habit-hooks packages. Use when asked to release, publish, or bump the version. Reviews what lands, enforces the in-sync versioning rule, validates the changelog, and drives the tag-triggered PyPI publish."
---

# Release Habit Hooks

Six packages ship from this repo: `habit-hooks` (core), `habit-hooks-generic`,
`habit-hooks-python`, `habit-hooks-typescript`, `habit-hooks-php`,
`habit-hooks-java`. A `v*` tag
triggers `.github/workflows/release.yml`, which builds all six and publishes
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
- **Every package ships at that version**, changed or not. `pip install -U
  habit-hooks` upgrades a plugin only when the new core stops being satisfied by
  the installed one, so a plugin left behind hands someone the new core with last
  release's plugins. `tests/test_the_plugin_floor_tracks_the_release.py` gates it.
- Bump `version` in the core's `pyproject.toml` and in every
  `plugins/*/pyproject.toml`, **and raise each `habit-hooks-<name>` floor in the
  core's `dependencies` and `optional-dependencies` to the new minor.** Then
  `uv lock` and confirm the lock shows the new versions. The same test gates both
  halves, so a forgotten floor fails the suite rather than shipping quietly.
- The floor is spelled `>=X.Y.dev0,<2`, never `~=X.Y`. By PEP 440 ordering
  `X.Y.0rc1` sorts *below* `X.Y`, so `~=X.Y` makes a release candidate declare
  floors its own plugins cannot satisfy — and no `--pre` flag lifts it, because
  it is the specifier excluding the version, not a policy about candidates. The
  same spelling serves every rc and the final release, so nothing is rewritten
  at the tag.
- **A release candidate does not move the minor.** `X.Y.0rc1`, `rc2`, `rc3` are
  all pre-releases of the same `X.Y.0`; only the `version` lines move between
  them. Iterate as far as the reporters need.

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

## 5. An install instruction is verified from an install, never from empty

Anyone handed an install command already has habit-hooks — that is *why* they are
reading it. So test the command from their state, not from an empty machine:

```
export UV_TOOL_DIR=$(mktemp -d) UV_TOOL_BIN_DIR=$(mktemp -d)
uv tool install 'habit-hooks[typescript]'      # the version they are on now
uv tool install <the exact command about to be published>
"$UV_TOOL_BIN_DIR/habit-hooks" --version       # did it actually move?
```

`uv tool install` **does not upgrade an already-installed tool.** It prints
"already installed" and exits 0. It needs `--force`. 1.4.0rc1 was announced on
#133 and #134 without it; both reporters retested 1.3.1, and one reported a
1.3.1 bug back as an rc failure.

**`--force` is not enough either: it resolves from uv's cached index.** Anyone
who installed the previous version minutes ago has a cache that predates the
one just published, and uv answers `No solution found … there is no version of
habit-hooks[typescript]==X.Y.Z` for a version sitting on PyPI. So the published
command is

```
uv tool install --force --refresh 'habit-hooks[<extras>]==X.Y.Z'
```

and all three parts earn their place: the pin, because uv will not upgrade to a
pre-release without one; `--force`, because it skips a tool already installed;
`--refresh`, because its index cache does not know the release exists. rc3 was
caught by this step, with the packages already live on PyPI.

A fresh venv proves the package builds. It says nothing about the upgrade path,
and the upgrade path is the only one a reader takes.

## 6. Bump the Homebrew tap

Only after the PyPI publish — the formula pins each artifact's URL and
sha256 from PyPI, so the values don't exist until the release is live.
The `habit-hooks/homebrew-tap` repo's `Formula/habit-hooks.rb` carries the core's sdist URL +
sha256, one `resource` block per plugin with its own URL + sha256, and a
`test do` block asserting the exact list of plugin entry points.

- Move every resource block to the new version's URL + sha256. **A plugin
  new in this release needs its own resource block added**, not just the
  existing ones bumped — a missing one ships a `brew install` without that
  plugin.
- Add the new plugin to the `test do` block's asserted entry-point list.
- Open it as a **pull request** against the tap — never push to its `main`.
  `brew test-bot` builds bottles either way, but `publish.yml` (`brew
  pr-pull`) attaches them from a PR number; pushed straight to main, 1.2.1
  shipped with no bottles.
