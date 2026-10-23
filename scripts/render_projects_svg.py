#!/usr/bin/env python3
"""
Render data/projects.json (written by fetch_projects.py) as:

  assets/projects/<slug>.svg   one animated "live deployment" card per project
  assets/deploy-ticker.svg     a marquee of the newest builds
  README.md                    the table between <!-- LIVE-DEPLOYMENTS:* --> markers

Every card links out with <a href> in the README; the SVG itself is a plain
<img>, so GitHub's image sandbox is enough. Only the live deployment URL is
rendered -- never a repo URL -- because the source repo may be private.

Animation rules for GitHub's SVG-as-image sandbox:
  * CSS @keyframes and SMIL both run; JavaScript never does.
  * No external fonts, images or scripts (the sandbox blocks them).
  * The still frame is complete on its own: animations use `backwards`, never
    `both`, so nothing depends on an animation tick to become readable.
  * Every loop is slow and low-contrast -- motion cues, not a laser show.

    python scripts/render_projects_svg.py
"""
import datetime
import hashlib
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = os.path.join(ROOT, "data", "projects.json")
OUT_DIR = os.path.join(ROOT, "assets", "projects")
TICKER = os.path.join(ROOT, "assets", "deploy-ticker.svg")
README = os.path.join(ROOT, "README.md")

START = "<!-- LIVE-DEPLOYMENTS:START -->"
END = "<!-- LIVE-DEPLOYMENTS:END -->"

W, H = 440, 178
CARD_W = 440

MONO = "ui-monospace,SFMono-Regular,'Cascadia Code',Menlo,Consolas,monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"

INK = "#f8fafc"
SOFT = "#9db0c8"
MUTED = "#64748b"
FRAME = "#1e293b"
TAG_BG = "#0f172a"

ACCENTS = {
    "cyan": ("#22d3ee", "#0e7490"),
    "indigo": ("#818cf8", "#4338ca"),
    "emerald": ("#34d399", "#047857"),
    "amber": ("#fbbf24", "#b45309"),
    "pink": ("#f472b6", "#be185d"),
    "sky": ("#38bdf8", "#0369a1"),
    "violet": ("#a78bfa", "#6d28d9"),
}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def accent_of(p):
    return ACCENTS.get((p.get("accent") or "").lower(), ACCENTS["cyan"])


def clip_text(s, limit):
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    cut = s[: limit - 1].rstrip()
    if " " in cut[limit // 2 :]:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:-") + "…"


def wrap(s, limit, lines=2):
    words = (s or "").split()
    out, cur = [], ""
    for word in words:
        candidate = (cur + " " + word).strip()
        if len(candidate) <= limit:
            cur = candidate
            continue
        if cur:
            out.append(cur)
        cur = word
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if not out:
        return [""]
    # If anything was dropped, mark the last kept line as truncated.
    kept = " ".join(out)
    if len(kept.split()) < len(words):
        out[-1] = out[-1].rstrip(" ,.;:-") + "…"
    return [clip_text(line, limit) for line in out]


def short_hash(*parts):
    return int(hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:6], 16)


