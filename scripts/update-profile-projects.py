#!/usr/bin/env python3
"""Refresh the profile README's public-repository list from GitHub's public API."""
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

def clean(value: str) -> str:
    return html.escape((value or "").replace("\n", " ").strip(), quote=True)

def main():
    with open(README, encoding="utf-8") as file:
        readme = file.read()
    if START not in readme or END not in readme:
        raise SystemExit("README project markers are missing; refusing to overwrite content.")

    repos = [
        repo for repo in fetch_repositories()
        if repo.get("owner", {}).get("login", "").lower() == USERNAME
        and repo.get("name", "").lower() != USERNAME
        and not repo.get("fork")
        and not repo.get("archived")
        and not repo.get("disabled")
    ]
    repos.sort(key=lambda repo: (repo.get("stargazers_count", 0), repo.get("updated_at", "")), reverse=True)
    repos = repos[:15]

    if not repos:
        section = "_No public repositories found yet._"
    else:
        rows = []
        for repo in repos:
            name = clean(repo.get("name", "Repository"))
            url = repo.get("html_url", "")
            description = clean(repo.get("description") or "A public project by Samyog.")
            language = clean(repo.get("language") or "Multiple technologies")
            stars = int(repo.get("stargazers_count") or 0)
            rows.append(
                f'<tr><td><a href="{url}"><strong>{name}</strong></a><br>'
                f'<sub>{description}</sub></td>'
                f'<td>{language}</td><td>★ {stars}</td></tr>'
            )
        section = (
            '<table>\n<tr><th>Repository</th><th>Primary language</th><th>Stars</th></tr>\n'
            + "\n".join(rows)
            + "\n</table>"
        )

    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    updated = before + START + "\n" + section + "\n" + END + after
    if updated != readme:
        with open(README, "w", encoding="utf-8", newline="\n") as file:
            file.write(updated)
        print(f"Updated profile with {len(repos)} public repositories.")
    else:
        print(f"Profile repository list is already current ({len(repos)} repositories).")

if __name__ == "__main__":
    main()
