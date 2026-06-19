# Life Dashboard — Handoff

> Overdrachtsdocument voor de volgende sessie. Bovenaan staat het \*\*oorspronkelijke
> plan (Fase 1)\*\* ongewijzigd; daaronder wat er nu staat, hoe je het draait/deployt,
> en de open punten. Geen secrets in dit bestand (zie `.env`, gitignored).

\---

## TL;DR — status

* **Fase 1 (fundering) is gebouwd én geverifieerd.** Backend (FastAPI), herbouwbare
SQLite-index, ICS- en markdown-parser, vault-writer, OpenRouter-abstractie, Svelte-
frontend, Docker. 10/10 tests groen; end-to-end + visueel gecheckt.
* **We zitten in de phase gate:** Joel test eerst voordat er een nieuwe versie komt. **Bouw geen Fase 2-features zonder expliciet akkoord.**
* **Sinds de bouw aangepast in `.env`:** OpenRouter-key ingevuld (briefings werken nu
echt) en `ICS\_URL` wijst naar Joels echte Google-agenda. Deploy naar de NAS (SSH +
git) is uitgevoerd — repo staat op GitHub, eerste deploy is gedaan.

\---

## HET OORSPRONKELIJKE PLAN (Fase 1) — ongewijzigd

### Doel \& context

Eén selfhosted "life dashboard": één scherm dat data uit Joels leven samenbrengt en
hem informeert wanneer nodig. Draait als webapp op een **Synology NAS (Docker)**,
getoond op een **42" LG OLED via de WebOS-browser** (bediend met de Magic Remote —
gewoon een URL openen). Dezelfde webapp moet óók werken op Mac en telefoon.

Dit is de **fundering**. Klein houden. Joel heeft een sterke neiging om hele systemen
te ontwerpen vóór er iets draait — help dat te weerstaan door je strikt aan de scope
te houden.

### Architectuur-principe (niet onderhandelbaar)

* **Obsidian-markdown = bron van waarheid.** Notities zijn van Joel, blijven
leesbaar/portable.
* **SQLite = herbouwbare index (cache).** Het dashboard en de AI bevragen SQLite,
nooit direct de markdown. De index moet je op elk moment kunnen weggooien en volledig
opnieuw kunnen opbouwen uit de markdown.
* **Schrijven naar de vault is minimaal.** De enige write in Fase 1: één logregel
toevoegen aan de dagnotitie van vandaag. Verder read-only.
* **AI-inferentie via OpenRouter** (API-key uit env var, los van Joels Anthropic-
account). Dunne abstractie zodat de provider later wisselbaar is (bijv. lokaal Qwen).

### Tech stack

* **Backend:** Python, FastAPI. Dun. Endpoints + parser + OpenRouter-client.
* **Index:** SQLite (één bestand, herbouwbaar).
* **Frontend:** Svelte. Bewust licht — moet vloeien op een zwakke TV-GPU met oudere
Chromium (\~87+). **Target ES2018.** Grid/Flexbox/CSS-variabelen. Vermijd container
queries, `:has()`, subgrid en de allernieuwste JS-API's. Grote tap-targets (Magic
Remote-pointer nu, touch later — zelfde code). Periodieke full page reload
(configureerbaar, default elke 3 uur) tegen geheugenlekken.
* **Draaien:** Docker Compose, naast de bestaande NAS-stack. Eén service voor de API,
frontend als statische build geserveerd door de API. Config via env vars.

### Scope Fase 1 — precies dit (één scherm, drie onderdelen)

1. **Agenda (vandaag + deze week).** Ingest van één ICS-bron (`.ics`-bestand in een
vaste vault-map óf een ICS-URL, configureerbaar). Parse events → index. Toon vandaag
prominent, deze week compact eronder. Géén maand/week/dag-toggle. Per event een
dunne AI-briefing: tap event → API stuurt titel/omschrijving/tijd + naïef gematchte
recente logs naar OpenRouter → kort briefing-paragraafje. Het zaadje, niet het
volledige briefing-systeem.
2. **Logveld (oneliners).** Eén tekstinput + verstuurknop. Versturen → append één regel
aan de dagnotitie: `- {tekst} #log/{thema}` (thema via klein dropdownetje, default
`#log/algemeen`). UX-regels (letterlijk): placeholder vooruitkijkend en neutraal
("Wat merk je op? Iets om morgen te proberen?"), nooit "wat ging er mis?"; één regel
is altijd een complete geldige log; geen verplichte vervolgvragen; niets als
score/cijfer/oordeel terug; logs zijn append-only; geen automatische "leg uit
waarom"-ondervraging.
3. **Recente logs.** Lees `#log/\*`-regels uit de index (met datum), toon de laatste \~10
als simpele lijst. Read-only.

