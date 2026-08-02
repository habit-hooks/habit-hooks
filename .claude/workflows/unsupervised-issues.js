/*
 * unsupervised-issues — a small autonomous "agile team" that delivers the
 * issues labelled "ready for unsupervised" ONE AT A TIME, in ANY repository.
 *
 * Per issue the run does four steps:
 *   plan    -> pick the single best UNBLOCKED issue (reads the world fresh)
 *   precheck-> skip it if it is already implemented on the base
 *   impl    -> implement it end to end
 *   review  -> independently review + fix until it passes (up to N rounds); on the
 *              round it passes, the SAME reviewer runs the FULL CI suite and pushes
 *              once — no separate gate agent
 * …then it loops.
 *
 * PROJECT-AGNOSTIC BY DISCOVERY. Nothing about any one repo is hardcoded. The
 * Setup step inspects the checkout — CLAUDE.md / AGENTS.md, the CI workflow files,
 * the lockfiles and manifest scripts — and reports how THIS project installs,
 * tests and gates itself. Every later prompt is built from what it found. Pass
 * `args.gates` to override discovery when a repo's CI is too unusual to read.
 *
 * Two delivery modes, switchable live via the mode file (re-read every iteration):
 *   - "per-issue" (daytime, default): each issue lands on its OWN branch
 *     (unsupervised/issue-<n>) cut fresh from origin/<default>. Merge them as
 *     they land; good for parallelising small independent branches.
 *   - "sequential" (overnight): every issue is stacked, in order, on ONE shared
 *     branch (unsupervised/overnight). The first issue cuts it fresh from
 *     origin/<default> — unless the branch already exists with unmerged work, in
 *     which case the run ADOPTS it and continues stacking from its tip — and each
 *     later issue continues on top of the previous one. In the morning you review
 *     one branch instead of a pile.
 *
 * GIT MODEL — one checkout, nothing destructive. The run reuses ONE working
 * checkout for every agent and every issue. A FRESH issue (per-issue always, and
 * the FIRST sequential issue) moves it with `git checkout -B <branch>
 * origin/<default>`; a CONTINUING sequential issue re-anchors the shared branch
 * to the last good tip (`git checkout -B unsupervised/overnight <sha>`, where
 * <sha> is the tip the previous issue's review+gate step reported) — intentionally
 * leaving any failed later commits behind in the reflog. Every step commits its
 * work LOCALLY, so the checkout is already clean when the next step/issue takes
 * over. There is NO hard reset and NO force-push anywhere: if a checkout refuses
 * (unexpectedly dirty tree) the step stops and reports instead of resetting, and
 * the REVIEW+GATE step — the ONLY step that pushes, once per issue after the
 * review passes and the full suite is green — pushes plainly and reports (never
 * forces) if the remote branch has diverged from an earlier run. At startup an
 * existing unsupervised/overnight with unmerged work is ADOPTED — the run
 * continues from its tip instead of recutting (delete the branch for a clean
 * start); a diverged local/remote pair aborts setup for a human to reconcile.
 *
 * Signals (paths logged at startup; add both to .gitignore):
 *   - mode file  .unsupervised-issues.mode : write "overnight"/"sequential" or
 *     "daytime"/"per-issue" to switch mode live (takes effect on the NEXT issue).
 *   - stop file  .unsupervised-issues.stop : touch it to stop after the current
 *     issue lands. Stale stop files are cleared at startup.
 *
 * UNBLOCKED = every issue it depends on is already on the base it builds on:
 * per-issue -> the dependency must be merged/closed on origin/<default>;
 * sequential -> a dependency delivered earlier THIS run already counts (it is
 * stacked on the shared branch). When nothing is startable, the run stops.
 *
 * No writes to GitHub are made. Needs the repo checkout and a clean working tree.
 * GitHub is read through the `gh` CLI when present, otherwise the GitHub MCP
 * tools — Setup detects which.
 *
 * Run:   Workflow({ name: 'unsupervised-issues', args: { mode: 'sequential' } })
 * Args (all optional):
 *   { label:  'ready for unsupervised', // issue label to pull from
 *     maxReviewRounds: 3,               // review->fix iterations before giving up
 *     mode: 'per-issue',                // starting mode: 'per-issue' | 'sequential'
 *     gates: ['pnpm test'],             // override the discovered full-suite gate
 *     stopFile: '<repoRoot>/.unsupervised-issues.stop',
 *     modeFile: '<repoRoot>/.unsupervised-issues.mode' }
 */

export const meta = {
  name: 'unsupervised-issues',
  description: 'Deliver ready-for-unsupervised issues one at a time in any repo; per-issue branches (daytime) or one shared stacked branch (overnight), switchable live',
  phases: [
    { title: 'Setup', detail: 'verify clean tree + GitHub access, discover the project\'s install/test/gate commands, find default branch' },
    { title: 'Deliver', detail: 'loop: read mode -> pick next unblocked issue -> implement -> review loop (on pass: full-suite gate + push)' },
  ],
}

// ---------------------------------------------------------------- config
// `args` may arrive as an object, or — a caller footgun — as a STRING: either a
// JSON object literal ('{"mode":"sequential"}') or the loose "key: value" form
// the skill card documents (args: "mode: sequential"). Historically the config
// did `const A = args || {}` and read `A.mode` directly, so a stringified arg
// made `A.mode` undefined and EVERY parameter silently collapsed to its default
// (a "sequential" request quietly ran per-issue). Coerce every accepted shape to
// an object so that can never happen unnoticed again.
function coerceArgs(raw) {
  if (raw == null) return {}
  if (typeof raw === 'object') return raw
  if (typeof raw !== 'string') {
    throw new Error(`unsupervised-issues: unsupported args type "${typeof raw}" — pass an object like { mode: 'sequential' }.`)
  }
  const s = raw.trim()
  if (!s) return {}
  if (s.startsWith('{') || s.startsWith('[')) {
    try {
      const parsed = JSON.parse(s)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed
      throw new Error('parsed value is not an object')
    } catch (e) {
      throw new Error(`unsupervised-issues: args looked like JSON but did not parse to an object: ${e && e.message ? e.message : e}`)
    }
  }
  // Loose "key: value[, key: value]" form. A bare token with no ':' (e.g.
  // "sequential") is taken as the mode, matching the skill card's shorthand.
  const obj = {}
  for (const part of s.split(',')) {
    const seg = part.trim()
    if (!seg) continue
    const i = seg.indexOf(':')
    if (i === -1) {
      obj.mode = seg
      continue
    }
    const k = seg.slice(0, i).trim()
    const v = seg.slice(i + 1).trim()
    if (k) obj[k] = v
  }
  return obj
}
const A = coerceArgs(typeof args === 'undefined' ? null : args)

