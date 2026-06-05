"""Unit tests for the pure formatting and injection helpers in profilegen.

The GraphQL fetch is intentionally not tested here: it is thin IO with no logic.
Everything worth testing is string-in / string-out, so no HTTP mocking is needed.
"""

import pytest

import profilegen as pg


def _item(title="Add feature", url="https://github.com/o/r/pull/1",
          repo="o/r", created="2026-01-02T10:11:12Z"):
    """Build an activity item dict matching the normalized fetch output."""
    return {"title": title, "url": url, "repo": repo, "createdAt": created}


# --- fmt_item -------------------------------------------------------------

def test_fmt_item_renders_link_repo_and_date():
    line = pg.fmt_item(_item())
    assert "[Add feature](https://github.com/o/r/pull/1)" in line
    assert "`o/r`" in line
    assert "2026-01-02" in line          # date trimmed to YYYY-MM-DD
    assert "T10:11:12" not in line       # time component dropped


def test_fmt_item_escapes_brackets_in_title():
    line = pg.fmt_item(_item(title="Fix [bug] in parser"))
    # brackets escaped so they do not break the markdown link text
    assert r"Fix \[bug\] in parser" in line


def test_fmt_item_passes_through_already_trimmed_date():
    # an already YYYY-MM-DD createdAt must survive the [:10] slice unchanged
    line = pg.fmt_item(_item(created="2026-01-02"))
    assert line.endswith("2026-01-02")


# --- fmt_section ----------------------------------------------------------

def test_fmt_section_lists_items_under_heading():
    section = pg.fmt_section("Recent PRs", [_item(title="One"), _item(title="Two")])
    assert section.startswith("### Recent PRs")
    assert section.count("\n- ") == 2


def test_fmt_section_empty_shows_placeholder():
    section = pg.fmt_section("Recent PRs", [])
    assert "### Recent PRs" in section
    assert "Nothing here yet" in section
    assert "- [" not in section          # no list items


# --- render_activity ------------------------------------------------------

def test_render_activity_has_both_sections():
    block = pg.render_activity([_item(title="PR")], [_item(title="ISS")])
    assert "Pull Requests" in block
    assert "Issues" in block
    assert "PR" in block and "ISS" in block


def test_render_activity_caps_at_five_items():
    many = [_item(title=f"PR{i}") for i in range(10)]
    block = pg.render_activity(many, [])
    # only the first 5 PRs rendered
    for i in range(5):
        assert f"PR{i}" in block
    assert "PR5" not in block


def test_render_activity_caps_and_routes_both_sections():
    prs = [_item(title=f"PR{i}", repo="o/pr") for i in range(10)]
    issues = [_item(title=f"ISS{i}", repo="o/iss") for i in range(10)]
    block = pg.render_activity(prs, issues)

    pr_part, iss_part = block.split("### 🐛 Recent Issues", 1)
    # each section capped at 5 and items land under the correct heading
    for i in range(5):
        assert f"PR{i}" in pr_part and f"ISS{i}" not in pr_part
        assert f"ISS{i}" in iss_part and f"PR{i}" not in iss_part
    assert "PR5" not in block and "ISS5" not in block
    assert iss_part.count("\n- ") == 5


# --- inject ---------------------------------------------------------------

README = (
    "# Title\n\n"
    "static intro stays\n\n"
    f"{pg.ACTIVITY_START}\n"
    "OLD CONTENT\n"
    f"{pg.ACTIVITY_END}\n\n"
    "footer stays\n"
)


def test_inject_replaces_only_between_markers():
    out = pg.inject(README, "NEW CONTENT")
    assert "NEW CONTENT" in out
    assert "OLD CONTENT" not in out
    # everything outside the markers is preserved
    assert "static intro stays" in out
    assert "footer stays" in out
    # markers themselves survive
    assert pg.ACTIVITY_START in out
    assert pg.ACTIVITY_END in out


def test_inject_is_idempotent():
    once = pg.inject(README, "NEW CONTENT")
    twice = pg.inject(once, "NEW CONTENT")
    assert once == twice


def test_inject_preserves_backslashes_in_content():
    # content with escaped brackets must not be mangled by regex substitution
    out = pg.inject(README, r"- \[x\] item")
    assert r"\[x\]" in out


def test_inject_preserves_backslash_digit_sequences():
    # a lambda replacement is used precisely so '\1'/'\g' are NOT treated as
    # re.sub backreferences; prove a backslash-then-digit survives verbatim
    out = pg.inject(README, r"- \[1\] \2 done")
    assert r"- \[1\] \2 done" in out


def test_inject_raises_when_markers_missing():
    with pytest.raises(ValueError):
        pg.inject("# no markers here", "NEW CONTENT")


@pytest.mark.parametrize("readme", [
    f"intro\n{pg.ACTIVITY_START}\nbody\nno end marker",
    f"intro\nno start marker\nbody\n{pg.ACTIVITY_END}\n",
])
def test_inject_raises_when_one_marker_missing(readme):
    with pytest.raises(ValueError):
        pg.inject(readme, "NEW CONTENT")
