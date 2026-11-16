/* Erzeugt die Kalenderdateien (cal/*.ics) aus den Daten in index.html.
   Aufruf im Repository-Ordner:  node tools/mkics.js
   - cal/blau-JJJJ-MM-TT.ics / cal/weiss-JJJJ-MM-TT.ics : einzelner Spieltag
   - cal/blau.ics / cal/weiss.ics                       : alle Spieltage (abonnierbar)  */
const fs = require("fs"), vm = require("vm"), path = require("path");
const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const a = html.indexOf("const PAGES_URL"), b = html.indexOf("const ICON_TREFFEN");
if (a < 0 || b < 0) throw new Error("Datenbereich in index.html nicht gefunden");
const ctx = {};
vm.runInNewContext(html.slice(a, b) + "\n;this.D={PAGES_URL,TEAMS,MATCHES,TURNIERBEGINN,SPIELTAGE};", ctx);
const { PAGES_URL, TEAMS, MATCHES, TURNIERBEGINN, SPIELTAGE } = ctx.D;
const WORD = { n4: "blau", n5: "weiss" }, LABEL = { n4: "🔵 BLAU", n5: "⚪ WEISS" };
const esc = s => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
const fold = line => { const out = []; let cur = ""; for (const ch of line) { const lim = out.length ? 74 : 75;
  if (Buffer.byteLength(cur + ch) > lim) { out.push(cur); cur = ""; } cur += ch; } out.push(cur); return out.join("\r\n "); };
const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
const VTZ = ["BEGIN:VTIMEZONE","TZID:Europe/Berlin","BEGIN:DAYLIGHT","TZOFFSETFROM:+0100","TZOFFSETTO:+0200","TZNAME:CEST",
  "DTSTART:19700329T020000","RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU","END:DAYLIGHT","BEGIN:STANDARD","TZOFFSETFROM:+0200",
  "TZOFFSETTO:+0100","TZNAME:CET","DTSTART:19701025T030000","RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU","END:STANDARD","END:VTIMEZONE"];
const cal = (name, events) => ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//NTSV 7. D//Hallenturnier//DE","CALSCALE:GREGORIAN",
  "METHOD:PUBLISH", "X-WR-CALNAME:" + esc(name), "X-WR-TIMEZONE:Europe/Berlin", "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
  ...VTZ, ...events.flat(), "END:VCALENDAR"].map(fold).join("\r\n") + "\r\n";
const per = { n4: [], n5: [] };
fs.readdirSync(path.join(root, "cal")).filter(f => f.endsWith(".ics")).forEach(f => fs.unlinkSync(path.join(root, "cal", f)));
for (const [d, sp] of Object.entries(SPIELTAGE).sort()) {
  for (const team of ["n4", "n5"]) {
    const games = MATCHES.filter(m => m.d === d && m.teams.includes(team)).sort((x, y) => x.t.localeCompare(y.t));
    if (!games.length) continue;
    const ymd = d.replace(/-/g, ""), hm = t => t.replace(":", "") + "00";
    const days = [...new Set(MATCHES.filter(m => m.d && m.teams.includes(team)).map(m => m.d))].sort();
    const nr = days.indexOf(d) + 1;
    const desc = `${nr}. Spieltag HFV U13 Hallenmeisterschaft\nTreff: ${sp.treffen} Uhr\nTurnierbeginn: ${TURNIERBEGINN[d] || games[0].t} Uhr\nTurnierende: ${sp.ende} Uhr`;
    const ev = ["BEGIN:VEVENT", `UID:ntsv7d-${team}-${ymd}@ntsv2014.github.io`, `DTSTAMP:${stamp}`,
      `DTSTART;TZID=Europe/Berlin:${ymd}T${hm(sp.treffen)}`, `DTEND;TZID=Europe/Berlin:${ymd}T${hm(sp.ende)}`,
      "SUMMARY:" + esc(`NTSV 7. D ${team === "n4" ? "Blau" : "Weiß"} Hallenturnier`),
      "LOCATION:" + esc(`${sp.halle}, ${sp.adresse}`), "DESCRIPTION:" + esc(desc),
      "BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:" + esc(`Treffen ${sp.treffen} Uhr – ${sp.halle}`), "TRIGGER:-PT30M", "END:VALARM",
      "END:VEVENT"];
    per[team].push(ev);
    fs.writeFileSync(path.join(root, "cal", `${WORD[team]}-${d}.ics`), cal(`NTSV 7. D ${team === "n4" ? "Blau" : "Weiß"}`, [ev]));
  }
}
for (const team of ["n4", "n5"])
  fs.writeFileSync(path.join(root, "cal", `${WORD[team]}.ics`), cal(`NTSV 7. D ${team === "n4" ? "Blau" : "Weiß"} – Hallenturniere`, per[team]));
console.log(fs.readdirSync(path.join(root, "cal")).join("\n"));