const SEQ_MODE_ALIASES = new Set(['sequential', 'overnight', 'night', 'single'])
const PER_ISSUE_MODE_ALIASES = new Set(['per-issue', 'per_issue', 'perissue', 'daytime', 'day'])
// Used ONLY for the START-MODE ARG. Unlike the live mode file (where any
// unrecognized content intentionally means per-issue), an explicitly-supplied
// but unrecognized `mode` arg is a caller mistake — fail loudly rather than
// silently defaulting, so a typo like mode:"seqential" can't run the wrong mode.
function startModeFromArg(m) {
  if (m == null || String(m).trim() === '') return 'per-issue' // unspecified → default
  const s = String(m).trim().toLowerCase()
  if (SEQ_MODE_ALIASES.has(s)) return 'sequential'
  if (PER_ISSUE_MODE_ALIASES.has(s)) return 'per-issue'
  throw new Error(`unsupervised-issues: unrecognized mode "${m}" — use "sequential"/"overnight" or "per-issue"/"daytime".`)
}
function positiveIntArg(v, dflt) {
  if (v == null || String(v).trim() === '') return dflt
  const n = Number(v)
  if (!Number.isInteger(n) || n < 1) {
    throw new Error(`unsupervised-issues: maxReviewRounds must be a positive integer, got "${v}".`)
  }
  return n
}
// A caller-supplied gate override may be an array or a single string.
function listArg(v) {
  if (v == null) return null
  const list = Array.isArray(v) ? v : [String(v)]
  const cleaned = list.map((s) => String(s).trim()).filter(Boolean)
  return cleaned.length ? cleaned : null
}
const cfg = {
  label: A.label || 'ready for unsupervised',
  maxReviewRounds: positiveIntArg(A.maxReviewRounds, 3),
  startMode: startModeFromArg(A.mode),
  gatesOverride: listArg(A.gates),
}

// ---------------------------------------------------------------- schemas
// Setup both PREPARES the run and DISCOVERS how this project builds itself.
// Everything the later prompts say about installing, testing and gating comes
// from these fields — that is what makes the workflow repo-independent.
const SETUP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok', 'reason'],
  properties: {
    ok: { type: 'boolean' },
    reason: { type: 'string' },
    repoRoot: { type: 'string' },
    defaultBranch: { type: 'string', description: 'the remote default branch name, e.g. main' },
    owner: { type: 'string', description: 'GitHub repo owner parsed from the origin remote' },
    repo: { type: 'string', description: 'GitHub repo name parsed from the origin remote' },
    hasGhCli: { type: 'boolean', description: 'true if the `gh` CLI is installed AND authenticated in this environment' },
    installCommand: { type: 'string', description: "how this project installs dependencies, e.g. 'pnpm install --frozen-lockfile' or 'uv sync --frozen'. Empty string if it needs none." },
    fullGate: {
      type: 'array',
      items: { type: 'string' },
      description: 'the ordered shell commands a branch must pass before it is mergeable — the local equivalent of this repo\'s CI. Cheapest/fastest first where CI allows.',
    },
    narrowTestGuidance: {
      type: 'string',
      description: 'one or two sentences telling an agent how to run the NARROWEST useful subset of tests for a change in this repo (e.g. "uv run pytest tests/test_x.py", "pnpm --filter <pkg> test"), plus any linter/typecheck to run alongside.',
    },
    heavySuites: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['command', 'paths'],
        properties: {
          command: { type: 'string', description: 'the expensive suite command' },
          paths: { type: 'string', description: 'the path prefix(es) whose changes make this suite relevant, e.g. "apps/editor/"' },
          note: { type: 'string', description: 'any setup needed before running it, e.g. freeing a port' },
        },
      },
      description: 'expensive/self-contained suites worth skipping when the diff does not touch their area. Empty array if the project has none.',
    },
    contracts: {
      type: 'array',
      items: { type: 'string' },
      description: 'files/interfaces this repo treats as human-gated (a published API, a plugin contract, a schema). An agent must stop and report rather than change these. Empty array if none.',
    },
    projectRules: {
      type: 'string',
      description: 'a short digest of the repo-specific non-negotiables found in CLAUDE.md / AGENTS.md / CONTRIBUTING that an implementer must obey (commit conventions, forbidden shortcuts, gate rules). Empty string if there are none.',
    },
    overnightState: { type: 'string', enum: ['absent', 'stale', 'adopt'], description: 'pre-existing shared overnight branch: absent (none), stale (fully merged into origin/<default>), adopt (has unmerged work — the run continues from it)' },
    overnightTip: { type: 'string', description: 'when overnightState="adopt", the commit SHA the shared branch continues from' },
  },
}

// One agent call per iteration decides the next unit of work by re-reading the
// world: it fetches the base, lists open labelled issues, works out
// dependencies, and returns the single best UNBLOCKED issue to start next.
const PICK_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['stopRequested', 'waitingForMerge', 'mode'],
  properties: {
    stopRequested: { type: 'boolean', description: 'true if the stop file exists' },
    mode: {
      type: 'string',
      enum: ['per-issue', 'sequential'],
      description: 'the delivery mode read from the mode file this iteration: "sequential" if the file exists and names overnight/sequential, otherwise "per-issue"',
    },
    next: {
      anyOf: [
        { type: 'null' },
        {
          type: 'object',
          additionalProperties: false,
          required: ['number', 'title', 'isBug', 'isHigh'],
          properties: {
            number: { type: 'integer' },
            title: { type: 'string' },
            isBug: { type: 'boolean' },
            isHigh: { type: 'boolean' },
          },
        },
      ],
      description: 'the single best unblocked issue to start now, or null if none is startable',
    },
    waitingForMerge: {
      type: 'boolean',
      description: 'true if there are undelivered issues that are blocked ONLY by branches this run already delivered but that are not yet merged to main — i.e. they would unblock once the human merges',
    },
    remaining: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['number', 'reason'],
        properties: { number: { type: 'integer' }, reason: { type: 'string' } },
      },
      description: 'open, not-yet-handled issues that were NOT picked, each with a short reason',
    },
    notes: { type: 'string' },
  },
}

