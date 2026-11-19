#!/usr/bin/env python3
"""Täglicher Abgleich der Ansetzungen (Spielplan der eigenen Teams) mit fussball.de.

- liest den Teamspielplan (Datum, Uhrzeit, Spielnummer, Gegner) beider Teams,
- liest für jeden Turniertag einmal die Spielstätte aus der Einzelansicht eines Spiels,
- übernimmt neue bzw. geänderte Spiele in MATCHES (index.html) und entfernt passende Platzhalter (d:null),
- meldet, was nur von Hand ergänzt werden kann (neuer Turniertag ohne Treffzeit/Ende,
  abweichende Halle) in checks/ansetzungen.md. Bereits gemeldete Punkte werden nicht erneut gemeldet
  (Zustand in checks/ansetzungen-state.json).

Aufruf: python3 tools/ansetzungen.py      Test: FD_CACHE=/pfad (plan-n4.html, plan-n5.html, spiel-<nr>.html)
"""
import datetime as dt, html, json, os, re, sys, urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fd import GROUPS, shortname, clean, UA  # Namensregeln wie beim Tabellenabruf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
REPORT = os.path.join(ROOT, "checks", "ansetzungen.md")
STATE = os.path.join(ROOT, "checks", "ansetzungen-state.json")
CACHE = os.environ.get("FD_CACHE")
TEAMS = {"n4": dict(id="02JAE3FD60000000VS5489B2VV3G3E4A", prefix="174405", name="Blau"),
         "n5": dict(id="02UCRRKAL8000000VS5489BRVTRSB17S", prefix="174404", name="Weiß")}
PLAN = ("https://www.fussball.de/ajax.team.matchplan/-/mime-type/HTML/mode/PAGE/show-filter/false/max/99"
        "/team-id/{id}/datum-von/2026-08-01/datum-bis/2027-06-30")


def get(url, cache_name):
    if CACHE:
        p = os.path.join(CACHE, cache_name)
        return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "de-DE,de"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def plan(tid):
    """Spiele der eigenen Gruppe aus dem Teamspielplan."""
    t = TEAMS[tid]; g = GROUPS[tid]
    s = get(PLAN.format(id=t["id"]), f"plan-{tid}.html")
    out, cur = [], None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        txt = clean(re.sub(r"<[^>]+>", " ", r))
        m = re.search(r"(\d\d)\.(\d\d)\.(\d{4}) - (\*\*|\d\d:\d\d) Uhr", txt)
        if m and 'colspan="6"' in r:
            d = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            cur = dict(d=d, t=None if m.group(4) == "**" else m.group(4)); continue
        m = re.search(r"HM \| (\d+)", txt)
        if m and cur is not None:
            cur["nr"] = m.group(1); continue
        clubs = re.findall(r'class="club-name">\s*(.*?)\s*</div>', r, re.S)
        if len(clubs) >= 2 and cur and cur.get("nr", "").startswith(t["prefix"]):
            url = re.search(r'href="(https://www\.fussball\.de/spiel/[^"]+)"', r)
            h, a = clean(clubs[0]), clean(clubs[1])
            if g["own"] in (h, a):
                out.append(dict(nr=cur["nr"], d=cur["d"] if cur["t"] else None, t=cur["t"],
                                h=shortname(h, g), a=shortname(a, g), url=url.group(1) if url else None))
            cur = None
    return out


def venue(m):
    s = get(m["url"], f"spiel-{m['nr']}.html") if m.get("url") else ""
    v = re.search(r'class="location"[^>]*>\s*(.*?)\s*<span', s, re.S)
    if not v: return None
    parts = [p.strip() for p in clean(v.group(1)).split(",") if p.strip()]
    if parts and parts[0].lower() == "halle": parts = parts[1:]
    if len(parts) < 3: return dict(halle=", ".join(parts), adresse="")
    return dict(halle=", ".join(parts[:-2]), adresse=", ".join(parts[-2:]))


norm = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("ß", "ss").replace("str.", "strasse").replace("straße", "strasse"))
fmt = lambda d: dt.date.fromisoformat(d).strftime("%d.%m.")


