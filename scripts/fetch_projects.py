#!/usr/bin/env python3
"""
Build data/projects.json -- the list of *live deployments* behind the animated
profile board -- from the Vercel API, then merge optional human metadata from
data/project_meta.json.

Why Vercel and not GitHub: the source repo may be private, and the profile
repo's GITHUB_TOKEN can only see itself. Vercel's project list has every project
the token can read, private source or not, plus its production URL. That is all
this board needs: a name and a working live link. Repo names are used for
matching metadata only and are never written to projects.json or the README.

Auth (optional but recommended). Add a repository secret named VERCEL_TOKEN:
  Vercel -> Account Settings -> Tokens -> Create Token (scope: the account/team
  that owns the projects). Read access is enough; nothing here writes.
Optional:
  VERCEL_TEAM_ID   team id, if the projects live under a team
  VERCEL_SCOPE     team slug, alternative to VERCEL_TEAM_ID
  MAX_PROJECTS     how many to show (default 8)

Without a token the script still succeeds and republishes the pinned entries
from project_meta.json, so the board never goes blank. On a transient API error
it leaves the existing data/projects.json untouched.

    python scripts/fetch_projects.py
"""
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
META_PATH = os.path.join(ROOT, "data", "project_meta.json")
OUT_PATH = os.path.join(ROOT, "data", "projects.json")

API = "https://api.vercel.com"
TIMEOUT = 30
MAX_PROJECTS = int(os.environ.get("MAX_PROJECTS", "8"))

FRAMEWORKS = {
    "nextjs": "Next.js",
    "next": "Next.js",
    "vite": "Vite",
    "create-react-app": "React",
    "react": "React",
    "vue": "Vue",
    "nuxtjs": "Nuxt",
    "svelte": "Svelte",
    "sveltekit": "SvelteKit",
    "astro": "Astro",
    "remix": "Remix",
    "gatsby": "Gatsby",
    "angular": "Angular",
    "python": "Python",
    "flask": "Flask",
    "django": "Django",
    "hugo": "Hugo",
    "jekyll": "Jekyll",
    "eleventy": "Eleventy",
    "static": "Static",
}

ACCENTS = ["cyan", "indigo", "emerald", "amber", "pink", "sky", "violet"]


def log(msg):
    print(msg, flush=True)


def load_meta():
    try:
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f).get("projects", {})
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        log(f"warning: {META_PATH} is not valid JSON ({e}); continuing without metadata")
        return {}


def api_get(path, params, token):
    """Minimal authenticated GET. requests is imported lazily so the no-token
    path works on a bare Python install."""
    import requests

    query = dict(params or {})
    team = os.environ.get("VERCEL_TEAM_ID")
    if team:
        query["teamId"] = team
    elif os.environ.get("VERCEL_SCOPE"):
        query["slug"] = os.environ["VERCEL_SCOPE"]

    r = requests.get(
        f"{API}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=query,
        timeout=TIMEOUT,
    )
    if r.status_code in (401, 403):
        raise RuntimeError(f"{path} -> {r.status_code} (token cannot read this scope)")
    r.raise_for_status()
    return r.json()


def list_projects(token):
    """GET /v10/projects, following pagination. The response is either a bare
    array or {projects: [...], pagination: {next: <timestamp>}}."""
    projects, seen, cursor = [], set(), None
    for _ in range(12):
        params = {"limit": 100}
        if cursor:
            params["from"] = cursor
        payload = api_get("/v10/projects", params, token)
        if isinstance(payload, list):
            projects.extend(payload)
            break
        batch = payload.get("projects") or []
        projects.extend(batch)
        cursor = (payload.get("pagination") or {}).get("next")
        if not cursor or not batch or cursor in seen:
            break
        seen.add(cursor)
    return projects


def iso(ms):
    if not ms:
        return None
    try:
        return datetime.datetime.fromtimestamp(
            int(ms) / 1000, datetime.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError, OSError):
        return None