const PRECHECK_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['alreadyDone'],
  properties: {
    alreadyDone: { type: 'boolean', description: 'true if the issue is already fully implemented on the base this issue would build on' },
    reason: { type: 'string', description: 'brief evidence for the verdict' },
  },
}

const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok', 'summary'],
  properties: {
    ok: { type: 'boolean', description: 'true only if complete and the targeted tests + typecheck are green' },
    summary: { type: 'string' },
    reason: { type: 'string', description: 'if ok=false, why' },
  },
}

// The review step is also the GATE now: on the round it finds no blocking
// problems, the SAME reviewer runs the full CI suite and pushes once — there is
// no separate gate agent. So its schema carries both the review verdict
// (pass/blocking) and the gate outcome (green/pushed/headSha), the latter present
// whenever the reviewer actually ran the gate (i.e. when pass=true).
const REVIEW_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['pass', 'blocking'],
  properties: {
    pass: { type: 'boolean', description: 'true iff the reviewer found NO blocking problems — it then ran the full CI gate and pushed. false means blocking problems remain for a fix agent to address before re-review.' },
    blocking: { type: 'array', items: { type: 'string' }, description: 'problems that must be fixed before merge' },
    green: { type: 'boolean', description: 'when pass=true: whether the FULL test suite passed on the branch' },
    pushed: { type: 'boolean', description: 'when pass=true: whether the branch was pushed to origin' },
    headSha: { type: 'string', description: 'output of `git rev-parse HEAD` after all gate work is committed — REQUIRED whenever the gate ran (pass=true). The branch tip this step leaves behind.' },
    summary: { type: 'string' },
    notes: { type: 'string' },
    reason: { type: 'string', description: 'if not green or not pushed, a short failure summary' },
  },
}

const FIX_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['ok'],
  properties: { ok: { type: 'boolean' }, reason: { type: 'string' } },
}

// ---------------------------------------------------------------- discovered project profile
// Filled in by Setup. Every prompt fragment below is a FUNCTION of these, which
// is what keeps the workflow free of any one repo's commands.
let repoRoot = ''
let defaultBranch = 'main'
let owner = ''
let repo = ''
let stopFile = ''
let modeFile = ''
let hasGhCli = false
let installCommand = ''
let fullGate = []
let narrowTestGuidance = ''
let heavySuites = []
let contracts = []
let projectRules = ''

// ---------------------------------------------------------------- shared prompt fragments

// Universal engineering standards, plus whatever Setup read out of the repo's
// own CLAUDE.md / AGENTS.md. Nothing here names a command or a path: the
// project-specific half arrives via `projectRules` and `contracts`.
const principles = () => {
  const lines = [
    "Follow the repo's own CLAUDE.md / AGENTS.md / CONTRIBUTING (read them — they outrank these defaults where they conflict). Non-negotiables:",
    '- TDD: write or extend a FAILING test first, then make it pass. Show the regression red against the unfixed code before fixing.',
    '- Zero warnings and zero errors when you are done — a warning you introduced is a failure.',
    '- KISS: small single-responsibility functions, self-documenting names, no dead code.',
    '- No code duplication — reuse or extract shared logic instead of copy-pasting.',
    '- Test code is production code: never exempt tests from lint/complexity/quality gates to make them pass.',
    '- Never silence a quality gate to get past it (no new suppressions, baselines, snoozes, skips, or ignore entries for debt YOU introduced) — fix the code instead.',
    "- Stay strictly within the issue's scope. Log unrelated problems in your result; do not fix them.",
    '- Any browser automation runs HEADLESS.',
  ]
  if (contracts.length) {
    lines.push(`- Do NOT change these human-gated contracts: ${contracts.join(', ')}. If the issue seems to require it, STOP and report instead of changing them.`)
  }
  if (projectRules) lines.push('', `Repo-specific rules discovered from this project's own docs:\n${projectRules}`)
  return lines.join('\n')
}

// GitHub access differs by environment: a local machine usually has `gh`, a
// sandboxed/cloud one often only has the GitHub MCP tools. Setup detects which,
// so neither is assumed.
const ghNote = () =>
  hasGhCli
    ? `Use the \`gh\` CLI for GitHub reads (it is installed and authenticated here). Repository: ${owner}/${repo}.`
    : `There is NO \`gh\` CLI in this environment. Use the GitHub MCP tools instead — load their schemas first with ToolSearch (e.g. \`select:mcp__github__issue_read,mcp__github__list_issues\`). Repository: owner="${owner}", repo="${repo}".`

const readIssue = (n) =>
  hasGhCli
    ? `Read issue #${n} with \`gh issue view ${n} --repo ${owner}/${repo} --json title,body,labels\` (add \`--comments\` if you need the discussion).`
    : `Read issue #${n} via the GitHub MCP tool \`mcp__github__issue_read\` (method="get", owner="${owner}", repo="${repo}", issue_number=${n}); use method="get_comments" if you need the discussion.`

const listIssuesInstruction = () =>
  hasGhCli
    ? `List every OPEN issue with the label using \`gh issue list --repo ${owner}/${repo} --state open --label "${cfg.label}" --limit 100 --json number,title,labels\`.`
    : `List every OPEN issue labelled "${cfg.label}" with \`mcp__github__list_issues\` (owner="${owner}", repo="${repo}", state="OPEN", labels=["${cfg.label}"]). Fetch modest pages (perPage ~30) if the payload is large.`

// The branch must pass what THIS repo's CI runs — discovered, never assumed.
const gateNote = () =>
  fullGate.length
    ? `This project's merge gate, in order:\n${fullGate.map((c, i) => `  ${i + 1}. ${c}`).join('\n')}\nA branch is not deliverable until every one of these is green. Make sure CI will pass before you consider the issue delivered.`
    : 'No full-suite gate was discovered for this project. Run whatever test/lint/build commands the repo documents, and say in your result which you ran.'

