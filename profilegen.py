#!/usr/bin/env python3
"""Refresh the dynamic activity section of the GitHub profile README.

Fetches the most recently opened pull requests and issues authored by
``PROFILE_LOGIN`` via the GitHub GraphQL API and injects them, as two markdown
lists, into the region of ``README.md`` delimited by the ACTIVITY markers.

Stars and followers are rendered by live shields.io badges in the static part
of the README, so this script never touches them. Only the text between the
markers is rewritten; everything else is preserved byte-for-byte.

Stdlib only. Configuration comes from two environment variables:
    GITHUB_TOKEN   - token used to authenticate the GraphQL request
    PROFILE_LOGIN  - GitHub login to collect activity for (default: shini4i)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

GRAPHQL_URL = "https://api.github.com/graphql"
README_PATH = "README.md"
MAX_ITEMS = 5

ACTIVITY_START = "<!-- ACTIVITY:START -->"
ACTIVITY_END = "<!-- ACTIVITY:END -->"

# Single query: two `search` connections, one for PRs and one for issues.
# `author:` spans all of GitHub, so contributions to other repos show up too.
_QUERY = """
query($prq: String!, $isq: String!, $n: Int!) {
  prs: search(query: $prq, type: ISSUE, first: $n) {
    nodes { ... on PullRequest { title url createdAt repository { nameWithOwner } } }
  }
  issues: search(query: $isq, type: ISSUE, first: $n) {
    nodes { ... on Issue { title url createdAt repository { nameWithOwner } } }
  }
}
"""


# --- pure helpers (unit-tested) -------------------------------------------

def fmt_item(item):
    """Render one activity entry as a markdown list line.

    ``item`` is a normalized dict with keys ``title``, ``url``, ``repo`` and
    ``createdAt`` (an ISO-8601 timestamp). The timestamp is trimmed to its
    ``YYYY-MM-DD`` date and brackets in the title are escaped so they cannot
    break the surrounding markdown link.
    """
    title = item["title"].replace("[", r"\[").replace("]", r"\]")
    date = item["createdAt"][:10]
    return f"- [{title}]({item['url']}) · `{item['repo']}` · {date}"


def fmt_section(heading, items):
    """Render a titled markdown section listing ``items`` (possibly empty)."""
    if not items:
        return f"### {heading}\n\n_Nothing here yet._"
    lines = "\n".join(fmt_item(i) for i in items)
    return f"### {heading}\n\n{lines}"


def render_activity(prs, issues):
    """Build the full activity block from PR and issue lists (each capped)."""
    return (
        f"{fmt_section('🔀 Recent Pull Requests', prs[:MAX_ITEMS])}\n\n"
        f"{fmt_section('🐛 Recent Issues', issues[:MAX_ITEMS])}"
    )


def inject(readme, content):
    """Replace the text between the ACTIVITY markers with ``content``.

    The markers themselves are preserved and everything outside them is left
    untouched. Raises ``ValueError`` if the markers are not found. A function
    replacement is used so backslashes in ``content`` are inserted literally.
    """
    pattern = re.compile(
        re.escape(ACTIVITY_START) + r".*?" + re.escape(ACTIVITY_END),
        re.DOTALL,
    )
    if not pattern.search(readme):
        raise ValueError("ACTIVITY markers not found in README")
    replacement = f"{ACTIVITY_START}\n{content}\n{ACTIVITY_END}"
    return pattern.sub(lambda _m: replacement, readme)


# --- IO (thin, not unit-tested) -------------------------------------------

def fetch_activity(token, login):
    """Query the GraphQL API and return ``(prs, issues)`` as normalized lists."""
    variables = {
        "prq": f"author:{login} is:pr sort:created-desc",
        "isq": f"author:{login} is:issue sort:created-desc",
        "n": MAX_ITEMS,
    }
    payload = json.dumps({"query": _QUERY, "variables": variables}).encode()
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "shini4i-profilegen",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        # A bad/expired token (401) is the most likely failure; surface the
        # status and body instead of an opaque traceback.
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail}") from exc

    if "errors" in body:
        raise RuntimeError(f"GraphQL errors: {body['errors']}")
    data = body.get("data")
    if not data:
        raise RuntimeError(f"GraphQL response missing data: {body}")

    def normalize(connection):
        return [
            {
                "title": node["title"],
                "url": node["url"],
                "repo": node["repository"]["nameWithOwner"],
                "createdAt": node["createdAt"],
            }
            for node in connection["nodes"]
        ]

    return normalize(data["prs"]), normalize(data["issues"])


def main():
    """Fetch activity, inject it into the README, and write back if changed."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    login = os.environ.get("PROFILE_LOGIN", "shini4i")

    prs, issues = fetch_activity(token, login)
    block = render_activity(prs, issues)

    with open(README_PATH, encoding="utf-8") as fh:
        current = fh.read()
    updated = inject(current, block)

    if updated == current:
        print("README already up to date.")
        return
    with open(README_PATH, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("README activity section updated.")


if __name__ == "__main__":
    main()
