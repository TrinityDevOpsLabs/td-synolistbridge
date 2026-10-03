"""Generate release notes from commits reachable from a version tag."""
import argparse
import re
import subprocess
from pathlib import Path
from urllib.parse import quote


def git(*args):
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.PIPE).strip()


def generate(tag, repository):
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", tag):
        raise ValueError("Expected a version tag such as v1.1.0 or v1.1.0-rc.1")
    ref = "refs/tags/" + tag
    git("rev-parse", "--verify", ref + "^{commit}")
    try:
        previous = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "--exclude", tag, ref)
    except subprocess.CalledProcessError:
        previous = None
    revision = "refs/tags/" + previous + ".." + ref if previous else ref
    commits = git("log", "--reverse", "--format=%H%x09%s", revision)
    base = "https://github.com/" + repository
    groups = {"Added": [], "Fixed": [], "Documentation": [], "Other changes": []}
    for line in commits.splitlines():
        sha, subject = line.split("\t", 1)
        match = re.match(r"(\w+)(?:\([^)]*\))?!?:\s*(.+)", subject)
        kind = match.group(1) if match else ""
        category = {"feat": "Added", "fix": "Fixed", "docs": "Documentation"}.get(kind, "Other changes")
        # Escape commit text so Markdown/HTML cannot change the notes structure.
        subject = subject.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        subject = re.sub(r"([\\`*_{}\[\]()!|])", r"\\\1", subject)
        groups[category].append(f"- {subject} ([{sha[:7]}]({base}/commit/{sha}))")
    sections = ["## Changes"]
    for category, entries in groups.items():
        if entries:
            sections.append("### " + category + "\n\n" + "\n".join(entries))
    if not commits:
        sections.append("No new commits since the previous version tag.")
    current_url = quote(tag, safe="")
    link = f"{base}/compare/{quote(previous, safe='')}...{current_url}" if previous else f"{base}/commits/{current_url}"
    sections.append(f"**Full Changelog:** {link}")
    return "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag")
    parser.add_argument("repository")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(generate(args.tag, args.repository), encoding="utf-8")