const narrowNote = () =>
  narrowTestGuidance
    ? `Run the NARROWEST sufficient checks for what you changed before committing: ${narrowTestGuidance}`
    : 'Run the narrowest sufficient checks for what you changed before committing (the relevant package/module tests plus a lint or typecheck).'

// Generalises the "don't run the slow, unrelated suite" rule: an expensive suite
// is skipped unless the diff actually touches its area. The final gate runs
// everything once, so skipping during review/fix rounds is correct, not a shortcut.
const heavySuiteNote = (baseRef) => {
  if (!heavySuites.length) return ''
  const rows = heavySuites
    .map((s) => `  - \`${s.command}\` is only relevant to changes under ${s.paths}.${s.note ? ` Before running it: ${s.note}` : ''}`)
    .join('\n')
  return `SCOPE YOUR TESTS. First list this change's files: \`git diff --name-only ${baseRef}...HEAD\`. This project has expensive suites that are self-contained:\n${rows}\nRun such a suite ONLY when a changed file falls under its paths; otherwise skip it and say so in your summary. The final gate covers everything once.`
}

// ---------------------------------------------------------------- git model
const SEQ_BRANCH = 'unsupervised/overnight'
const branchFor = (n) => `unsupervised/issue-${n}`

// Mode in force for the CURRENT issue (re-read from the mode file each iteration).
// `seqEstablished`/`seqBaseRef` track the shared branch: once a sequential
// issue's gate REPORTS the branch tip (headSha), the branch is established and
// the next sequential issue continues from that tip. Keyed off the gate's
// report, NOT its push or greenness — so a rejected/blocked push can never make
// the next issue recut the shared branch over already-delivered work. Setup may
// also pre-establish the branch by adopting an existing tip with unmerged work.
let mode = cfg.startMode
let seqEstablished = false
let seqBaseRef = ''

// planFor(issue) resolves the mode + run state into the concrete git plumbing:
//   branch  - where the issue's work goes
//   baseRef - the ref it builds on: origin/<default> for a fresh start, or the
//             last good shared-branch tip for a continuing sequential issue
//   sequential/continues/fresh - mode flags (fresh = the branch is (re)created
//             at origin/<default>: per-issue always, and the FIRST sequential
//             issue when no existing overnight branch was adopted)
function planFor(issue) {
  const sequential = mode === 'sequential'
  const continues = sequential && seqEstablished
  return {
    sequential,
    continues,
    fresh: !continues,
    branch: sequential ? SEQ_BRANCH : branchFor(issue.number),
    baseRef: continues ? seqBaseRef : `origin/${defaultBranch}`,
  }
}

// Put the shared checkout onto the issue's base. Nothing destructive: every step
// commits its work, so the tree is expected clean; if a checkout refuses anyway,
// the agent stops and reports rather than resetting. Re-anchoring a continuing
// branch with `checkout -B` intentionally leaves any failed later commits
// behind (the reflog keeps them).
const startOnBase = (plan) =>
  `Put the checkout on the base this issue builds on. The run reuses ONE checkout across issues:
${plan.fresh ? `  git fetch origin ${defaultBranch}\n` : ''}  git checkout -B ${plan.branch} ${plan.baseRef}
If the checkout refuses (e.g. unexpected local changes), do NOT delete or discard anything — no hard resets, no cleans, no force flags. Stop and report the blockage in your result instead; a human will look.`

const startDesc = (plan) =>
  plan.continues
    ? `${plan.branch}, continuing on top of previously stacked issues (tip ${plan.baseRef})`
    : plan.sequential
      ? `the shared overnight branch ${plan.branch}, started fresh from origin/${defaultBranch}`
      : `its own branch ${plan.branch}, built fresh from origin/${defaultBranch}`

const workspaceDesc = (plan) => `the main checkout, currently on branch ${plan.branch}`

const installNote = () =>
  installCommand
    ? `Dependencies are already installed in this checkout; re-run \`${installCommand}\` only if the fetch changed a lockfile or manifest.`
    : 'Dependencies are already installed in this checkout.'

// Every delivery step commits LOCALLY and NEVER pushes — the review+gate step is
// the only pusher. Committing (even WIP on failure) keeps the reused checkout
// clean so the next step/issue starts from a clean base without any tree-wide
// reset. The committer identity is whatever the environment provides — the step
// does not set or verify an author.
const commitLocally = (issue, plan) =>
  `Commit your work LOCALLY on ${plan.branch} with a clear message referencing #${issue.number}, following any commit conventions the repo documents. Do NOT push — only the review+gate step pushes, once the review passes; your commit stays local for the later steps to build on. Always leave the working tree CLEAN (everything committed) so the next issue starts from a clean checkout.`

// The review+gate step's single push is always a PLAIN push — never a force. A
// rejected push (stale diverged remote branch from an earlier run) is reported
// for a human to resolve, not overwritten.
const pushCmd = (plan) => `git push -u origin ${plan.branch}`

// ---------------------------------------------------------------- delivery steps

// Safety net: some issues are fixed but left open. Before spending a full
// implement/review cycle, verify on the base this issue would build on that the
// issue isn't already done. If it is, we skip it and report it — no writes.
async function precheck(issue, plan) {
  return agent(
    `Decide whether GitHub issue #${issue.number} ("${issue.title}") is ALREADY fully implemented on ${plan.baseRef} — the base this issue would build on. Some issues are fixed but left open, and we must not redo them.
Inspect the base READ-ONLY — do NOT checkout, reset, or modify the working tree or any branch. ${plan.fresh ? `First \`git fetch origin ${defaultBranch}\`. ` : ''}Read code directly from the ref: \`git log ${plan.baseRef}\`, \`git show ${plan.baseRef}:<path>\`, \`git grep <pattern> ${plan.baseRef} -- '<glob>'\`, \`git ls-tree -r --name-only ${plan.baseRef}\`.
${ghNote()}
${readIssue(issue.number)} Read its acceptance criteria, then judge whether they are ALREADY satisfied on ${plan.baseRef}.
Do NOT implement or change anything. Return alreadyDone=true ONLY if you are confident every acceptance criterion is already met; otherwise alreadyDone=false. Give brief evidence in reason.`,
    { label: `precheck #${issue.number}`, phase: 'Deliver', schema: PRECHECK_SCHEMA },
  )
}