def age_label(iso_ts, gen_ts):
    if not iso_ts:
        return "live on vercel"
    try:
        when = datetime.datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        now = datetime.datetime.fromisoformat(gen_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return "live on vercel"
    delta = now - when
    minutes = max(0, int(delta.total_seconds() // 60))
    if minutes < 60:
        return "deployed just now" if minutes < 5 else f"deployed {minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"deployed {hours}h ago"
    days = hours // 24
    if days < 7:
        return f"deployed {days}d ago"
    weeks = days // 7
    if weeks < 6:
        return f"deployed {weeks}w ago"
    months = days // 30
    return f"deployed {months}mo ago"


def initials(name):
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    if not words:
        return "LIVE"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def tag_width(label):
    return 18 + len(label) * 5.75


# --------------------------------------------------------------------------
# one card
# --------------------------------------------------------------------------
def render_card(p, gen_ts):
    a, a_dim = accent_of(p)
    name = p.get("name") or "Untitled build"
    host = p.get("host") or p.get("live_url", "")
    desc = p.get("description") or ""
    tags = [t for t in (p.get("tags") or []) if t][:3]
    platform = (p.get("platform") or "vercel").upper()
    framework = (p.get("framework") or "").upper()
    subtitle = f"{platform} · {framework}" if framework else platform
    age = age_label(p.get("deployed_at"), gen_ts)

    h = short_hash(p.get("slug", name))
    sheen_delay = 0.9 + (h % 31) / 10.0
    dot_delay = (h % 17) / 10.0
    beam_delay = 1.2 + (h % 23) / 10.0
    drift_delay = (h % 13) / 10.0

    lines = wrap(desc, 62, 2)
    title = clip_text(name, 27)
    subtitle = clip_text(subtitle, 34)
    footer_host = clip_text(host, 36)

    # tags laid out left to right, dropping any that would overflow 400px
    tag_parts, x = [], 20.0
    used = []
    for i, tag in enumerate(tags):
        label = clip_text(tag, 18)
        w = tag_width(label)
        if x + w > 420:
            break
        first = i == 0
        fill = a if first else "#94a3b8"
        tag_parts.append(
            f'<g transform="translate({x:.1f},112)">'
            f'<rect width="{w:.1f}" height="20" rx="5" fill="'
            f'{a if first else TAG_BG}" fill-opacity="{0.12 if first else 0.75}" '
            f'stroke="{a if first else "#233043"}" stroke-opacity="{0.5 if first else 0.9}" '
            f'stroke-width="0.8"/>'
            f'<text x="{w / 2:.1f}" y="13.5" text-anchor="middle" font-family="{MONO}" '
            f'font-size="9.5" font-weight="600" fill="{fill}">{esc(label)}</text>'
            f"</g>"
        )
        used.append(label)
        x += w + 7

    desc_parts = []
    for i, line in enumerate(lines):
        desc_parts.append(
            f'<text x="20" y="{81 + i * 17}" font-family="{SANS}" font-size="11.5" '
            f'fill="{SOFT}">{esc(line)}</text>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="t{h} d{h}">
<title id="t{h}">{esc(name)} — live at {esc(host)}</title>
<desc id="d{h}">{esc(desc)}</desc>
<defs>
  <linearGradient id="bg{h}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#0b1220"/><stop offset="0.55" stop-color="#080d17"/><stop offset="1" stop-color="#05080f"/>
  </linearGradient>
  <linearGradient id="edge{h}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{a}" stop-opacity="0.55"/>
    <stop offset="0.45" stop-color="#243044" stop-opacity="0.9"/>
    <stop offset="1" stop-color="{a_dim}" stop-opacity="0.35"/>
  </linearGradient>
  <radialGradient id="aura{h}" cx="0.5" cy="0.5" r="0.5">
    <stop offset="0" stop-color="{a}" stop-opacity="0.20"/>
    <stop offset="0.65" stop-color="{a}" stop-opacity="0.05"/>
    <stop offset="1" stop-color="{a}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="bar{h}" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{a_dim}" stop-opacity="0.15"/>
    <stop offset="0.35" stop-color="{a}" stop-opacity="0.85"/>
    <stop offset="0.7" stop-color="{a}" stop-opacity="0.35"/>
    <stop offset="1" stop-color="{a}" stop-opacity="0.08"/>
  </linearGradient>
  <linearGradient id="sheen{h}" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
    <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.09"/>
    <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
  </linearGradient>
  <linearGradient id="icon{h}" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{a}" stop-opacity="0.30"/>
    <stop offset="1" stop-color="{a_dim}" stop-opacity="0.18"/>
  </linearGradient>
  <pattern id="grid{h}" width="22" height="22" patternUnits="userSpaceOnUse">
    <path d="M22 0H0V22" fill="none" stroke="#243044" stroke-width="0.6" stroke-opacity="0.5"/>
  </pattern>
  <clipPath id="clip{h}"><rect width="{W}" height="{H}" rx="15"/></clipPath>
</defs>
<style>
  @keyframes rise{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
  @keyframes sweep{{0%{{transform:translateX(0)}}42%,100%{{transform:translateX(760px)}}}}
  @keyframes breathe{{0%,100%{{transform:translate(0,0) scale(1)}}50%{{transform:translate(-14px,10px) scale(1.14)}}}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.25}}}}
  @keyframes beam{{0%{{transform:translateX(-90px)}}100%{{transform:translateX(450px)}}}}
  @keyframes blink{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}
  @keyframes nudge{{0%,100%{{transform:translateX(0)}}50%{{transform:translateX(3px)}}}}
  .card{{animation:rise 0.7s cubic-bezier(0.16,1,0.3,1) backwards}}
  .sheen{{animation:sweep 8s cubic-bezier(0.4,0,0.2,1) {sheen_delay:.1f}s infinite}}
  .aura{{animation:breathe 15s ease-in-out {drift_delay:.1f}s infinite}}
  .dot{{animation:pulse 2.4s ease-in-out {dot_delay:.1f}s infinite}}
  .beam{{animation:beam 5.5s linear {beam_delay:.1f}s infinite}}
  .caret{{animation:blink 1.1s steps(1,end) infinite}}
  .link{{animation:nudge 3s ease-in-out infinite}}
  @media (prefers-reduced-motion: reduce){{.card,.sheen,.aura,.dot,.beam,.caret,.link{{animation:none!important}}}}
</style>
<g class="card">
  <rect width="{W}" height="{H}" rx="15" fill="url(#bg{h})"/>
  <g clip-path="url(#clip{h})">
    <rect width="{W}" height="{H}" fill="url(#grid{h})" opacity="0.34"/>
    <circle class="aura" cx="398" cy="12" r="120" fill="url(#aura{h})" style="transform-box:fill-box;transform-origin:center"/>
    <g transform="skewX(-18)"><rect class="sheen" x="-190" y="-60" width="160" height="320" fill="url(#sheen{h})"/></g>
    <rect class="beam" x="0" y="{H - 4}" width="80" height="4" fill="#ffffff" opacity="0.55"/>
    <rect x="0" y="{H - 4}" width="{W}" height="4" fill="url(#bar{h})"/>
  </g>
  <rect x="0.6" y="0.6" width="{W - 1.2}" height="{H - 1.2}" rx="14.4" fill="none" stroke="url(#edge{h})" stroke-width="1.2"/>
  <path d="M16 1.2H424" stroke="#ffffff" stroke-opacity="0.07"/>

  <rect x="20" y="18" width="36" height="36" rx="10" fill="url(#icon{h})" stroke="{a}" stroke-opacity="0.45" stroke-width="1"/>
  <text x="38" y="41" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="800" fill="#ffffff" letter-spacing="0.6">{esc(initials(name))}</text>

  <text x="66" y="34" font-family="{SANS}" font-size="17" font-weight="700" fill="{INK}" letter-spacing="-0.2">{esc(title)}</text>
  <text x="66" y="51" font-family="{MONO}" font-size="9.5" fill="{MUTED}" letter-spacing="0.9">{esc(subtitle)}</text>

  <g transform="translate(364,18)">
    <rect width="56" height="20" rx="10" fill="#052e22" fill-opacity="0.9" stroke="#10b981" stroke-opacity="0.4" stroke-width="0.9"/>
    <circle cx="11" cy="10" r="2.6" fill="#34d399" class="dot"/>
    <circle cx="11" cy="10" r="2.6" fill="none" stroke="#34d399" stroke-width="1">
      <animate attributeName="r" values="2.6;9" dur="2.4s" begin="{dot_delay:.1f}s" repeatCount="indefinite"/>
      <animate attributeName="stroke-opacity" values="0.6;0" dur="2.4s" begin="{dot_delay:.1f}s" repeatCount="indefinite"/>
    </circle>
    <text x="19" y="13.4" font-family="{MONO}" font-size="8.5" font-weight="700" fill="#6ee7b7" letter-spacing="0.9">LIVE</text>
  </g>

  {''.join(desc_parts)}
  {''.join(tag_parts)}

  <line x1="20" y1="142" x2="420" y2="142" stroke="#1e293b" stroke-width="1"/>
  <line x1="20" y1="142" x2="150" y2="142" stroke="{a}" stroke-opacity="0.55" stroke-width="1"/>

  <circle cx="23" cy="157" r="2" fill="{a}" opacity="0.8"/>
  <text x="30" y="160" font-family="{MONO}" font-size="9" fill="{MUTED}" letter-spacing="0.6">{esc(age)}</text>
  <g class="link">
    <text x="420" y="160" text-anchor="end" font-family="{MONO}" font-size="9.5" fill="{a}" letter-spacing="0.2">{esc(footer_host)}</text>
  </g>
</g>
</svg>
'''
    return svg


# --------------------------------------------------------------------------
# ticker
# --------------------------------------------------------------------------
def render_ticker(projects, gen_ts):
    tw, th = 900, 46
    slot = 360
    name_x, age_x, host_x = 14, 146, 222
    items = []
    for p in projects:
        a, _ = accent_of(p)
        age = age_label(p.get("deployed_at"), gen_ts).replace("deployed ", "")
        if age == "live on vercel":
            age = "live"
        items.append(
            (
                clip_text(p.get("name") or "", 20),
                clip_text(p.get("host") or "", 24),
                clip_text(age, 10),
                a,
            )
        )
    if not items:
        items = [("No live builds yet", "deploy something", "soon", "#22d3ee")]

    def run(opacity):
        out = []
        for i, (name, host, age, a) in enumerate(items):
            out.append(
                f'<g transform="translate({i * slot},0)" opacity="{opacity}">'
                f'<circle cx="2" cy="23" r="2.4" fill="{a}"/>'
                f'<text x="{name_x}" y="26" font-family="{SANS}" font-size="11.5" font-weight="700" fill="#e2e8f0">{esc(name)}</text>'
                f'<text x="{age_x}" y="26" font-family="{MONO}" font-size="9.5" fill="#64748b">{esc(age)}</text>'
                f'<text x="{host_x}" y="26" font-family="{MONO}" font-size="9.5" fill="{a}" opacity="0.9">{esc(host)}</text>'
                f"</g>"
            )
        return "".join(out)

    total = slot * len(items)
    duration = max(34, min(90, round(total / 42)))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{tw}" height="{th}" viewBox="0 0 {tw} {th}" role="img" aria-label="Latest live deployments">
<title>Latest live deployments</title>
<defs>
  <linearGradient id="tbg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#0a101c"/><stop offset="0.5" stop-color="#0c1322"/><stop offset="1" stop-color="#080d16"/>
  </linearGradient>
  <linearGradient id="tedge" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#22d3ee" stop-opacity="0.45"/>
    <stop offset="0.5" stop-color="#6366f1" stop-opacity="0.35"/>
    <stop offset="1" stop-color="#34d399" stop-opacity="0.35"/>
  </linearGradient>
  <linearGradient id="tfade" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="#000"/><stop offset="0.04" stop-color="#fff"/>
    <stop offset="0.9" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
  </linearGradient>
  <mask id="tmask" maskUnits="userSpaceOnUse" x="0" y="0" width="{tw}" height="{th}"><rect width="{tw}" height="{th}" fill="url(#tfade)"/></mask>
  <clipPath id="tclip"><rect x="0" y="0" width="{tw}" height="{th}" rx="11"/></clipPath>
</defs>
<style>
  @keyframes slide{{from{{transform:translateX(0)}}to{{transform:translateX(-{total}px)}}}}
  @keyframes tpulse{{0%,100%{{opacity:1}}50%{{opacity:0.2}}}}
  .track{{animation:slide {duration}s linear infinite}}
  .tdot{{animation:tpulse 2s ease-in-out infinite}}
  @media (prefers-reduced-motion: reduce){{.track,.tdot{{animation:none!important}}}}
</style>
<rect width="{tw}" height="{th}" rx="11" fill="url(#tbg)"/>
<rect x="0.6" y="0.6" width="{tw - 1.2}" height="{th - 1.2}" rx="10.4" fill="none" stroke="url(#tedge)" stroke-width="1"/>
<g clip-path="url(#tclip)">
  <rect width="{tw}" height="{th}" fill="#0b1220"/>
  <g mask="url(#tmask)">
    <g clip-path="url(#tclip)">
      <g class="track">
        {run(1)}
        {run(1)}
      </g>
    </g>
  </g>
</g>
<rect x="0" y="0" width="158" height="{th}" fill="#080d16" opacity="0.92"/>
<circle class="tdot" cx="20" cy="23" r="3.2" fill="#34d399"/>
<text x="32" y="19" font-family="{MONO}" font-size="7.5" fill="#475569" letter-spacing="1.6">VERCEL EDGE</text>
<text x="32" y="30.5" font-family="{MONO}" font-size="8.5" font-weight="700" fill="#7dd3fc" letter-spacing="1.1">LATEST DEPLOY</text>
<line x1="158" y1="10" x2="158" y2="{th - 10}" stroke="#1e293b" stroke-width="1"/>
</svg>
'''
    return svg


# --------------------------------------------------------------------------
# README block
# --------------------------------------------------------------------------
def render_readme_block(projects):
    cells = []
    for p in projects:
        slug = p.get("slug") or "project"
        alt = f"{p.get('name')} — live at {p.get('host')}"
        cells.append(
            '    <td align="center" width="50%">\n'
            f'      <a href="{esc(p.get("live_url"))}">'
            f'<img src="./assets/projects/{slug}.svg" width="440" alt="{esc(alt)}" /></a>\n'
            "    </td>"
        )
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i : i + 2]
        if len(pair) == 1:
            pair.append('    <td align="center" width="50%"></td>')
        rows.append("  <tr>\n" + "\n".join(pair) + "\n  </tr>")
    table = "<table>\n" + "\n".join(rows) + "\n</table>"

    return (
        f"{START}\n"
        '<div align="center">\n\n'
        '<img src="./assets/deploy-ticker.svg" width="100%" '
        'alt="Newest live deployments, auto-refreshed" />\n\n'
        f"{table}\n\n"
        f'<sub><code>{len(projects)} live builds</code> · every card opens the deployed site · '
        "auto-synced from Vercel</sub>\n\n"
        "</div>\n"
        f"{END}"
    )


# --------------------------------------------------------------------------
def write_if_changed(path, content):
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            if f.read() == content:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    return True


def update_readme(block):
    with open(README, encoding="utf-8", newline="") as f:
        text = f.read()
    if START not in text or END not in text:
        print("note: README markers missing; skipped README update")
        return False
    if "\r\n" in text:  # keep the README's existing line endings
        block = block.replace("\n", "\r\n")
    before, _, rest = text.partition(START)
    _, _, after = rest.partition(END)
    return write_if_changed(README, before + block + after)


def main():
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)
    projects = data.get("projects") or []
    gen_ts = data.get("generated_at") or datetime.datetime.now(
        datetime.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not projects:
        raise SystemExit("no projects in data/projects.json; run fetch_projects.py first")

    slugs = set()
    for p in projects:
        slug = p.get("slug") or "project"
        slugs.add(slug)
        changed = write_if_changed(
            os.path.join(OUT_DIR, f"{slug}.svg"), render_card(p, gen_ts)
        )
        print(f"{'wrote' if changed else 'kept '} assets/projects/{slug}.svg")

    # Drop cards for projects that are no longer live.
    if os.path.isdir(OUT_DIR):
        for name in os.listdir(OUT_DIR):
            if name.endswith(".svg") and name[:-4] not in slugs:
                os.remove(os.path.join(OUT_DIR, name))
                print(f"removed stale assets/projects/{name}")

    write_if_changed(TICKER, render_ticker(projects, gen_ts))
    print(f"wrote assets/deploy-ticker.svg ({len(projects)} items)")

    if update_readme(render_readme_block(projects)):
        print("updated README live-deployments block")
    else:
        print("README live-deployments block already current")


if __name__ == "__main__":
    main()