### Endpoints (richtlijn)

`GET /agenda/today` · `GET /agenda/{event\_id}/briefing` · `POST /log {text, theme}` ·
`GET /logs/recent` · `POST /index/rebuild`

### NIET bouwen in Fase 1 (bewust uitgesteld)

Geen weer · geen OV/kaart/routeplanning · geen maand/week/dag-toggle · geen rijk
metadata-schema voor afspraaktypes · geen write-back behálve de logregel · geen WebOS
`.ipk`-packaging · geen patroon-detectie / thema-samenvoeging (later, alleen op
expliciet commando) · geen auth/multi-user (draait op LAN/Tailscale).

### Phase gate

Wanneer Fase 1 draait — dashboard opent op `http://nas:PORT`, agenda van vandaag met
briefing per event, logregel die in de dagnotitie belandt, en `POST /index/rebuild`
bouwt de index correct opnieuw op uit de markdown — **stop en laat Joel het grondig testen** vóór er iets bijkomt.

\---

## Beslissingen sinds het plan

* **Nextcloud is van tafel.** Joel stopt met Nextcloud. Het dashboard hing daar nooit
van af: het leest/schrijft een **map met markdown** op `VAULT\_PATH`. Hóe die map
synct (Syncthing / Obsidian Sync / git / NAS-share) is een aparte, nog onbesliste
keuze — buiten scope van het dashboard.
* **Geen vaste vault-layout was er** → simpele defaults gekozen (aanpasbaar; parser is
mild, index herbouwbaar):

  * Dagnotities: `VAULT\_PATH/Daily/YYYY-MM-DD.md`, met `# YYYY-MM-DD` als H1.
  * Logregel `- {tekst} #log/{thema}` wordt **bovenaan** ingevoegd (onder de H1),
nieuwste eerst — Joels keuze.
  * Agenda: `.ics`-bestand(en) in `VAULT\_PATH/Calendar/` **plus** optionele `ICS\_URL`
(beide ondersteund, bestand eerst).
* **Endpoints staan onder `/api`** (+ `/api/config`, `/api/health`) zodat de frontend
same-origin geserveerd kan worden. Mapt 1-op-1 op het richtlijn-lijstje hierboven.
* **Deploy-flow = SSH + git** (Joels keuze). De NAS (DS1525+, Container Manager) bouwt
de image zelf; geen Docker op de pc en geen registry nodig.

\---

## Wat er nu staat (geïmplementeerd \& geverifieerd)

* **Backend** (`backend/app/`): `config.py` (env), `clock.py` (tz), `db.py` (SQLite-
schema, herbouwbaar), `parser.py` (markdown→logs, ICS→events met recurrence-expansie,
volledige rebuild), `vault.py` (de ene write: top-of-file append + create-if-missing),
`llm.py` (OpenRouter, gracieus zonder key), `briefing.py` (naïeve match + cache),
`agenda.py` (vandaag + deze week, recente logs), `main.py` (endpoints + static
serving), `reindex.py` (CLI: gooi index-bestand weg en herbouw).
* **Frontend** (`frontend/src/lib/`): `Agenda.svelte`, `LogField.svelte`,
`RecentLogs.svelte`, `api.js`. ES2018-build, donker OLED-thema, grote targets,
periodieke reload. Responsive (TV + telefoon) geverifieerd.
* **Tests:** `backend/tests/test\_parser.py` — 10/10 groen (logparser, frontmatter-skip,
vault-write create + top-insert, herbouwbare/idempotente rebuild, recente-logs-
volgorde, today-events).
* **Docker:** multi-stage `Dockerfile` (Node bouwt frontend → Python serveert API +
static), `docker-compose.yml` (vault read-write mount, index in apart volume).
* **Bewijs herbouwbaarheid:** een gelogde regel belandt in de markdown en overleeft
`POST /api/index/rebuild` (die de index wéggooit en puur uit markdown herbouwt).

### Belangrijkste env vars (zie `.env.example` voor de volledige lijst)