def host_of(url):
    if not url:
        return ""
    return re.sub(r"^https?://", "", url).split("/")[0].lower()


def live_deployment(project):
    """Newest READY production deployment, or None if the project has never
    shipped to production."""
    deployments = project.get("latestDeployments") or []
    ready = [
        d
        for d in deployments
        if d.get("target") == "production" and d.get("readyState") == "READY"
    ]
    if not ready:
        return None
    return max(ready, key=lambda d: d.get("createdAt") or 0)


def pick_from_aliases(aliases, project_name):
    """Prefer a real custom domain, then <project>.vercel.app, then any
    production-looking *.vercel.app alias. Branch/hash aliases lose."""
    aliases = [a for a in (aliases or []) if a and "*" not in a]
    custom = [a for a in aliases if not a.endswith(".vercel.app")]
    if custom:
        return "https://" + sorted(custom, key=len)[0]
    bare = f"{project_name}.vercel.app"
    if bare in aliases:
        return "https://" + bare
    clean = [a for a in aliases if a.endswith(".vercel.app") and "-git-" not in a]
    if clean:
        return "https://" + sorted(clean, key=len)[0]
    if aliases:
        return "https://" + sorted(aliases, key=len)[0]
    return None


def production_domain(project, token):
    """Fallback when deployment aliases only expose a *.vercel.app URL: ask for
    the project's production domains and take a verified custom one."""
    try:
        payload = api_get(
            f"/v9/projects/{project['id']}/domains",
            {"production": "true", "redirects": "false", "limit": 20},
            token,
        )
    except Exception as e:  # noqa: BLE001 - a missing domain must not drop the card
        log(f"  note: domains lookup failed for {project.get('name')}: {e}")
        return None
    domains = payload if isinstance(payload, list) else payload.get("domains", [])
    usable = [
        d
        for d in domains
        if d.get("name")
        and not d.get("redirect")
        and d.get("verified", True)
        and not d["name"].endswith(".vercel.app")
    ]
    if usable:
        return "https://" + usable[0]["name"]
    return None


def meta_for(meta, *keys):
    for key in keys:
        if key and key in meta:
            return meta[key]
    lowered = {k.lower(): v for k, v in meta.items()}
    for key in keys:
        if key and key.lower() in lowered:
            return lowered[key.lower()]
    return None


def prettify(name):
    words = re.split(r"[-_.\s]+", name)
    small = {"and", "of", "the", "with", "a", "an", "to", "for"}
    acronyms = {
        "ai": "AI", "ml": "ML", "cv": "CV", "llm": "LLM", "api": "API",
        "csit": "CSIT", "tu": "TU", "ui": "UI", "ux": "UX", "qr": "QR",
        "3d": "3D", "2d": "2D", "db": "DB", "js": "JS", "ts": "TS",
    }
    out = []
    for i, word in enumerate(words):
        if not word:
            continue
        low = word.lower()
        if low in acronyms:
            out.append(acronyms[low])
        elif low in small and i:
            out.append(low)
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out) or name


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def framework_label(project):
    raw = (project.get("framework") or "").lower()
    return FRAMEWORKS.get(raw, raw.replace("-", " ").title() if raw else "Web")