def main():
    src = open(INDEX, encoding="utf-8").read()
    out = src
    state = json.load(open(STATE)) if os.path.exists(STATE) else {"gemeldet": []}
    applied, todo = [], []
    line_re = lambda nr: re.compile(r'  \{ d:(?:"[^"]*"|null), t:(?:"[^"]*"|null),(?: grp:\d+,)?(?: hyp:true,)? nr:"' + nr + r'", h:"([^"]*)", a:"([^"]*)", teams:\["(n[45])"\], (score:[^\n]*)\},?\n')
    for tid, t in TEAMS.items():
        try: ms = plan(tid)
        except Exception as e:
            todo.append(f"{t['name']}: Spielplan nicht lesbar ({e})"); continue
        seen_days = {}
        for m in ms:
            if not m["d"]: continue
            lr = line_re(m["nr"]); old = lr.search(out)
            new_line = f'  {{ d:"{m["d"]}", t:"{m["t"]}", nr:"{m["nr"]}", h:"{m["h"]}", a:"{m["a"]}", teams:["{tid}"], '
            if old:
                cur = re.search(r'd:"([^"]*)", t:"([^"]*)"', old.group(0))
                if not cur or (cur.group(1), cur.group(2), old.group(1), old.group(2)) != (m["d"], m["t"], m["h"], m["a"]):
                    end = "},\n" if old.group(0).endswith("},\n") else "}\n"
                    out = out.replace(old.group(0), new_line + old.group(4) + end)
                    applied.append(f"{t['name']}: Spiel {m['h']} – {m['a']} jetzt {fmt(m['d'])} {m['t']} Uhr")
            else:
                # Platzhalter (d:null) mit demselben Gegner entfernen
                opp = m["a"] if m["h"] == "NTSV 7. D" else m["h"]
                ph = re.compile(r'  \{ d:null, t:null,[^\n]*?h:"(?:NTSV 7\. D|' + re.escape(opp) + r')", a:"(?:NTSV 7\. D|' + re.escape(opp) + r')", teams:\["' + tid + r'"\][^\n]*\n')
                out = ph.sub("", out, count=1)
                anchor = "  // ---- 7. D Blau (JH 05) – Gegner fest"
                out = out.replace(anchor, new_line + "score:null },\n" + anchor, 1)
                applied.append(f"{t['name']}: neu angesetzt {fmt(m['d'])} {m['t']} Uhr {m['h']} – {m['a']}")
            seen_days.setdefault(m["d"], m)
        # Spielstätte je Turniertag
        for d, m in seen_days.items():
            if d < dt.date.today().isoformat(): continue
            v = venue(m)
            sp = re.search(r'"' + d + r'": \{[^\n]*?halle:"([^"]*)", adresse:"([^"]*)"', out)
            if not sp:
                todo.append(f"{t['name']}, {fmt(d)}: neuer Turniertag" + (f" ({v['halle']}, {v['adresse']})" if v else "")
                            + " – Treffzeit, Ende und Halle bitte aus SpielerPlus nachtragen")
            elif v and v["adresse"] and norm(v["adresse"]) != norm(sp.group(2)):
                todo.append(f"{t['name']}, {fmt(d)}: Halle laut fussball.de „{v['halle']}, {v['adresse']}“ – auf der Seite steht „{sp.group(1)}, {sp.group(2)}“")
    neu = [x for x in todo if x not in state["gemeldet"]]
    now = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    if out != src:
        out = re.sub(r'const DATA_STAND = "[^"]*";', f'const DATA_STAND = "{now.strftime("%d.%m.%Y")}";', out)
        open(INDEX, "w", encoding="utf-8").write(out)
    if applied or neu:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8") as f:
            f.write(f"Stand: {now.strftime('%Y-%m-%d %H:%M')}\n\n")
            if applied: f.write("## Übernommen\n" + "".join(f"- {x}\n" for x in applied) + "\n")
            if neu: f.write("## Bitte prüfen\n" + "".join(f"- {x}\n" for x in neu) + "\n")
        state["gemeldet"] = sorted(set(state["gemeldet"]) | set(neu))
        json.dump(state, open(STATE, "w"), ensure_ascii=False, indent=1)
    print("\n".join(applied + neu) or "keine neuen Ansetzungen")


if __name__ == "__main__":
    main()