async function implement(issue, plan) {
  return agent(
    `Implement GitHub issue #${issue.number} ("${issue.title}").

${startOnBase(plan)}
You are now on ${startDesc(plan)}. ${installNote()}

${ghNote()}
${readIssue(issue.number)} Then implement it end to end.
${principles()}
${gateNote()}

${narrowNote()}
${heavySuiteNote(plan.baseRef)}
${commitLocally(issue, plan)}
If you cannot reach green, still commit your progress LOCALLY and return ok=false with the blocking reason — but leave the tree clean.`,
    { label: `impl #${issue.number}`, phase: 'Deliver', schema: IMPL_SCHEMA },
  )
}

// Review AND gate in one step. Each round an independent reviewer checks the
// change; if it finds BLOCKING problems it returns them (a fix agent addresses
// them, then we review again). On the round it finds NONE, the SAME reviewer runs
// the FULL CI suite and pushes once — this merged step is the ONLY pusher, so
// there is no separate gate agent re-paying for the suite. Its result carries the
// gate outcome (green/pushed/headSha) used to advance the sequential base.
async function reviewLoop(issue, plan) {
  let review = null
  let round = 0
  while (round < cfg.maxReviewRounds) {
    round++
    review = await agent(
      `Independently review AND gate the change for GitHub issue #${issue.number} ("${issue.title}"), working inside ${workspaceDesc(plan)}.
${ghNote()}

STEP 1 — REVIEW. Confirm it FULLY satisfies the issue's acceptance criteria (${readIssue(issue.number)}) and judge it against these principles:
${principles()}
For a visual/UI issue, drive it in HEADLESS browser automation and confirm the described behaviour. At this stage run only the NARROW checks you need to judge correctness — do not re-implement.
If you find ANY BLOCKING problem (incorrect, incomplete, violates the principles, or would fail CI): STOP HERE — return pass=false with a concrete list of BLOCKING problems, each independently checkable. Do NOT run the full suite or push; a fix agent will address them and you will review again. Leave the tree committed and clean.

STEP 2 — GATE + PUSH (only when STEP 1 found NO blocking problem). The change is merge-ready, so you now run the CI dress-rehearsal and push — there is NO separate gate step. This is the ONLY step that pushes ${plan.branch}: commit everything locally, get the gate green, then push once.
${gateNote()}
${heavySuiteNote(plan.baseRef)}
- If the gate PASSES: ensure all work is committed, push with \`${pushCmd(plan)}\`, and return pass=true, green=true, pushed=true.
- If a gate command FAILS because of THIS issue's change: fix the code, re-run until fully green, commit, push, return pass=true, green=true, pushed=true. Never suppress, skip, or baseline a failure to make it pass.
- Only if a failure is GENUINELY pre-existing/flaky and unrelated to this change (a quality-gate finding on a file YOU changed never qualifies): do NOT patch unrelated code — push what you have and return pass=true, green=false with a short reason so a human can look.
- If a gate command reports that it SKIPPED because a required tool is missing, that is NOT a pass: install the tool as the repo documents and re-run until it genuinely executes.
- If the PUSH is REJECTED (non-fast-forward: origin/${plan.branch} already exists with different history, e.g. left over from an earlier run): do NOT force-push, do NOT delete or overwrite the remote branch, do NOT retry with force flags. Leave everything committed locally and return pass=true, pushed=false with a reason naming the stale remote branch so a human can clean it up.
Never leave the branch with uncommitted changes. Whenever you ran the gate (STEP 2), finish with \`git rev-parse HEAD\` and return it as headSha.`,
      { label: `review+gate #${issue.number}.${round}`, phase: 'Deliver', schema: REVIEW_SCHEMA },
    )
    if (review && review.pass) break
    const fix = await agent(
      `Address the reviewer's BLOCKING findings for issue #${issue.number}, working inside ${workspaceDesc(plan)}.
Blocking findings:
${((review && review.blocking) || []).map((b, i) => `${i + 1}. ${b}`).join('\n')}
${principles()}
Fix each item, then re-run the checks:
${narrowNote()}
${heavySuiteNote(plan.baseRef)}
${commitLocally(issue, plan)}
Return ok=false with a reason only if you cannot resolve them.`,
      { label: `fix #${issue.number}.${round}`, phase: 'Deliver', schema: FIX_SCHEMA },
    )
    if (!fix || !fix.ok) {
      review = { pass: false, blocking: (review && review.blocking) || ['fix agent could not resolve findings'] }
      break
    }
  }
  return {
    passed: !!(review && review.pass),
    rounds: round,
    blocking: (review && review.blocking) || [],
    // Gate outcome from the passing round (undefined if it never passed).
    gate: review && review.pass
      ? { green: !!review.green, pushed: !!review.pushed, headSha: review.headSha, reason: review.reason, summary: review.summary }
      : null,
  }
}