def vercel_entries(projects, token, meta):
    """One entry per project with a READY production deployment."""
    entries = []
    seen_meta = set()
    for project in projects:
        name = project.get("name") or ""
        if not name:
            continue
        deployment = live_deployment(project)
        if not deployment:
            continue
        repo = (project.get("link") or {}).get("repo") or ""
        entry_meta = meta_for(meta, name, repo)
        if entry_meta is not None:
            seen_meta.add(id(entry_meta))

        url = (entry_meta or {}).get("live_url")
        if not url:
            url = pick_from_aliases(
                (deployment.get("alias") or []) + (deployment.get("aliasFinal") or []),
                name,
            )
        if url and host_of(url).endswith(".vercel.app"):
            url = production_domain(project, token) or url
        if not url and deployment.get("url"):
            url = "https://" + deployment["url"]
        if not url:
            continue

        fw = framework_label(project)
        title = (entry_meta or {}).get("title") or prettify(name)
        description = (entry_meta or {}).get("description") or (
            f"{fw} build deployed to Vercel's edge network, shipped straight from "
            f"the latest production branch."
        )
        entries.append(
            {
                "name": title,
                "slug": (entry_meta or {}).get("slug") or slugify(title),
                "description": description,
                "tags": list((entry_meta or {}).get("tags") or [fw, "Vercel"])[:3],
                "live_url": url,
                "host": host_of(url),
                "platform": (entry_meta or {}).get("platform", "vercel"),
                "framework": fw,
                "deployed_at": iso(deployment.get("createdAt")),
                "pinned": False,
                "accent": (entry_meta or {}).get("accent")
                or ACCENTS[len(entries) % len(ACCENTS)],
            }
        )
    entries.sort(key=lambda e: e["deployed_at"] or "", reverse=True)
    return entries, seen_meta


def pinned_entries(meta, taken_hosts, taken_slugs, meta_ids=(), start_index=0):
    """Entries that should appear even when the API cannot see them (no token,
    another account, or only some projects exposed)."""
    entries = []
    for key, value in meta.items():
        if not value.get("pinned") or not value.get("live_url"):
            continue
        if id(value) in meta_ids:
            continue
        if host_of(value["live_url"]) in taken_hosts:
            continue
        title = value.get("title") or prettify(key)
        slug = value.get("slug") or slugify(title)
        if slug in taken_slugs:
            slug = slugify(slug + "-live")
        entries.append(
            {
                "name": title,
                "slug": slug,
                "description": value.get("description")
                or "Live production build, deployed and served from the edge.",
                "tags": list(value.get("tags") or ["Live"])[:3],
                "live_url": value["live_url"],
                "host": host_of(value["live_url"]),
                "platform": value.get("platform", "vercel"),
                "framework": value.get("framework", ""),
                "deployed_at": value.get("deployed_at"),
                "pinned": True,
                "accent": value.get("accent")
                or ACCENTS[(start_index + len(entries)) % len(ACCENTS)],
                "_order": value.get("order", 999),
            }
        )
    entries.sort(key=lambda e: (e["_order"], e["name"]))
    for e in entries:
        e.pop("_order", None)
    return entries


def build(api_projects, token, meta):
    entries, seen_meta = vercel_entries(api_projects, token, meta)
    entries += pinned_entries(
        meta,
        taken_hosts={e["host"] for e in entries},
        taken_slugs={e["slug"] for e in entries},
        meta_ids=seen_meta,
        start_index=len(entries),
    )
    return entries[:MAX_PROJECTS]


def main():
    meta = load_meta()
    token = (os.environ.get("VERCEL_TOKEN") or "").strip()
    api_projects, source = [], "pinned"

    if token:
        try:
            api_projects = list_projects(token)
            source = "vercel-api"
            log(f"Vercel API: {len(api_projects)} projects visible")
        except Exception as e:  # noqa: BLE001 - the board must survive API hiccups
            log(f"error: Vercel API unavailable ({e})")
            if os.path.exists(OUT_PATH):
                log(f"keeping existing {OUT_PATH} untouched")
                return 0
            log("no existing data file; falling back to pinned entries")
    else:
        log("VERCEL_TOKEN not set -> using pinned entries from data/project_meta.json")

    projects = build(api_projects, token, meta)
    if not projects:
        log("error: no live projects found and nothing pinned; not writing an empty board")
        return 1

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "source": source,
        "count": len(projects),
        "projects": projects,
    }
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    log(f"wrote {OUT_PATH}: {len(projects)} projects ({source})")
    for p in projects:
        log(f"  - {p['name']:<28} {p['live_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
