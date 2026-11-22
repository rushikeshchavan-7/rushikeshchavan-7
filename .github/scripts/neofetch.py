"""Builds the neofetch-style README card (assets/neofetch/{dark,light}.svg).

Run daily by .github/workflows/neofetch.yml so uptime and the contribution graph stay current.
Locally it runs without a token and reuses the saved contributions.json.
"""
import datetime as dt
import html
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "neofetch"
CONTRIB_FILE = OUT / "contributions.json"
YEARS_SHOWN = 3
USER = "rushikeshchavan-7"
SINCE = dt.date(2022, 1, 1)  # first production-grade project
MONO = "ConsolasFallback,Consolas,'SFMono-Regular',Menlo,'Liberation Mono',monospace"
WIDTH = 60  # characters in the info column

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657", value="#a5d6ff", dots="#616e7f", art="#c9d1d9", accent="#ff7b72", cells=("#21262d", "#0e4429", "#006d32", "#26a641", "#39d353")),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800", value="#0a3069", dots="#c2cfde", art="#24292f", accent="#cf222e", cells=("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")),
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


def fetch_contributions(years):
    """Daily contribution counts for the given years, merged into contributions.json."""
    saved = json.loads(CONTRIB_FILE.read_text()) if CONTRIB_FILE.exists() else {}
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return saved
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
      contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    for y in years:
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": {"login": USER, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"}}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        try:
            weeks = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        except Exception as exc:  # keep last good data on any API hiccup
            print(f"contributions fetch failed for {y}:", exc)
            continue
        for w in weeks:
            for d in w["contributionDays"]:
                saved[d["date"]] = d["contributionCount"]
    saved = dict(sorted(saved.items()))
    CONTRIB_FILE.write_text(json.dumps(saved, separators=(",", ":")))
    return saved


def levels(counts):
    """GitHub-style 0-4 levels from quartiles of the non-zero days."""
    nz = sorted(c for c in counts if c)
    if not nz:
        return lambda c: 0
    q = [nz[int(len(nz) * f) - 1 if int(len(nz) * f) else 0] for f in (.25, .5, .75)]
    return lambda c: 0 if c == 0 else 1 if c <= q[0] else 2 if c <= q[1] else 3 if c <= q[2] else 4


def build(theme, art, info, contrib, today):
    t = THEMES[theme]
    e = html.escape
    fs, lh = 15.5, 20
    art_fs, art_lh = 8.5, 9.6
    art_w = max(map(len, art)) * art_fs * 0.6
    ix = 40 + art_w + 36
    top = max(len(info) * lh + 70, len(art) * art_lh + 70)
    years = list(range(today.year - YEARS_SHOWN + 1, today.year + 1))[::-1]
    cell, gap, ylab = 12, 3, 20
    graph_h = 50 + len(years) * (7 * (cell + gap) + 64)
    h = top + graph_h - 20
    w = int(ix + WIDTH * fs * 0.6 + 40)
    ay = (top - len(art) * art_lh) / 2 + art_fs

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
    # ---- contribution graph ----
    gx, gy = 40, top
    gw = w - 80
    out.append(f'<text x="{gx}" y="{gy}" font-size="{fs}" xml:space="preserve"><tspan fill="{t["accent"]}" font-weight="bold">- Contributions</tspan>'
               f'<tspan fill="{t["dots"]}"> {"—" * int((gw / (fs * 0.6)) - 16)}</tspan></text>')
    y0 = gy + 36
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    for yr in years:
        start = dt.date(yr, 1, 1)
        end = min(dt.date(yr, 12, 31), today)
        days = [(start + dt.timedelta(n)) for n in range((end - start).days + 1)]
        counts = [contrib.get(d.isoformat(), 0) for d in days]
        lvl = levels(counts)
        total = sum(counts)
        out.append(f'<text x="{gx}" y="{y0}" font-size="13.5" xml:space="preserve"><tspan fill="{t["key"]}">{yr}</tspan>'
                   f'<tspan fill="{t["dots"]}">: </tspan><tspan fill="{t["value"]}">{total:,} contributions</tspan></text>')
        cy0 = y0 + 30
        offset = (start.weekday() + 1) % 7  # Sunday-first rows like GitHub
        span = (53) * (cell + gap)
        x0 = gx + (gw - span) / 2
        for mi, m in enumerate(months):
            md = dt.date(yr, mi + 1, 1)
            col = ((md - start).days + offset) // 7
            out.append(f'<text x="{x0 + col * (cell + gap)}" y="{y0 + 22}" font-size="11" fill="{t["dots"]}">{m}</text>')
        rects = []
        for d, c in zip(days, counts):
            idx = (d - start).days + offset
            col, row = divmod(idx, 7)
            rects.append(f'<rect x="{x0 + col * (cell + gap)}" y="{cy0 + row * (cell + gap)}" width="{cell}" height="{cell}" rx="2.5" fill="{t["cells"][lvl(c)]}"/>')
        out.append("".join(rects))
        y0 = cy0 + 7 * (cell + gap) + 34
    out.append("</svg>")
    (OUT / f"{theme}.svg").write_text("\n".join(out) + "\n")


def main():
    art = (OUT / "ascii-art.txt").read_text().rstrip("\n").split("\n")
    today = dt.date.today()
    contrib = fetch_contributions(range(today.year - YEARS_SHOWN + 1, today.year + 1))
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
    ]
    for theme in THEMES:
        build(theme, art, info, contrib, today)
    print("built neofetch cards;", sum(contrib.values()), "contributions on record")


if __name__ == "__main__":
    main()
