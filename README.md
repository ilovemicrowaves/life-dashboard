# Life Dashboard — Fase 1 (fundering)

Eén selfhosted scherm dat data uit je leven samenbrengt: je agenda van vandaag,
een logveld voor oneliners, en je recente logs. Draait als webapp (Docker) op de
NAS, getoond op de 42" LG OLED via de WebOS-browser, en werkt ook gewoon op Mac
en telefoon.

Dit is bewust de *fundering*. Klein, maar volledig werkend en herbouwbaar.

## Architectuur-principe (niet onderhandelbaar)

- **Markdown = bron van waarheid.** Je notities zijn een **map met markdown**.
  Het dashboard leest/schrijft alleen die map (`VAULT_PATH`). *Hoe* die map gesynct
  wordt (Syncthing / Obsidian Sync / git / NAS-share) staat hier helemaal los van —
  geen Nextcloud nodig.
- **SQLite = herbouwbare cache.** Het dashboard en de AI bevragen SQLite, nooit
  direct de markdown. Je mag het indexbestand altijd weggooien: `POST /api/index/rebuild`
  (of `python -m app.reindex`) bouwt het volledig opnieuw op uit de markdown.
- **Schrijven is minimaal.** De énige schrijfactie is: één logregel toevoegen aan
  de dagnotitie van vandaag. Verder lezen we read-only.
- **AI via OpenRouter, achter een dunne abstractie** (`app/llm.py`). Later wisselbaar
  naar bijv. lokaal Qwen zonder de rest aan te raken.

## Projectstructuur

```
Dashboard/
├─ backend/                 FastAPI + parser + index + OpenRouter-client
│  ├─ app/
│  │  ├─ config.py          alle env-config
│  │  ├─ clock.py           tijd/tz-helpers
│  │  ├─ db.py              SQLite-schema + connectie (herbouwbaar)
│  │  ├─ parser.py          markdown→logs, ICS→events, volledige rebuild
│  │  ├─ vault.py           de ene schrijfactie: logregel-append
│  │  ├─ llm.py             OpenRouter-abstractie
│  │  ├─ briefing.py        naïeve match + AI-briefing per event
│  │  ├─ agenda.py          queries: vandaag + deze week, recente logs
│  │  ├─ main.py            FastAPI-app + endpoints + static serving
│  │  └─ reindex.py         CLI: gooi index weg en herbouw
│  └─ tests/                kerntests (parser, write, rebuild)
├─ frontend/                Svelte (ES2018, licht, TV-vriendelijk)
│  └─ src/lib/              Agenda, LogField, RecentLogs, api
├─ sample-vault/            voorbeeld-vault om tegen te ontwikkelen
│  ├─ Daily/                YYYY-MM-DD.md met #log/-regels
│  └─ Calendar/life.ics     voorbeeldagenda (incl. herhaling)
├─ Dockerfile               multi-stage: bouw frontend + draai API
├─ docker-compose.yml       één service, vault-mount + index-volume
└─ .env.example             alle instellingen met uitleg
```

## Snel starten — lokaal (dev)

Vereist: Python 3.12 en Node 20+. Kopieer eerst `.env.example` naar `.env`
(de defaults wijzen al naar `sample-vault/`, dus het werkt meteen).

**Backend** (eenmalig venv + deps):

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

Start de API (serveert ook de gebouwde frontend als die er is):

```powershell
backend\.venv\Scripts\python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8765
```

**Frontend** — voor productie-achtig draaien bouw je 'm één keer; de API serveert
`frontend/dist` dan op dezelfde poort:

```powershell
npm --prefix frontend install
npm --prefix frontend run build
```

Open daarna **http://localhost:8765**.

> Voor frontend-ontwikkeling met hot reload: `npm --prefix frontend run dev`
> (draait op :5173 en proxyt `/api` naar de backend op :8765).

## Draaien op de NAS (Docker Compose)

```bash
# in een .env naast docker-compose.yml:
#   VAULT_HOST_PATH=/volume1/pad/naar/jouw/vault   # read-write
#   HOST_PORT=8765
#   OPENROUTER_API_KEY=sk-or-...                    # optioneel
#   ICS_FILE=/vault/Calendar/life.ics              # of ICS_URL=...
docker compose up -d --build
```

Open **http://nas:8765**. De vault wordt op `/vault` gemount (read-write voor de
logregel-append); de index leeft in een apart Docker-volume (`/data`) — buiten je
vault, want het is wegwerpbaar.

## Configuratie

Alles via env vars — zie **`.env.example`** voor de volledige lijst met uitleg.
De belangrijkste:

| Variabele | Doel |
|---|---|
| `VAULT_PATH` | map met je markdown (bron van waarheid) |
| `DAILY_SUBDIR` | submap met dagnotities (`Daily`) |
| `ICS_FILE` / `ICS_URL` | agendabron: bestand in de vault en/of een live URL |
| `INDEX_DB` | pad naar het SQLite-indexbestand (wegwerpbaar) |
| `DASHBOARD_TZ` | tijdzone (`Europe/Amsterdam`) |
| `OPENROUTER_API_KEY` | leeg = draait zonder AI (placeholder-briefing) |
| `OPENROUTER_MODEL` | model-id bij OpenRouter (wisselbaar) |
| `RELOAD_INTERVAL_HOURS` | periodieke full page-reload (default 3) |
| `LOG_THEMES` / `DEFAULT_THEME` | thema's voor het log-dropdownetje |

## De dagnotitie-conventie

Voorlopige, simpele default (pas 'm aan wanneer je wil — de parser is mild en je
herbouwt gewoon):

- Dagnotities: `VAULT_PATH/Daily/YYYY-MM-DD.md`, met `# YYYY-MM-DD` als titel.
- Een log is elke regel met een `#log/<thema>`-tag. Nieuwe logs komen **bovenaan**
  (onder de titel), nieuwste eerst: `- {tekst} #log/{thema}`.
- Ontbreekt de dagnotitie van vandaag, dan maakt de app 'm minimaal aan.

## API-endpoints

| Methode + pad | Wat |
|---|---|
| `GET /api/agenda/today` | events vandaag (prominent) + de rest van deze week |
| `GET /api/agenda/{id}/briefing` | dunne AI-briefing voor één event (gecached) |
| `POST /api/log` | `{ text, theme }` → append aan dagnotitie + index bijwerken |
| `GET /api/logs/recent` | laatste N logregels |
| `POST /api/index/rebuild` | gooi de index weg en herbouw uit de vault |
| `GET /api/config` | UI-config (reload-interval, thema's, …) |

## De index is wegwerpbaar (bewijs)

```powershell
# Via de API (of de knop 'Index herbouwen' rechtsonder):
curl -X POST http://localhost:8765/api/index/rebuild

# Of fysiek het bestand weggooien en opnieuw opbouwen uit de markdown:
$env:PYTHONPATH = "backend"; backend\.venv\Scripts\python -m app.reindex
```

Tests draaien:

```powershell
$env:PYTHONPATH = "backend"; backend\.venv\Scripts\python -m pytest backend\tests -q
```

## Wat (nog) niet — bewust uitgesteld

Geen weer, geen OV/kaart, geen maand/week/dag-toggle, geen rijk metadata-schema,
geen write-back behalve de logregel, geen WebOS-packaging, geen patroon-detectie of
thema-samenvoeging, geen auth/multi-user.

**Logische volgende fase (nog niet bouwen):** een periodieke index-rebuild
(scheduler/cron) zodat de agenda vanzelf vers blijft, en een echte
OpenRouter-key invullen om de briefings te activeren.
