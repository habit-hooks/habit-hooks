"""How a spec's nested contexts inherit, isolate and skip.

A spec file is a tree of headings: an ancestor's steps are preamble to every
leaf below it, siblings never see each other's state, and only leaves are
tests. Separate from the marker tests because these are the rules *between*
cases rather than what any one step does.
"""

import pytest

from harness import SpecError, parse_spec

from spec_runs import run


# --- contexts --------------------------------------------------------------


def test_sibling_contexts_are_isolated(tmp_path):
    spec = (
        "# Root\n"
        "## A\n```bash\necho hi > shared.txt\n```\n"
        "## B\n```bash\ncat shared.txt\n```\n"
    )
    # B runs in a fresh dir, so shared.txt is absent and B fails.
    assert run(spec, tmp_path) == ["pass", "fail"]


def test_ancestor_preamble_accumulates(tmp_path):
    spec = (
        "# Root\n✏️A\n```text\n1\n```\n"
        "## Mid\n✏️B\n```text\n2\n```\n"
        "### Leaf\n```bash\nprintf '%s%s' \"$A\" \"$B\"\n```\n🖥️ ✅\n```text\n12\n```\n"
    )
    assert run(spec, tmp_path) == ["pass"]


def test_only_leaves_are_tests(tmp_path):
    spec = "# Root\n## A\n```bash\ntrue\n```\n## B\n```bash\ntrue\n```\n"
    assert run(spec, tmp_path) == ["pass", "pass"]


def test_skip_is_reported_not_run(tmp_path):
    spec = "# T 🟡\n```bash\nexit 1\n```\n"
    results = parse_spec(spec)
    assert len(results) == 1 and results[0].skip is True
    assert run(spec, tmp_path) == ["skip"]


def test_skip_inherited_from_ancestor(tmp_path):
    spec = "# Group 🟡\n## Leaf\n```bash\nexit 1\n```\n"
    assert run(spec, tmp_path) == ["skip"]


def test_missing_required_block_is_spec_error():
    # ✏️ with no following block is malformed (caught while pairing markers).
    with pytest.raises(SpecError):
        parse_spec("# T\n✏️X\n```bash\ntrue\n```\n")


def test_stdin_missing_block_is_spec_error():
    # ⌨️ likewise requires its payload block before the command runs.
    with pytest.raises(SpecError):
        parse_spec("# T\n⌨️\n```bash\ncat\n```\n")
