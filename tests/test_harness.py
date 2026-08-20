"""Unit tests for the spec harness — one per marker plus the cross-cutting rules."""

from pathlib import Path

import pytest

from harness import SpecError, SpecFailure, execute, normalize, parse_spec


def _status(test, where: Path, repo_root: Path) -> str:
    """Run one parsed test in its own dir; return "skip"/"pass"/"fail"."""
    if test.skip:
        return "skip"
    where.mkdir()
    try:
        execute(test, where, repo_root)
        return "pass"
    except (SpecFailure, SpecError):
        return "fail"


def run(text: str, tmp_path: Path, repo_root: Path | None = None) -> list[str]:
    """Parse + run a spec body, returning a status per test."""
    root = repo_root or tmp_path
    cases = parse_spec(text)
    return [_status(c, tmp_path / f"t{i}", root) for i, c in enumerate(cases)]


# --- normalisation ---------------------------------------------------------


def test_normalize_strips_ansi_and_trailing():
    assert normalize("\x1b[31mhi\x1b[0m  \n\n\n") == "hi"


def test_normalize_trims_per_line_and_drops_trailing_blanks():
    assert normalize("a   \nb\t\n\n\n") == "a\nb"


# --- markers ---------------------------------------------------------------


def test_command_and_screen_pass(tmp_path):
    spec = "# T\n```bash\necho hi\n```\n🖥️ ✅\n```text\nhi\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_screen_stdout_mismatch_fails(tmp_path):
    spec = "# T\n```bash\necho hi\n```\n🖥️ ✅\n```text\nbye\n```\n"
    assert run(spec, tmp_path) == ["fail"]


def test_screen_expected_nonzero_exit(tmp_path):
    spec = "# T\n```bash\nexit 3\n```\n🖥️ ❌ 3\n"
    assert run(spec, tmp_path) == ["pass"]


def test_exit_defaults_to_zero_pass(tmp_path):
    assert run("# T\n```bash\ntrue\n```\n", tmp_path) == ["pass"]


def test_exit_defaults_to_zero_fail(tmp_path):
    assert run("# T\n```bash\nexit 1\n```\n", tmp_path) == ["fail"]


def test_stdin_marker_feeds_command(tmp_path):
    spec = "# T\n⌨️\n```text\npayload\n```\n```bash\ncat\n```\n🖥️ ✅\n```text\npayload\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_env_marker_sets_variable(tmp_path):
    spec = "# T\n✏️GREETING\n```text\nhowdy\n```\n```bash\nprintf '%s' \"$GREETING\"\n```\n🖥️ ✅\n```text\nhowdy\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_env_marker_expands_variables(tmp_path):
    spec = ("# T\n✏️X\n```text\na\n```\n✏️Y\n```text\n$X/b\n```\n"
            "```bash\nprintf '%s' \"$Y\"\n```\n🖥️ ✅\n```text\na/b\n```\n")
    assert run(spec, tmp_path) == ["pass"]


def test_file_write_marker(tmp_path):
    spec = "# T\n📄data/x.txt\n```text\ncontent here\n```\n```bash\ncat data/x.txt\n```\n🖥️ ✅\n```text\ncontent here\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_file_copy_marker(tmp_path):
    (tmp_path / "fixture.txt").write_text("from repo\n", encoding="utf-8")
    spec = "# T\n📄 @fixture.txt\n```bash\ncat fixture.txt\n```\n🖥️ ✅\n```text\nfrom repo\n```\n"
    assert run(spec, tmp_path, repo_root=tmp_path) == ["pass"]


def test_file_copy_marker_with_explicit_dest(tmp_path):
    (tmp_path / "fixture.txt").write_text("from repo\n", encoding="utf-8")
    spec = "# T\n📄dest.txt @fixture.txt\n```bash\ncat dest.txt\n```\n🖥️ ✅\n```text\nfrom repo\n```\n"
    assert run(spec, tmp_path, repo_root=tmp_path) == ["pass"]


def test_stderr_marker_asserts_stderr(tmp_path):
    spec = "# T\n```bash\necho boom >&2\n```\n🚨\n```text\nboom\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_stderr_marker_mismatch_fails(tmp_path):
    spec = "# T\n```bash\necho boom >&2\n```\n🚨\n```text\nother\n```\n"
    assert run(spec, tmp_path) == ["fail"]


def test_stderr_with_screen_failure(tmp_path):
    # 🖥️ and 🚨 sit on adjacent lines with no blank between, so markdown-it
    # groups them into one paragraph — both markers must still be extracted.
    spec = "# T\n```bash\necho bad >&2; exit 1\n```\n🖥️ ❌ 1\n🚨\n```text\nbad\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_adjacent_marker_lines_parse_separately():
    # Regression guard for the parser swap: two markers in one paragraph.
    steps = parse_spec("# T\n```bash\ntrue\n```\n🖥️ ✅\n🚨\n")[0].steps
    assert [type(s).__name__ for s in steps] == ["Command", "Screen", "Stderr"]


def test_variation_selector_ignored(tmp_path):
    # 🖥 without U+FE0F must behave like 🖥️.
    spec = "# T\n```bash\necho hi\n```\n\U0001F5A5 ✅\n```text\nhi\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_bash_block_never_consumed_as_payload(tmp_path):
    # The ```bash following ⌨️'s json must run, not be eaten as stdin.
    spec = "# T\n⌨️\n```json\nin\n```\n```bash\ncat\n```\n🖥️ ✅\n```text\nin\n```\n"
    assert run(spec, tmp_path) == ["pass"]


def test_bare_block_without_marker_is_ignored(tmp_path):
    spec = "# T\n```toml\njust docs\n```\n```bash\ntrue\n```\n"
    assert run(spec, tmp_path) == ["pass"]


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