`VAULT\_PATH`, `DAILY\_SUBDIR`, `ICS\_FILE`, `ICS\_URL`, `INDEX\_DB`,
`AUTO\_REBUILD\_ON\_START`, `DASHBOARD\_TZ`, `OPENROUTER\_API\_KEY`, `OPENROUTER\_MODEL`,
`PORT`, `RELOAD\_INTERVAL\_HOURS`, `LOG\_THEMES`, `DEFAULT\_THEME`, `RECENT\_LOGS\_COUNT`,
`CORS\_ORIGINS`, `STATIC\_DIR`.

> \*\*Secrets staan in `.env` (gitignored), niet hier.\*\* Op de dev-machine zijn nu
> ingevuld: `OPENROUTER\_API\_KEY` (→ briefings werken echt), `OPENROUTER\_MODEL`
> (`anthropic/claude-3.5-haiku`) en `ICS\_URL` (Joels privé Google-agenda).

\---

## Hoe draaien

**Lokaal (dev, Windows):**

```powershell
py -3.12 -m venv backend\\.venv
backend\\.venv\\Scripts\\python -m pip install -r backend\\requirements.txt
npm --prefix frontend install ; npm --prefix frontend run build
backend\\.venv\\Scripts\\python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8765
```

→ `http://localhost:8765`. Tests: `$env:PYTHONPATH="backend"; backend\\.venv\\Scripts\\python -m pytest backend\\tests -q`.

> Docker bouwt niet op de Windows-pc (geen Docker) — dat gebeurt op de NAS.

**NAS (DS1525+, Container Manager — SSH + git):** zie `README.md` en `deploy.sh`.
Kort: één keer clonen via een `alpine/git`-container in `/volume1/docker/life-dashboard`,
`.env` aanmaken met NAS-paden (`VAULT\_PATH=/vault`, `ICS\_FILE=/vault/Calendar/...`,
`HOST\_PORT=8765`), dan `sudo docker compose up -d --build`. Elke nieuwe versie:
`sudo sh deploy.sh` (pull via git-container + rebuild).

\---

## Open punten / logische volgende fase (NIET bouwen zonder akkoord)

1. **Pushen + eerste NAS-deploy.** ✅ Gedaan — alles is gecommit, repo staat op
GitHub (`ilovemicrowaves/life-dashboard`), eerste NAS-deploy is uitgevoerd.
2. **Periodieke index-rebuild (scheduler/cron).** Nu wordt de agenda bij een rebuild in
de index gezet over een venster `\[vandaag-7, vandaag+31]`; er is **geen auto-rebuild**.
"Vandaag" blijft dagenlang kloppen, maar nieuwe/gewijzigde agenda-items verschijnen
pas na een rebuild (knop "Index herbouwen" of `POST /api/index/rebuild`). Een
nachtelijke rebuild lost dit op.
3. **Briefings live afstellen.** De key staat nu in `.env`, dus de per-event briefing
geeft echte AI-tekst i.p.v. de placeholder. Prompt/match aanscherpen als het zaadje
bevalt.
4. **Verder uitgesteld (uit "NIET bouwen"):** weer, OV/kaart, maand/week/dag-toggle,
patroon-detectie (alleen op expliciet commando), etc.

\---

## Werkrelatie (belangrijk)

Joel wil dat ik **scope-discipline** bewaak en zijn neiging tot over-engineering lichtelijk
tegenga. Bouw exact de afgesproken scope, stop bij de phase gate, en benoem de volgende
fase zonder die te bouwen. Sensible defaults + "zeg het als je X wil" boven preventief
toevoegen.

## Gerelateerd werk (deze sessie, ander project)

Joels Obsidian-vault "Life" (`C:\\Users\\Admin\\Desktop\\Obsidian\\Life`) is deze sessie
radicaal vereenvoudigd (van een door-AI-onderhouden wiki naar platte, eerste-persoons
notities). Details staan in het persoonlijke geheugen van Claude Code (`project-life-vault`), niet in
deze repo. Zelfde filosofie als het dashboard: markdown = bron, structuur eruit
berekend, AI op afroep.

## Sleutelbestanden

`README.md` (run/deploy) · `.env.example` (alle config) · `docker-compose.yml` +
`Dockerfile` · `deploy.sh` (NAS-update) · `backend/app/main.py` (endpoints) ·
`backend/app/parser.py` (index-rebuild) · `backend/tests/test\_parser.py`.

