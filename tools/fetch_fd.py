#!/usr/bin/env python3
"""Liest Ergebnisse und Tabelle der Gruppen JH 05 (Blau) / JH 04 (Weiß) von fussball.de
und schreibt sie in index.html (TABLES + Ergebnisse der eigenen Spiele in MATCHES).

Aufruf:  python3 tools/fetch_fd.py [n4] [n5]      (ohne Argument: beide)
Test:    FD_CACHE=/pfad python3 tools/fetch_fd.py  (liest <cache>/<datum>-<team>.html und Fonts <cache>/<id>_font)

fussball.de verschleiert Ziffern mit einer Web-Schrift je Seitenaufruf; die Schrift wird
mitgeladen und über die Glyphen-Namen (zero, one, …) zurückübersetzt.
"""
import datetime as dt, html, io, os, re, sys, urllib.request
from zoneinfo import ZoneInfo
from fontTools.ttLib import TTFont
from fontTools.agl import toUnicode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
CACHE = os.environ.get("FD_CACHE")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
BASE = "https://www.fussball.de/spieltag/{slug}/-/spieldatum/{d}/staffel/{st}"
GROUPS = {
    "n4": dict(group="JH 05", own="Niendorf 4.D-Jun. (A2)", own_tbl="NTSV 7. D Blau",
               slug="jh-05--d-junioren-u13-kreisebene-hamburg-d-junioren-hallen-kreisturnier-d-junioren-saison2627-hamburg",
               st="0327PBA1RK00000BVS5489BUVUFHD2VV-G"),
    "n5": dict(group="JH 04", own="Niendorf 10.D-Jun. (A5)", own_tbl="NTSV 7. D Weiß",
               slug="jh-04--d-junioren-u13-kreisebene-hamburg-d-junioren-hallen-kreisturnier-d-junioren-saison2627-hamburg",
               st="0327PBA1J400000BVS5489BUVUFHD2VV-G"),
}
ALIAS = [("Alstertal-Langenhorn", "SCALA"), ("Eintracht Norderstedt", "Eintr. Norderstedt"), ("SV Groß Borstel", "SV Gr. Borstel"), ("Niendorf ", "NTSV ")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


_fonts = {}
def fontmap(fid):
    if fid not in _fonts:
        data = open(os.path.join(CACHE, fid + "_font"), "rb").read() if CACHE else \
            get(f"https://www.fussball.de/export.fontface/-/format/ttf/id/{fid}/type/font")
        cm = TTFont(io.BytesIO(data)).getBestCmap()
        _fonts[fid] = {k: (" " if v == "space" else toUnicode(v)) for k, v in cm.items()}
    return _fonts[fid]


def deobf(s):
    return re.sub(r'data-obfuscation="(\w+)"([^>]*>)([^<]*)',
                  lambda m: m.group(2) + "".join(fontmap(m.group(1)).get(ord(c), c) for c in html.unescape(m.group(3))), s)


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()


def text(fragment):
    return re.sub(r"\s+", " ", clean(re.sub(r"<[^>]+>", " ", fragment))).strip()


def page(tid, d):
    g = GROUPS[tid]
    raw = open(os.path.join(CACHE, f"{d}-{tid}.html"), encoding="utf-8").read() if CACHE else \
        get(BASE.format(slug=g["slug"], d=d, st=g["st"])).decode("utf-8")
    return deobf(raw)


def parse(s, d):
    """Spiele des Datums d und Tabelle einer Spieltagsseite."""
    tstart = s.find('class="table table-striped table-full-width"')
    mpart, tpart = s[:tstart], s[tstart:]
    want = dt.date.fromisoformat(d).strftime("%d.%m.%Y")
    matches, cur = [], None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", mpart, re.S):
        clubs = re.findall(r'class="club-name">\s*(.*?)\s*</div>', r, re.S)
        if len(clubs) < 2:
            m = re.search(r"\b(\d\d\.\d\d\.\d{4})\b", text(r))
            if m and "column-date" not in r: cur = m.group(1)
            continue
        if cur != want: continue
        sc = re.search(r'class="score-left">([^<]*)<.*?class="score-right">([^<]*)<', r, re.S)
        tm = re.search(r"(\d\d:\d\d)\s*$", text(re.search(r'class="column-date">(.*?)</td>', r, re.S).group(1)))
        h, a = (clean(c) for c in clubs[:2])
        score = None
        if sc and sc.group(1).strip().isdigit() and sc.group(2).strip().isdigit():
            score = f"{int(sc.group(1))}:{int(sc.group(2))}"
        matches.append(dict(t=tm.group(1) if tm else None, h=h, a=a, score=score))
    rows = []
    body = tpart[:tpart.find("</table>")]
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
        tds = [text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        club = re.search(r'class="club-name">\s*(.*?)\s*</div>', r, re.S)
        if not club or len(tds) < 8: continue
        nums = [x for x in tds if x]
        # Platz, (Logo/Name), Sp, G, U, V, Tore, Diff, Pkt
        tail = nums[-7:]
        pl = re.match(r"(\d+)", nums[0]) if nums else None
        if not pl or len(tail) < 7: continue
        rows.append([int(pl.group(1)), clean(club.group(1)), *map(int, tail[:4]),
                     tail[4].replace(" ", ""), int(tail[5]), int(tail[6])])
    return matches, rows


def tblname(n, g):
    if n == g["own"]: return g["own_tbl"]
    n = re.sub(r"\.D-Jun\.?", ".D", n)
    for a, b in ALIAS:
        if n.startswith(a): n = b + n[len(a):]
    return n


def shortname(n, g):
    return "NTSV 7. D" if n == g["own"] else re.sub(r"\s*\([^)]*\)$", "", tblname(n, g))


def js_rows(rows):
    return ",\n".join(f'      [{r[0]},"{r[1]}",{r[2]},{r[3]},{r[4]},{r[5]},"{r[6]}",{r[7]},{r[8]}]' for r in rows)


def main(tids):
    src = open(INDEX, encoding="utf-8").read()
    today = dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    out, log = src, []
    for tid in tids:
        g = GROUPS[tid]
        days = sorted(set(re.findall(r'\{ d:"(\d{4}-\d\d-\d\d)"[^\n]*teams:\["' + tid + r'"\]', src)))
        # Wochenenden der Spieltage (Sa+So); aktueller = letzter, dessen Samstag erreicht ist
        weekends = []
        for d in days:
            x = dt.date.fromisoformat(d); sat = x - dt.timedelta(days=(x.weekday() - 5) % 7)
            weekends.append((sat, sat + dt.timedelta(days=1), x))
        idx = max([i for i, w in enumerate(weekends) if w[0] <= today], default=0)
        res = {}
        def load(i):
            if i in res: return res[i]
            ms, table = [], None
            for d in (weekends[i][0], weekends[i][1]):
                if d > today and not CACHE: continue
                try: m, t = parse(page(tid, d.isoformat()), d.isoformat())
                except FileNotFoundError: continue
                ms += [dict(mm, d=d.isoformat()) for mm in m]
                if t: table = t
            res[i] = (ms, table); return res[i]
        ms, table = load(idx)
        n = idx + 1
        played = sum(1 for m in ms if m["score"])
        if played == 0 and idx > 0:          # neuer Spieltag noch ohne Ergebnis → vorigen zeigen
            idx -= 1; n = idx + 1; ms, table2 = load(idx); table = table or table2
            played = sum(1 for m in ms if m["score"])
        total = len(ms)
        if not table:
            log.append(f"{g['group']}: keine Tabelle gefunden"); continue
        rows = [[r[0], tblname(r[1], g)] + r[2:] for r in table]
        live = f"played:{played}, total:{total}" if total and played < total else "played:null, total:null"
        stand = today.strftime("%d.%m.%Y")
        pat = re.compile(r'(\{ group:"' + re.escape(g["group"]) + r'"[^\n]*?stand:")[^"]*(", spieltag:)[^,]*, played:[^,]*, total:[^,]*,(\s*rows:\[\n).*?(\n    \]\})', re.S)
        new = pat.sub(lambda m: m.group(1) + stand + m.group(2) + f"{n}, {live}," + m.group(3) + js_rows(rows) + m.group(4), out, count=1)
        # eigene Spiele: Ergebnisse übernehmen
        for m in ms:
            if not m["score"] or g["own"] not in (m["h"], m["a"]): continue
            line = re.compile(r'(\{ d:"' + m["d"] + r'", t:"' + (m["t"] or "") + r'", nr:"\d+", h:"' + re.escape(shortname(m["h"], g)) +
                              r'", a:"' + re.escape(shortname(m["a"], g)) + r'", teams:\["' + tid + r'"\], score:)(null|"[^"]*")(, fd:true)?')
            new = line.sub(lambda x: x.group(1) + f'"{m["score"]}", fd:true', new)   # fd: von fussball.de, nicht mehr änderbar
        log.append(f"{g['group']}: {n}. Spieltag, {played}/{total} Spiele, {len(rows)} Teams")
        out = new
    if out != src:
        body = lambda s: re.sub(r'stand:"[^"]*"', "", s)
        if body(out) != body(src):           # nur Datum geändert → nicht speichern
            out = re.sub(r'const DATA_STAND = "[^"]*";', f'const DATA_STAND = "{today.strftime("%d.%m.%Y")}";', out)
            open(INDEX, "w", encoding="utf-8").write(out)
            log.append("index.html aktualisiert")
        else: log.append("keine Änderung")
    else: log.append("keine Änderung")
    print("\n".join(log))


def in_window():
    """Zeitgesteuerte Läufe nur an Spieltags-Wochenenden (Sa, So) und am Montag danach."""
    src = open(INDEX, encoding="utf-8").read()
    today = dt.datetime.now(ZoneInfo("Europe/Berlin")).date()
    for d in set(re.findall(r'\{ d:"(\d{4}-\d\d-\d\d)"', src)):
        x = dt.date.fromisoformat(d); sat = x - dt.timedelta(days=(x.weekday() - 5) % 7)
        if sat <= today <= sat + dt.timedelta(days=2): return True
    return False


if __name__ == "__main__":
    if "--scheduled" in sys.argv and not in_window():
        print("kein Spieltags-Wochenende – nichts zu tun"); sys.exit(0)
    main([a for a in sys.argv[1:] if a in GROUPS] or ["n4", "n5"])