// Deliver one issue through the full pipeline. Returns a record describing where
// it landed. In sequential mode the review+gate step's reported headSha is what
// establishes the shared branch and advances the base the next issue continues
// from — independent of push success, so a rejected/blocked push can never cause
// the next issue to recut the branch over this one's work. A passing review that
// reports no headSha is FATAL (rec.fatal): without its tip the next issue cannot
// continue safely, so the run stops.
async function deliver(issue) {
  const plan = planFor(issue)
  const base = { issue: issue.number, title: issue.title, branch: plan.branch, mode, pushed: false, stacked: false }
  try {
    const pre = await precheck(issue, plan)
    if (pre && pre.alreadyDone) {
      return { ...base, delivered: false, status: 'already-done', rounds: 0, blocking: [], note: pre.reason || 'already implemented on the base branch' }
    }
    const impl = await implement(issue, plan)
    if (!impl || !impl.ok) {
      return { ...base, delivered: false, status: 'impl-failed', rounds: 0, blocking: [impl ? impl.reason || 'implementation incomplete' : 'implementer produced no result'] }
    }
    const r = await reviewLoop(issue, plan)
    if (!r.passed) {
      return { ...base, delivered: false, status: 'review-failed', rounds: r.rounds, blocking: r.blocking }
    }
    // The review passed, which means the SAME step ran the full gate and pushed;
    // its gate outcome (green/pushed/headSha) rides along in r.gate.
    const g = r.gate
    if (!g || !g.headSha) {
      return { ...base, delivered: false, fatal: true, status: 'gate-missing', rounds: r.rounds, blocking: ['review+gate passed but reported no headSha (possibly a denied command) — run stopped: the same cause would kill every later gate, and a continuing sequential issue could recut the branch over this work'] }
    }
    const pushed = !!g.pushed
    const stacked = plan.sequential
    if (stacked) {
      seqEstablished = true
      seqBaseRef = g.headSha
    }
    if (!g.green) {
      return { ...base, delivered: false, pushed, stacked, status: 'suite-failed', rounds: r.rounds, blocking: [g.reason || 'full suite not green'] }
    }
    if (!pushed) {
      return { ...base, delivered: false, pushed, stacked, status: 'push-rejected', rounds: r.rounds, blocking: [g.reason || 'push rejected — stale remote branch needs human cleanup'] }
    }
    return { ...base, delivered: true, pushed, stacked, status: 'delivered', rounds: r.rounds, blocking: [], summary: g.summary }
  } catch (e) {
    return { ...base, delivered: false, status: 'threw', rounds: 0, blocking: [`delivery threw: ${e && e.message ? e.message : e}`] }
  }
}

// ---------------------------------------------------------------- planner

// One agent decides the next unit of work by re-reading the world: it reads the
// live mode file, fetches the base, lists open labelled issues, resolves
// dependencies, and returns the single best UNBLOCKED issue to start next.
async function pickNext(handled, onOwnBranch, onSharedBranch) {
  const handledList = handled.length ? handled.join(', ') : '(none)'
  const ownBranchList = onOwnBranch.length ? onOwnBranch.join(', ') : '(none)'
  const sharedList = onSharedBranch.length ? onSharedBranch.join(', ') : '(none)'
  const sharedEstablished = seqEstablished
  return agent(
    `You are the planner for an unsupervised, one-issue-at-a-time delivery run in "${repoRoot}". Pick the SINGLE next issue to start.

${ghNote()}
0. Stop gate: check whether the file "${stopFile}" exists (\`test -f "${stopFile}"\`). Set stopRequested accordingly. If it exists, still complete the rest of this analysis but the caller will not start anything new.
1. MODE: read the live mode file to decide how work lands. Run \`cat "${modeFile}" 2>/dev/null || true\`. If the file exists AND its content (trimmed, case-insensitive) is "overnight" or "sequential", set mode="sequential". Otherwise (file absent, empty, or says "daytime"/"per-issue"/anything else) set mode="per-issue". Return this in the \`mode\` field. The BASE that candidates build on depends on the mode:
   - "per-issue": the BASE is origin/${defaultBranch}. Each issue lands on its own branch off it.
   - "sequential": all issues stack on the shared branch \`${SEQ_BRANCH}\`. The shared branch is ${sharedEstablished ? `ALREADY ESTABLISHED (issues stacked this run: ${sharedList}) — the BASE is its local tip (${seqBaseRef}); it may not exist on origin yet` : `NOT yet established this run — the next sequential issue will start it fresh off origin/${defaultBranch}; treat the BASE as origin/${defaultBranch}`}.
2. Get the latest world state for the BASE: \`git fetch origin ${defaultBranch}\`.
3. ${listIssuesInstruction()} Only OPEN issues are candidates — a CLOSED issue is done and must never be picked.
4. These issue numbers have ALREADY been handled this run (delivered or attempted and set aside) — EXCLUDE them from selection entirely: ${handledList}.
   - Delivered onto their OWN per-issue branch (pushed, awaiting human merge, NOT on origin/${defaultBranch}): ${ownBranchList}.
   - Delivered onto the shared overnight branch (already stacked on ${SEQ_BRANCH} this run): ${sharedList}.
5. Rank the remaining candidates by priority WITHOUT reading bodies yet: prefer issues labelled "bug" or "priority: high", then the lowest issue number. Then walk them in priority order and, for each, read its body to decide whether it is startable:
   a. ALREADY DONE? If the issue's change already appears to be present on the BASE (its acceptance criteria are already met in the code — some issues are fixed but left open), do NOT pick it. Skip it and note it as "appears already done on the base".
   b. DEPENDENCIES: identify any dependency on another issue (look for a "Depends on: #N" line, and any prose naming a blocking issue). A dependency is SATISFIED if that dependency issue is CLOSED, or its change is already present on the BASE, or it is one of the shared-branch numbers above (${sharedList}) AND we are in sequential mode (it is stacked on the sequential base). A dependency that is one of the own-per-issue-branch numbers (${ownBranchList}) is NOT satisfied while we build on origin/${defaultBranch} — that work is pushed but not yet merged. (Handled-but-FAILED numbers are never satisfied — that work is on no base.)
      A candidate is UNBLOCKED only if EVERY dependency is satisfied. Pick the FIRST candidate that is neither already-done nor blocked as \`next\`. If none qualifies, next=null. You do not need to read every body — stop once you have your pick.
6. Set waitingForMerge=true only if there is at least one candidate that is unblocked-except-for-an-own-per-issue-branch dependency (${ownBranchList}) — i.e. work that would become startable once the human merges an already-delivered per-issue branch. Otherwise false.
7. In \`remaining\`, list the candidates you did NOT pick with a one-line reason each (e.g. "appears already done on the base", "blocked by #123 (delivered, awaiting merge)", "blocked by #77 (open, not started)", "dependency cycle").

Return next, mode, stopRequested, waitingForMerge, remaining, and notes.`,
    { label: `pick next (${handled.length} handled)`, phase: 'Deliver', schema: PICK_SCHEMA },
  )
}

// ---------------------------------------------------------------- run

