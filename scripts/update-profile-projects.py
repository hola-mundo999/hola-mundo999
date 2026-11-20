#!/usr/bin/env python3
"""Refresh the profile README with the user's latest public repositories."""
from __future__ import annotations

import html
import json
import re
import urllib.request

USERNAME = "hola-mundo999"
README = "README.md"
START = "<!-- PROJECTS:START -->"
END = "<!-- PROJECTS:END -->"
API = f"https://api.github.com/users/{USERNAME}/repos?type=owner&sort=updated&per_page=100"
FEATURED_REPOS = {
    "auvyren-virtual-store",
    "ai-csit-study-assistant",
    "ai-gesture-controller-",
    "prime-event-ticket-manager",
}
DISPLAY_NAMES = {
    "country-info-app": "Country Explorer",
    "github-user-finder": "GitHub Finder",
    "note-app": "NoteNest",
    "password-generator": "PassForge",
    "random-color-palette": "Paletto",
    "result-card-generator": "Result Announced",
    "tu-csit-notice-hub": "TU CSIT Notice Hub",
}


def fetch_repositories():
    repos = []
    url = API
    while url:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "hola-mundo999-profile-project-sync",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            repos.extend(json.load(response))
            link = response.headers.get("Link", "")
        match = re.search(r'<([^>]+)>; rel="next"', link)
        url = match.group(1) if match else None
    return repos


def clean(value: str, limit: int = 140) -> str:
    value = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(value) > limit:
        value = value[: limit - 1].rstrip() + "…"
    return html.escape(value, quote=True)


def main():
    with open(README, encoding="utf-8") as file:
        readme = file.read()

    if START not in readme or END not in readme:
        raise SystemExit("README project markers are missing; refusing to overwrite content.")

    repos = [
        repo for repo in fetch_repositories()
        if repo.get("owner", {}).get("login", "").lower() == USERNAME
        and repo.get("name", "").lower() != USERNAME
        and repo.get("name", "").lower() not in FEATURED_REPOS
        and not repo.get("fork")
        and not repo.get("archived")
        and not repo.get("disabled")
    ]
    repos.sort(
        key=lambda repo: (repo.get("updated_at", ""), repo.get("name", "").lower()),
        reverse=True,
    )
    repos = repos[:30]

    if not repos:
        section = "_No additional public repositories to show yet._"
    else:
        rows = []
        for repo in repos:
            slug = repo.get("name", "Repository").lower()
            display_name = DISPLAY_NAMES.get(slug, repo.get("name", "Repository").replace("-", " ").title())
            name = clean(display_name, 80)
            description_text = repo.get("description") or "Personal project."
            description_text = re.sub(
                r"\s+by Samyog Sapkota\s*$", "", description_text.strip(), flags=re.IGNORECASE
            )
            description = clean(description_text)
            language = clean(repo.get("language") or "Various")
            url = repo.get("html_url", "")
            homepage = (repo.get("homepage") or "").strip()
            if not url.startswith(f"https://github.com/{USERNAME}/"):
                continue
            live_link = (
                f'<a href="{html.escape(homepage, quote=True)}">Live ↗</a>'
                if homepage.startswith(("https://", "http://"))
                else "—"
            )
            rows.append(
                f'<tr><td><a href="{url}"><strong>{name}</strong></a></td>'
                f'<td>{description}</td><td>{language}</td><td>{live_link}</td></tr>'
            )

        if rows:
            section = (
                "<table>\n"
                "<thead><tr><th>Project</th><th>About</th><th>Language</th><th>Demo</th></tr></thead>\n"
                "<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>"
            )
        else:
            section = "_No additional public repositories to show yet._"

    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    updated = before + START + "\n" + section + "\n" + END + after

    if updated != readme:
        with open(README, "w", encoding="utf-8", newline="\n") as file:
            file.write(updated)
        print(f"Updated profile with {len(repos)} additional public repositories.")
    else:
        print(f"Profile repository list is already current ({len(repos)} repositories).")


if __name__ == "__main__":
    main()
