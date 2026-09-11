"""What makes a snooze lapse, and what re-affirming one records (#163).

``snooze_index`` owns the file: reading it, refusing what it cannot mean, and
replacing it without tearing. This module owns the rule read out of it, along
with the terms that rule is expressed in, which came out of ``snooze.py`` where
they sat beside the CLI. That division is the one ``rendering`` draws against
``mapper``, and the dependency runs the same way: ``snooze_lapse`` →
``snooze_index``.

The rule has two halves. Git answers whether the branch changed the file, and
only the index can answer whether that change is the one already judged — which
is why nothing a re-run of ``--snooze`` wrote could clear a finding while an
entry was a bare path.

Both halves are asked per key *and* anchor: the pair is what the rule has always
decided on, and a key is not always one file.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection
from pathlib import Path

from attrs import evolve, frozen

from .snooze_index import Anchors, Index

CONTENT_ALGORITHM = "sha256"


def anchor_file(issue: dict) -> str:
    """The file an issue's snooze is anchored to: its ``details.file``, else its key.

    A sensor keys an issue by whatever groups it best, which is not always a path
    — ``sensors.finding_paths.anchored`` names the same two, ``deptry`` keying by
    module and ``knip`` by export name — so the file to record, and to compare,
    comes from the details bag rather than from the key.

    A ``file`` that is not a non-empty string reads as absent, the same reading
    ``sensors.finding_paths._reported_file`` gives it. That stage lets such an
    issue through rather than failing its sensor, so this one is reached with a
    ``None`` or a number in there, and the anchor is now a path we open.
    """
    file = issue.get("details", {}).get("file")
    return file if isinstance(file, str) and file else issue["key"]


def anchors_by_key(findings: list[dict]) -> dict[str, set[str]]:
    """Every key the run reports, with the files it reports that key under.

    Usually one file each; see ``anchor_file`` for when it is several.
    """
    anchors: dict[str, set[str]] = {}
    for finding in findings:
        for issue in finding["issues"]:
            anchors.setdefault(issue["key"], set()).add(anchor_file(issue))
    return anchors


def snoozed_anchors(findings: list[dict], snoozed: set[str]) -> set[str]:
    """The files the snoozed issues sit in — where a lapse could apply."""
    return {
        anchor_file(issue)
        for finding in findings
        for issue in finding["issues"]
        if issue["key"] in snoozed
    }


def content_hash(path: Path) -> str | None:
    """The digest of ``path``'s content, or ``None`` when it is no file to read.

    Only ``\\r\\n`` is normalised away first, which makes this half of the rule
    deliberately *more* forgiving than the other rather than identical to it.
    Measured: under ``core.autocrlf`` git reports nothing for a CRLF-only
    rewrite, without it git reports the file. Hashing the bytes on disk would
    therefore lapse a snooze affirmed on a CRLF checkout the moment an LF one
    read the index — and the index is checked in precisely so the answer
    travels. So a line ending is the one difference this half forgives, which
    costs little: a line-ending-only rewrite is not the new debt the ratchet
    exists to surface.

    An unreadable path records nothing rather than failing the run, the same
    degrade ``changed_files`` gives a path git cannot place.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    digest = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    return f"{CONTENT_ALGORITHM}:{digest}"


@frozen
class Lapse:
    """Why a snooze may no longer hold: git's answer, and the index's own.

    ``files`` are the anchor files this branch changed since the base ref;
    ``affirmed`` the key-and-anchor pairs whose file still holds the content the
    entry recorded for it.
    """

    files: Collection[str] = frozenset()
    affirmed: Collection[tuple[str, str]] = frozenset()

    def spares(self, key: str, anchor: str) -> bool:
        """Whether a snooze on ``key``, anchored to ``anchor``, survives it."""
        return anchor not in self.files or (key, anchor) in self.affirmed

    def affirming(self, index: Index, findings: list[dict], project_dir: Path) -> Lapse:
        """This lapse, told which of its changed anchors still hold what they recorded.

        Only an anchor git called changed is asked, because ``spares`` decides
        every other one without it. Asking them all would read and hash every
        snoozed file in the project on the ordinary run where git flagged none —
        in a transform that runs inside a hook loop, and whose git half is
        batched into one call for that very reason.
        """
        affirmed = {
            (key, anchor)
            for key, anchor in _reported_pairs(findings)
            if anchor in self.files and _holds(index.get(key, {}), anchor, project_dir)
        }
        return evolve(self, affirmed=affirmed)


def renewed(index: Index, findings: list[dict], project_dir: Path) -> Index:
    """``index``, with every reported key recording its anchors as they stand.

    Every anchor the run reports, including one the key has no record of yet.
    ``--snooze`` renews what it is fed, so the documented whole-project pipeline
    affirms each file in the pipe — which is what fixing the existing
    ``--snooze`` asks for, and the reason that pipeline is a blunt instrument
    under the ratchet.

    An anchor the run does *not* report is left alone: this run measured nothing
    about it, and the file it describes may not even be in the current scope.
    """
    return index | {
        key: index.get(key, {}) | _recorded(anchors, project_dir)
        for key, anchors in anchors_by_key(findings).items()
    }


def _recorded(anchors: set[str], project_dir: Path) -> Anchors:
    """The content each anchor holds now, skipping the ones that are no file.

    A key may be anchored to something there is nothing to read; and a file
    briefly unreadable is not an answer either, so it keeps whatever the entry
    recorded before rather than losing its affirmation for a reason nobody chose.
    """
    fresh = {anchor: content_hash(project_dir / anchor) for anchor in anchors}
    return {anchor: content for anchor, content in fresh.items() if content is not None}


def _reported_pairs(findings: list[dict]) -> set[tuple[str, str]]:
    """Every key the run reports, paired with the file it reports it under.

    A pair, not a key: affirming the key would exempt a file nobody judged —
    including one that has only just started reporting the smell, which is new
    debt and the ratchet's whole point.
    """
    return {
        (issue["key"], anchor_file(issue))
        for finding in findings
        for issue in finding["issues"]
    }


def _holds(recorded: Anchors, anchor: str, project_dir: Path) -> bool:
    """Only an anchor that recorded something is asked, so an index written
    before #163 reads no file at all."""
    return anchor in recorded and recorded[anchor] == content_hash(project_dir / anchor)