phase('Setup')
const setup = await agent(
  `Prepare this repo for an unsupervised one-issue-at-a-time delivery run, and PROFILE how this specific project builds and tests itself. Working directory is the git checkout root. This workflow knows nothing about this repo in advance — what you report here is what every later agent will be told to run, so be accurate and concrete.

PART A — preflight
1. Verify \`git status\` shows a CLEAN working tree. If it does not, return ok=false with the reason and make NO changes.
2. Determine how GitHub is reachable. Try the \`gh\` CLI first: run \`gh auth status\`. If it succeeds, set hasGhCli=true. If \`gh\` is missing or unauthenticated, set hasGhCli=false and instead confirm access via the GitHub MCP tools (load schemas with ToolSearch, e.g. \`select:mcp__github__get_me\`, then call \`mcp__github__get_me\`). If NEITHER works, return ok=false.
3. Parse the GitHub owner and repo from \`git remote get-url origin\` (e.g. https://github.com/OWNER/REPO(.git) -> owner=OWNER, repo=REPO). Return them as owner and repo.
4. Determine the remote default branch name (e.g. from \`git symbolic-ref refs/remotes/origin/HEAD\`, falling back to \`main\`). \`git fetch origin <default>\` and fast-forward the local default branch to its remote.

PART B — profile the project (this is what makes the run repo-independent)
Read the repo's own documentation and configuration rather than guessing: CLAUDE.md, AGENTS.md, CONTRIBUTING.md, README.md, the files under .github/workflows/, and the manifest/lockfiles present (package.json + which lockfile, pyproject.toml/uv.lock, Cargo.toml, go.mod, Gemfile, Makefile, justfile, …).
5. installCommand: the exact command that installs dependencies reproducibly (prefer the frozen/locked form the CI workflow uses). Empty string if the project needs no install step. Then RUN it so the checkout is ready.
6. fullGate: the ordered list of shell commands that together reproduce this repo's CI gate for a branch — lint, typecheck, unit tests, build, and any project-specific structural/quality gate. Take them from the CI workflow files where possible so they match what will actually judge the PR. Order them cheapest-first where CI allows. Use the project's real runner (e.g. \`uv run pytest -q\`, \`pnpm test\`, \`make check\`) — never a generic guess.
7. narrowTestGuidance: one or two sentences telling an agent how to run the narrowest useful subset for a targeted change in this repo, plus the lint/typecheck to pair with it.
8. heavySuites: any suite that is expensive AND self-contained, so it is only worth running when the diff touches its area — give the command, the path prefix(es) that make it relevant, and any setup it needs (e.g. freeing a port). Return an empty array if the project has none. Do not invent entries.
9. contracts: files or interfaces this repo treats as human-gated — a published API surface, a plugin contract, a stored schema, anything its docs say must not be changed without a human. Empty array if none.
10. projectRules: a SHORT digest (a handful of bullet lines) of repo-specific non-negotiables an implementer must obey — commit message conventions, forbidden shortcuts, how its quality gate must be treated, branch policy. Quote the repo, do not invent rules. Empty string if the repo documents none.

PART C — shared-branch state
11. Inspect any PRE-EXISTING shared overnight branch (\`${SEQ_BRANCH}\`) so the run can CONTINUE from it instead of recutting it. Inspection only — do NOT checkout, move, or delete anything here.
   - \`git fetch origin ${SEQ_BRANCH}\` (a failure just means it does not exist on origin); also check for a local \`${SEQ_BRANCH}\` branch.
   - Neither exists: overnightState="absent" (omit overnightTip).
   - Both exist: the candidate tip is whichever CONTAINS the other (test with \`git merge-base --is-ancestor A B\` in both directions; if they are equal, either one). If they have DIVERGED (neither contains the other), return ok=false with a reason telling the human to reconcile first — keep one tip (push or tag it) or delete the branch they don't want — the run must not guess which work to keep.
   - Only one exists: it is the candidate tip.
   - If the candidate tip is already contained in origin/<default>, OR every commit it has over origin/<default> is patch-equivalent to something already on it (\`git cherry origin/<default> <tip>\` prints only \`-\` lines — the work was landed rebased/re-authored, which plain ancestry cannot see): the branch is fully merged and stale — overnightState="stale" (omit overnightTip; a fresh start is safe).
   - Otherwise: overnightState="adopt", overnightTip=<the candidate's SHA from \`git rev-parse\`>.
12. Clear any STALE stop signal so this fresh run isn't immediately stopped: \`rm -f "$(pwd)/.unsupervised-issues.stop"\` (ignore if absent).
13. Seed the live mode file with this run's starting mode, but ONLY if it does not already exist (an existing file is the human's standing preference and must win): \`test -f "$(pwd)/.unsupervised-issues.mode" || printf '%s\\n' "${cfg.startMode}" > "$(pwd)/.unsupervised-issues.mode"\`. Do NOT overwrite it if present. If these two signal files are not gitignored, add them to .gitignore — but do NOT commit that change; just leave it and mention it in reason, so the tree state is visible to the human.

Return ok, reason, repoRoot, defaultBranch, owner, repo, hasGhCli, installCommand, fullGate, narrowTestGuidance, heavySuites, contracts, projectRules, overnightState, overnightTip.`,
  { label: 'setup + profile', schema: SETUP_SCHEMA },
)

if (!setup || !setup.ok) {
  log(`Setup failed — aborting: ${setup ? setup.reason : 'no result'}`)
  return { aborted: true, reason: setup && setup.reason }
}
repoRoot = setup.repoRoot
defaultBranch = setup.defaultBranch || 'main'
owner = setup.owner || ''
repo = setup.repo || ''
hasGhCli = !!setup.hasGhCli
installCommand = setup.installCommand || ''
fullGate = cfg.gatesOverride || setup.fullGate || []
narrowTestGuidance = setup.narrowTestGuidance || ''
heavySuites = setup.heavySuites || []
contracts = setup.contracts || []
projectRules = setup.projectRules || ''
stopFile = A.stopFile || `${repoRoot}/.unsupervised-issues.stop`
modeFile = A.modeFile || `${repoRoot}/.unsupervised-issues.mode`

