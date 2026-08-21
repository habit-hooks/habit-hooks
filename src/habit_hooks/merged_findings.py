"""Findings that would print the same guide are one finding.

Two sensors can see one smell — eslint's ``max-lines`` and the generic
``line-count`` sensor both report ``oversized-file`` — and one sensor can report
a smell many times over, as jscpd does, a finding per clone. The mapper prints
one block per finding, so left alone each of those became another copy of the
same ~200-word guide (#140).

**The guide is the thing merged on, not the smell.** One guide printed twice is
the whole waste being removed, so merging exactly what renders alike is correct
by construction — and merging by smell alone is not: `high-complexity` from the
python plugin and from the typescript plugin route to *different* guides
(``rendering.resolve_guide``, off the finding's ``language``), and folding them
together coaches a ``.ts`` file in Python. Keying on ``language`` instead is no
fix either, since ``generic`` declares none and would stop #140 being fixed at
all.

Merging is the mapper's, not the sensors stage's: what a sensor emitted is the
run's own record, read by ``habit-snooze``, so a snooze key must not depend on
who else saw the same file. It happens before anything is rendered, so
:mod:`habit_hooks.rendering` still renders exactly one finding and knows nothing
about this — the guide arrives as a callable the mapper supplies.
"""

from __future__ import annotations

from typing import Callable, Hashable

# The keys the merge settles itself, so the loop over the rest must skip them.
SETTLED_BY_THE_MERGE = ("smell", "details", "issues")

# Where an issue's details say the observation is. ``file`` and ``line``/
# ``column`` are the finding contract's own location fields
# (docs/sensor-interface.spec.md); a smell may spell the place its own way, and
# ``duplicated-code`` does — a jscpd occurrence names a RANGE and no line, so
# leaving its bounds out would read two clones of one file as one duplication.
PLACE_FIELDS = ("file", "line", "column", "startLine", "endLine")


def merged(
    findings: list[dict], guide_of: Callable[[dict], Hashable]
) -> list[dict]:
    """One finding per smell and guide, in the order the first of each arrived.

    ``guide_of`` answers which guide a finding would render — the mapper's own
    resolution, passed in so this module never learns about ``Config`` or
    ``Resolver``. The smell is in the key too: a ``[smells.<name>] guide``
    override can point two smells at one file, and their banners still name
    them separately.
    """
    groups: dict[tuple, list[dict]] = {}
    for finding in findings:
        groups.setdefault((finding["smell"], guide_of(finding)), []).append(finding)
    return [_one_finding(group) for group in groups.values()]


def _one_finding(group: list[dict]) -> dict:
    """The findings of one group as the single finding that renders for them.

    A top-level key other than the three below is **first non-null**: the
    runner stamps ``language`` from the producing plugin and ``generic``
    declares none, so a null must not out-rank a real answer. It cannot pick a
    language from outside the group — every member resolves to the group's one
    guide, so re-resolving with any of theirs lands there too.

    Built rather than edited: ``merged`` answers a question about the findings
    it is handed and does not rewrite them.
    """
    finding = dict(group[0])
    for later in group[1:]:
        for name, value in later.items():
            if name not in SETTLED_BY_THE_MERGE and finding.get(name) is None:
                finding[name] = value
    finding["details"] = _agreed_facts(group)
    finding["issues"] = _issues_across(group)
    return finding


def _agreed_facts(group: list[dict]) -> dict:
    """The smell-level ``details`` the group does not contradict itself about.

    Not first-come: a fact only one finding states is kept — ``line-count``
    names the threshold it enforced and eslint does not — but a fact two of
    them state *differently* is **dropped**: jscpd's ``lines``/``tokens``
    describe one clone pair, and three pairs merged would otherwise publish the
    first pair's numbers as the whole finding's. A guide reading a missing key
    renders nothing; one reading a wrong number teaches the reader something
    untrue. A key stays dropped once contradicted, however many later findings
    happen to restate the first value.
    """
    agreed: dict = {}
    contradicted: set = set()
    for finding in group:
        for name, fact in (finding.get("details") or {}).items():
            if name in contradicted:
                continue
            if name not in agreed:
                agreed[name] = fact
            elif agreed[name] != fact:
                del agreed[name]
                contradicted.add(name)
    return agreed


def _issues_across(group: list[dict]) -> list[dict]:
    """Every issue of the first finding, then whatever the later ones add.

    Deduplication is **across** findings only. A sensor's own issue list is
    authoritative — it meant the seven long functions it reported, and the two
    comments it found on one line — and three shipped sensors (``pmd``,
    ``phpmd``, ``comment``) key by file and give no column, so two of their
    issues on one line are one observation by any identity this can build.
    Second-guessing that is not the merge's job; #140 is about two *sensors*
    reporting one thing.
    """
    issues = list(group[0].get("issues") or [])
    seen = {_observation(issue) for issue in issues}
    for later in group[1:]:
        own = later.get("issues") or []
        issues.extend(issue for issue in own if _observation(issue) not in seen)
        seen.update(_observation(issue) for issue in own)
    return issues


def _observation(issue: dict) -> tuple:
    """What an issue is *about*: its snooze key, and the place it names.

    Nothing either tool said in its own voice counts — two sensors seeing one
    thing disagree on ``source`` and ``message`` precisely because they are two
    tools. A field neither stated and a field stated as ``null`` both come back
    ``None``, which is the same absence and has to compare as one.
    """
    details = issue.get("details") or {}
    return (issue.get("key"), *(details.get(field) for field in PLACE_FIELDS))
