"""Builds the neofetch-style README card (assets/neofetch/{dark,light}.svg).

Run daily by .github/workflows/neofetch.yml so uptime and GitHub stats stay current.
Locally it runs without a token and keeps the last saved stats.
"""
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "neofetch"
STATS_FILE = OUT / "stats.json"
USER = "rushikeshchavan-7"
SINCE = dt.date(2022, 1, 1)  # first production-grade project
MONO = "ConsolasFallback,Consolas,'SFMono-Regular',Menlo,'Liberation Mono',monospace"
WIDTH = 60  # characters in the info column

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657", value="#a5d6ff", dots="#616e7f", art="#c9d1d9", accent="#ff7b72"),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800", value="#0a3069", dots="#c2cfde", art="#24292f", accent="#cf222e"),
}


def uptime(today):
    y = today.year - SINCE.year
    m = today.month - SINCE.month
    d = today.day - SINCE.day
    if d < 0:
        m -= 1
        prev = (today.replace(day=1) - dt.timedelta(days=1))
        d += prev.day
    if m < 0:
        y -= 1
        m += 12
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(y, 'year')}, {plural(m, 'month')}, {plural(d, 'day')}"


def fetch_stats():
    saved = json.loads(STATS_FILE.read_text()) if STATS_FILE.exists() else {}
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return saved
    query = """query($login:String!){user(login:$login){
      followers{totalCount}
      repositories(ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC,first:100){totalCount nodes{stargazerCount}}
      repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST],includeUserRepositories:false){totalCount}
      contributionsCollection{contributionCalendar{totalContributions}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    try:
        u = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]
    except Exception as exc:  # keep last good numbers on any API hiccup
        print("stats fetch failed:", exc)
        return saved
    stats = {
        "repos": u["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in u["repositories"]["nodes"]),
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "followers": u["followers"]["totalCount"],
        "contributions": u["contributionsCollection"]["contributionCalendar"]["totalContributions"],
    }
    STATS_FILE.write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def build(theme, art, info):
    t = THEMES[theme]
    e = html.escape
    fs, lh = 15.5, 20
    art_fs, art_lh = 8.5, 9.6
    art_w = max(map(len, art)) * art_fs * 0.6
    ix = 40 + art_w + 36
    h = max(len(info) * lh + 70, len(art) * art_lh + 70)
    w = int(ix + WIDTH * fs * 0.6 + 40)
    ay = (h - len(art) * art_lh) / 2 + art_fs

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{int(h)}" viewBox="0 0 {w} {int(h)}" font-family="{MONO}">',
           "<style>.c{animation:b 1.1s steps(1) infinite}@keyframes b{50%{opacity:0}}</style>",
           f'<rect x=".5" y=".5" width="{w-1}" height="{int(h)-1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
           f'<text x="40" y="{ay:.1f}" font-size="{art_fs}" fill="{t["art"]}" xml:space="preserve">']
    for i, line in enumerate(art):
        out.append(f'<tspan x="40" dy="{0 if i == 0 else art_lh}">{e(line)}</tspan>')
    out.append("</text>")

    y = 50
    out.append(f'<text x="{ix:.1f}" y="{y}" font-size="{fs}" fill="{t["text"]}" xml:space="preserve">')
    for i, row in enumerate(info):
        dy = 0 if i == 0 else lh
        kind = row[0]
        if kind == "title":
            name = row[1]
            out.append(f'<tspan x="{ix:.1f}" dy="{dy}" fill="{t["accent"]}" font-weight="bold">{e(name)}</tspan>'
                       f'<tspan fill="{t["dots"]}"> {"—" * (WIDTH - len(name) - 1)}</tspan>')
        elif kind == "blank":
            out.append(f'<tspan x="{ix:.1f}" dy="{dy}"> </tspan>')
        else:
            pairs = row[1]
            parts, used = [], 0
            for j, (k, v) in enumerate(pairs):
                sep = " | " if j else ""
                # last pair fills the line with leader dots, earlier pairs are compact
                if j == len(pairs) - 1:
                    dots = max(1, WIDTH - used - len(sep) - len(k) - 2 - len(v) - 2)
                    seg = (f'<tspan fill="{t["text"]}">{sep}</tspan><tspan fill="{t["key"]}">{e(k)}</tspan>'
                           f'<tspan fill="{t["dots"]}">: {"." * dots} </tspan><tspan fill="{t["value"]}">{e(v)}</tspan>')
                else:
                    seg = (f'<tspan fill="{t["text"]}">{sep}</tspan><tspan fill="{t["key"]}">{e(k)}</tspan>'
                           f'<tspan fill="{t["dots"]}">: </tspan><tspan fill="{t["value"]}">{e(v)}</tspan>')
                    used += len(sep) + len(k) + 2 + len(v)
                parts.append(seg)
            out.append(f'<tspan x="{ix:.1f}" dy="{dy}">{"".join(parts)}</tspan>')
    out.append("</text>")
    cy = 50 + (len(info) - 1) * lh + lh
    out.append(f'<text x="{ix:.1f}" y="{cy}" font-size="{fs}" fill="{t["accent"]}">❯ <tspan class="c" fill="{t["text"]}">█</tspan></text>')
    out.append("</svg>")
    (OUT / f"{theme}.svg").write_text("\n".join(out) + "\n")


def main():
    art = (OUT / "ascii-art.txt").read_text().rstrip("\n").split("\n")
    s = fetch_stats()
    n = lambda key: f"{s[key]:,}" if key in s else "—"
    kv = lambda *pairs: ("kv", list(pairs))
    info = [
        ("title", "rushikesh@chavan"),
        kv(("Role", "Software Engineer")),
        kv(("Host", "CareEdge Analytics & Advisory")),
        kv(("Uptime", uptime(dt.date.today()))),
        kv(("Location", "Mumbai, India")),
        kv(("Motto", "Jack of all trades. Mastering them all.")),
        ("blank",),
        kv(("Languages.Programming", "C#, Python, TypeScript, SQL")),
        kv(("Stack.AI", "LangChain, LangGraph, RAG, Groq, Gemini")),
        kv(("Stack.Backend", ".NET Core, FastAPI, PostgreSQL, Oracle")),
        kv(("Stack.Frontend", "Angular, React, Next.js, Tailwind")),
        kv(("Stack.Cloud", "AWS, Docker, Azure DevOps, Actions")),
        ("blank",),
        kv(("Shipped", "CrediSense, DocuMind, Cultivate 365")),
        kv(("Awards", "Emerging Engineer + Rookie of the Year FY26")),
        ("blank",),
        ("title", "- Contact"),
        kv(("Email", "rushikeshchavan2002@gmail.com")),
        kv(("Website", "rushikeshh.in")),
        kv(("LinkedIn", "rushikesh-chavan-275282211")),
        ("blank",),
        ("title", "- GitHub Stats"),
        kv(("Repos", n("repos")), ("Contributed", n("contributed")), ("Stars", n("stars"))),
        kv(("Followers", n("followers")), ("Contributions (1y)", n("contributions"))),
    ]
    for theme in THEMES:
        build(theme, art, info)
    print("built neofetch cards", s)


if __name__ == "__main__":
    main()
