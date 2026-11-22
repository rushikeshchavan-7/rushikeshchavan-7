"""Builds the README card: ASCII portrait + 3-year contribution graph (assets/neofetch/{dark,light}.svg).

Run daily by .github/workflows/neofetch.yml so the contribution graph stays current.
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
MONO = "ConsolasFallback,Consolas,'SFMono-Regular',Menlo,'Liberation Mono',monospace"

THEMES = {
    "dark": dict(bg="#161b22", border="#30363d", text="#c9d1d9", key="#ffa657", value="#a5d6ff", dots="#616e7f", art="#c9d1d9", accent="#ff7b72", cells=("#21262d", "#0e4429", "#006d32", "#26a641", "#39d353")),
    "light": dict(bg="#f6f8fa", border="#d0d7de", text="#24292f", key="#953800", value="#0a3069", dots="#c2cfde", art="#24292f", accent="#cf222e", cells=("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39")),
}


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


def build(theme, art, contrib, today):
    t = THEMES[theme]
    e = html.escape
    art_fs, art_lh = 8.5, 9.6
    art_w = max(map(len, art)) * art_fs * 0.6
    art_h = len(art) * art_lh
    cell, gap = 11, 2.5
    step = cell + gap
    years = list(range(today.year - YEARS_SHOWN + 1, today.year + 1))[::-1]
    block = 30 + 7 * step + 28          # label + months + grid + spacing
    graph_w, graph_h = 53 * step, len(years) * block - 28
    gx = 40 + art_w + 48
    w = int(gx + graph_w + 40)
    h = int(max(art_h, graph_h) + 80)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{MONO}">',
           f'<rect x=".5" y=".5" width="{w-1}" height="{h-1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>',
           f'<text x="40" y="{(h - art_h) / 2 + art_fs:.1f}" font-size="{art_fs}" fill="{t["art"]}" xml:space="preserve">']
    for i, line in enumerate(art):
        out.append(f'<tspan x="40" dy="{0 if i == 0 else art_lh}">{e(line)}</tspan>')
    out.append("</text>")

    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    y0 = (h - graph_h) / 2 + 12
    for yr in years:
        start = dt.date(yr, 1, 1)
        end = min(dt.date(yr, 12, 31), today)
        days = [start + dt.timedelta(n) for n in range((end - start).days + 1)]
        counts = [contrib.get(d.isoformat(), 0) for d in days]
        lvl = levels(counts)
        out.append(f'<text x="{gx}" y="{y0:.1f}" font-size="13.5" xml:space="preserve"><tspan fill="{t["key"]}" font-weight="bold">{yr}</tspan>'
                   f'<tspan fill="{t["dots"]}"> · </tspan><tspan fill="{t["value"]}">{sum(counts):,} contributions</tspan></text>')
        offset = (start.weekday() + 1) % 7  # Sunday-first rows like GitHub
        for mi, m in enumerate(months):
            col = ((dt.date(yr, mi + 1, 1) - start).days + offset) // 7
            out.append(f'<text x="{gx + col * step:.1f}" y="{y0 + 20:.1f}" font-size="10.5" fill="{t["dots"]}">{m}</text>')
        cy0 = y0 + 28
        rects = []
        for d, c in zip(days, counts):
            col, row = divmod((d - start).days + offset, 7)
            rects.append(f'<rect x="{gx + col * step:.1f}" y="{cy0 + row * step:.1f}" width="{cell}" height="{cell}" rx="2.5" fill="{t["cells"][lvl(c)]}"/>')
        out.append("".join(rects))
        y0 += block
    out.append("</svg>")
    (OUT / f"{theme}.svg").write_text("\n".join(out) + "\n")


def main():
    art = (OUT / "ascii-art.txt").read_text().rstrip("\n").split("\n")
    today = dt.date.today()
    contrib = fetch_contributions(range(today.year - YEARS_SHOWN + 1, today.year + 1))
    for theme in THEMES:
        build(theme, art, contrib, today)
    print("built cards;", sum(contrib.values()), "contributions on record")


if __name__ == "__main__":
    main()