// A run with no gate cannot tell "delivered" from "broken", which is the whole
// point of an unsupervised loop. Refuse rather than deliver unverifiable work.
if (!fullGate.length) {
  log('Setup discovered no full-suite gate for this project, and none was supplied. Aborting: an unsupervised run with nothing to verify against would merge unverified work. Pass one explicitly, e.g. Workflow({ name: "unsupervised-issues", args: { gates: ["<test command>"] } }).')
  return { aborted: true, reason: 'no verifiable gate discovered or supplied' }
}

if (setup.overnightState === 'adopt' && !setup.overnightTip) {
  log(`Setup reported an adoptable ${SEQ_BRANCH} but no tip SHA — aborting rather than risking a recut over unmerged work.`)
  return { aborted: true, reason: 'overnightState=adopt without overnightTip' }
}
if (setup.overnightState === 'adopt' && setup.overnightTip) {
  seqEstablished = true
  seqBaseRef = setup.overnightTip
  log(`Existing ${SEQ_BRANCH} has unmerged work — sequential issues will CONTINUE from its tip ${setup.overnightTip} instead of recutting. Delete the branch (local and origin) first if you want a clean start.`)
}
log(`Repo ${owner}/${repo} on ${defaultBranch}. GitHub via ${hasGhCli ? '`gh` CLI' : 'GitHub MCP tools'}.`)
log(`Gate (${fullGate.length} step${fullGate.length === 1 ? '' : 's'})${cfg.gatesOverride ? ' [supplied via args]' : ' [discovered]'}: ${fullGate.join(' && ')}`)
if (heavySuites.length) log(`Scoped heavy suites: ${heavySuites.map((s) => `${s.command} (${s.paths})`).join('; ')}`)
if (contracts.length) log(`Human-gated contracts agents must not change: ${contracts.join(', ')}`)
log(`Delivering one issue at a time. Starting mode: ${cfg.startMode} (${cfg.startMode === 'sequential' ? `stacking on ${SEQ_BRANCH}` : `own branch per issue off origin/${defaultBranch}`}).`)
log(`Switch modes live (takes effect on the next issue) by writing the mode file:  echo overnight > "${modeFile}"  (sequential)  |  echo daytime > "${modeFile}"  (per-issue).`)
log(`Stop after the current issue any time with:  touch "${stopFile}"`)

phase('Deliver')
const handled = new Map() // issue number -> delivery record
let stopped = false

while (true) {
  // Hand the planner where each already-handled issue actually landed, so it can
  // resolve dependencies. own-branch = per-issue pushes (awaiting human merge);
  // shared = pushed onto the overnight branch this run (stacked, satisfies deps).
  const onOwnBranch = [...handled.values()].filter((r) => r.pushed && r.mode !== 'sequential').map((r) => r.issue)
  const onSharedBranch = [...handled.values()].filter((r) => r.stacked).map((r) => r.issue)
  const pick = await pickNext([...handled.keys()], onOwnBranch, onSharedBranch)
  if (!pick) {
    log('Planner produced no result — stopping.')
    break
  }
  // Adopt the mode the planner read from the live mode file for this iteration.
  const prevMode = mode
  mode = pick.mode === 'sequential' ? 'sequential' : 'per-issue'
  if (mode !== prevMode) log(`Mode switched to ${mode} (from the mode file) — applies to the next issue.`)
  if (pick.stopRequested) {
    log('Stop signal present — not starting a new issue.')
    stopped = true
    break
  }
  if (!pick.next) {
    log(pick.waitingForMerge
      ? 'No issues ready to deliver — remaining work is waiting on per-issue-branch merges. Stopping; restart after merging (or switch to overnight mode to keep stacking).'
      : 'No unblocked issues left to deliver — done.')
    break
  }

  const issue = pick.next
  log(`Next: #${issue.number} ("${issue.title}")${issue.isBug ? ' [bug]' : issue.isHigh ? ' [high]' : ''} — ${mode === 'sequential' ? `stacking on ${SEQ_BRANCH}` : 'own branch'}.`)
  const rec = await deliver(issue)
  handled.set(issue.number, rec)
  log(rec.delivered
    ? rec.mode === 'sequential'
      ? `Delivered #${issue.number} onto ${rec.branch} (full suite green) — stacked for morning review.`
      : `Delivered #${issue.number} on ${rec.branch} (full suite green) — ready for you to merge.`
    : rec.stacked
      ? `Stacked #${issue.number} onto ${rec.branch} (${rec.status === 'push-rejected' ? 'green, but the push was rejected — needs a human push' : 'full suite NOT green'}) — later issues build on it; NEEDS ATTENTION before merge: ${(rec.blocking || []).join('; ')}`
      : rec.status === 'already-done'
        ? `Skipped #${issue.number} — already implemented on the base (${rec.note || 'no change needed'}). You may close it.`
        : `#${issue.number} not delivered (${rec.status}): ${(rec.blocking || []).join('; ')}`)
  if (rec.fatal) {
    log(rec.mode === 'sequential'
      ? `Run stopped: the review+gate step for #${issue.number} passed but reported no branch tip (likely a denied command). Work is committed on ${rec.branch}; a re-run will detect that unmerged tip and continue from it.`
      : `Run stopped: the review+gate step for #${issue.number} passed but reported no branch tip (likely a denied command). Work is committed on ${rec.branch} — rescue that tip (push it, or tag it) BEFORE re-running: a fresh run recuts ${rec.branch} from origin/${defaultBranch}.`)
    break
  }
}

const records = [...handled.values()]
return {
  mode: 'one-issue-at-a-time',
  finalMode: mode,
  repo: `${owner}/${repo}`,
  defaultBranch,
  gate: fullGate,
  sharedBranch: records.some((r) => r.stacked) ? SEQ_BRANCH : null,
  stopped,
  stopFile,
  modeFile,
  delivered: records.filter((r) => r.delivered).map((r) => ({ issue: r.issue, branch: r.branch, title: r.title, mode: r.mode })),
  alreadyDone: records.filter((r) => r.status === 'already-done').map((r) => ({ issue: r.issue, title: r.title, note: r.note })),
  notDelivered: records.filter((r) => !r.delivered && r.status !== 'already-done').map((r) => ({ issue: r.issue, branch: r.branch, status: r.status, blocking: r.blocking })),
}
