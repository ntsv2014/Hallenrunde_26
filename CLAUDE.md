# NTSV 7. D · Hallenmeisterschaft 2026/27

Öffentliche Übersicht (GitHub Pages): https://ntsv2014.github.io/Hallenrunde_26/

- Alle Daten stehen in `index.html` (Konstanten `MATCHES`, `TABLES`, `SPIELTAGE`, `TURNIERBEGINN`, `DATA_STAND`).
- **Nach jeder Datenänderung** die Kalenderdateien neu erzeugen und mit committen:
  `node tools/mkics.js` (schreibt `cal/*.ics`).
- Zweitfassung auf claude.ai (Artifact-Slug `9a1dfc62-ddfb-4b81-8f0d-bcbb4ffa609f`, öffentlich geteilt) mit denselben Datenänderungen per `edit_version` aktuell halten.
- Keine personenbezogenen Daten (Spielernamen, Zu-/Absagen) veröffentlichen.
- „Alstertal-Langenhorn“ immer als „SCALA“, „Eintracht“ als „Eintr.“.
- Tabellen/Ergebnisse kommen automatisch per GitHub-Workflow `fussball.de abrufen` (`tools/fetch_fd.py`, Start über die Buttons auf „Aktuell“ mit Schlüssel). Tabellenkopf: `spieltag`, `played`/`total` (Live-Stand, null = komplett). „SV Groß Borstel“ als „SV Gr. Borstel“.
