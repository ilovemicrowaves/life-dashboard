"""Kerntests: logparser, de ene schrijfactie, en de herbouwbare index."""

from __future__ import annotations

from datetime import date

from app import clock, db, parser, vault
from app.agenda import get_recent_logs, get_today_and_week
from app.config import Settings


# --------------------------------------------------------------------------
# Logparser
# --------------------------------------------------------------------------

def test_parse_log_lines_basic():
    text = (
        "# 2026-06-19\n\n"
        "- nieuwste idee #log/idee\n"
        "- iets over werk #log/werk\n"
        "gewone regel zonder tag\n"
        "* met sterretje als bullet #log/algemeen\n"
    )
    rows = parser.parse_log_lines(text)
    assert [r[1] for r in rows] == ["idee", "werk", "algemeen"]
    assert rows[0][0] == "nieuwste idee"          # tekst zonder tag/bullet
    assert [r[2] for r in rows] == [0, 1, 2]      # positie top->beneden


def test_parse_skips_frontmatter():
    text = (
        "---\n"
        "tags: [daily]\n"
        "note: #log/neptag-in-frontmatter telt niet\n"
        "---\n"
        "# 2026-06-19\n\n"
        "- echte log #log/algemeen\n"
    )
    rows = parser.parse_log_lines(text)
    assert len(rows) == 1
    assert rows[0][1] == "algemeen"


# --------------------------------------------------------------------------
# Vault-write: create + top-insert
# --------------------------------------------------------------------------

def _settings(tmp_path) -> Settings:
    return Settings(
        vault_path=tmp_path / "vault",
        index_db=tmp_path / "data" / "index.db",
        ics_file="",
        ics_url="",
        openrouter_api_key="",
        auto_rebuild_on_start=False,
        dashboard_tz="Europe/Amsterdam",
    )


def test_append_creates_minimal_note(tmp_path):
    s = _settings(tmp_path)
    d = date(2026, 6, 19)
    vault.append_log(s, "eerste regel", "algemeen", d)
    p = vault.daily_path(s, d)
    assert p.read_text(encoding="utf-8") == "# 2026-06-19\n\n- eerste regel #log/algemeen\n"


def test_append_inserts_newest_on_top_preserving_h1(tmp_path):
    s = _settings(tmp_path)
    d = date(2026, 6, 19)
    vault.append_log(s, "oudste", "algemeen", d)
    vault.append_log(s, "middelste", "werk", d)
    vault.append_log(s, "nieuwste", "idee", d)
    body = vault.daily_path(s, d).read_text(encoding="utf-8")
    assert body == (
        "# 2026-06-19\n\n"
        "- nieuwste #log/idee\n"
        "- middelste #log/werk\n"
        "- oudste #log/algemeen\n"
    )


def test_append_preserves_frontmatter(tmp_path):
    s = _settings(tmp_path)
    d = date(2026, 6, 19)
    p = vault.daily_path(s, d)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("---\ntags: [daily]\n---\n# 2026-06-19\n\n- bestaand #log/werk\n", encoding="utf-8")
    vault.append_log(s, "nieuw", "idee", d)
    body = p.read_text(encoding="utf-8")
    assert body == (
        "---\ntags: [daily]\n---\n"
        "# 2026-06-19\n\n"
        "- nieuw #log/idee\n"
        "- bestaand #log/werk\n"
    )


def test_log_line_is_single_line_even_with_newlines(tmp_path):
    s = _settings(tmp_path)
    line = vault.format_log_line("regel een\nregel twee", "algemeen")
    assert "\n" not in line
    assert line == "- regel een regel twee #log/algemeen"


# --------------------------------------------------------------------------
# Herbouwbare index
# --------------------------------------------------------------------------

def _seed_vault(tmp_path) -> Settings:
    s = _settings(tmp_path)
    daily = s.daily_dir
    daily.mkdir(parents=True, exist_ok=True)
    (daily / "2026-06-17.md").write_text(
        "# 2026-06-17\n\n- ouder idee #log/idee\n", encoding="utf-8"
    )
    (daily / "2026-06-18.md").write_text(
        "# 2026-06-18\n\n- nieuwer-bovenaan #log/werk\n- nieuwer-onderaan #log/algemeen\n",
        encoding="utf-8",
    )
    # ICS met één afspraak vandaag, zodat 'today' gevuld is.
    today = clock.today_local(s.dashboard_tz)
    ics = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//\n"
        "BEGIN:VEVENT\nUID:test-today@x\nSUMMARY:Testafspraak\n"
        f"DTSTART:{today.strftime('%Y%m%d')}T080000Z\n"
        f"DTEND:{today.strftime('%Y%m%d')}T083000Z\n"
        "END:VEVENT\nEND:VCALENDAR\n"
    )
    cal_dir = s.vault_path / "Calendar"
    cal_dir.mkdir(parents=True, exist_ok=True)
    (cal_dir / "test.ics").write_text(ics, encoding="utf-8")
    s.ics_file = str(cal_dir / "test.ics")
    return s


def test_rebuild_populates_logs_and_events(tmp_path):
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    counts = parser.rebuild(conn, s)
    assert counts["logs"] == 3
    assert counts["events"] >= 1


def test_rebuild_is_disposable_and_idempotent(tmp_path):
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    first = parser.rebuild(conn, s)
    second = parser.rebuild(conn, s)  # weggooien + opnieuw -> zelfde resultaat
    assert first == second


def test_recent_logs_ordering(tmp_path):
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)
    recent = get_recent_logs(conn, 10)
    # Nieuwste datum eerst; binnen een dag bovenste regel eerst.
    assert recent[0]["text"] == "nieuwer-bovenaan"
    assert recent[1]["text"] == "nieuwer-onderaan"
    assert recent[2]["text"] == "ouder idee"


def test_today_contains_seeded_event(tmp_path):
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)
    data = get_today_and_week(conn, s)
    summaries = [e["summary"] for e in data["today"]["events"]]
    assert "Testafspraak" in summaries


# --------------------------------------------------------------------------
# Auto-rebuild: change detection
# --------------------------------------------------------------------------

def test_vault_files_changed_true_when_no_rebuild(tmp_path):
    """Zonder last_rebuild is alles 'veranderd'."""
    s = _settings(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    # Geen rebuild gedaan, dus geen last_rebuild meta.
    assert parser.vault_files_changed(s) is True


def test_vault_files_changed_false_when_nothing_changed(tmp_path):
    """Na een rebuild is er niets veranderd — mits er geen ICS_URL is."""
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)
    assert parser.vault_files_changed(s) is False


def test_vault_files_changed_true_when_md_modified(tmp_path):
    """Een gewijzigd .md-bestand wordt gedetecteerd."""
    import time as _time

    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)

    # Kleine pauze zodat de mtime gegarandeerd > last_rebuild is.
    _time.sleep(0.02)

    # Wijzig een bestaand .md-bestand.
    md = s.daily_dir / "2026-06-18.md"
    md.write_text("# 2026-06-18\n\n- nieuwe regel #log/werk\n", encoding="utf-8")

    assert parser.vault_files_changed(s) is True


def test_vault_files_changed_true_with_ics_url(tmp_path):
    """ICS-URL is altijd 'mogelijk veranderd'."""
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)

    s.ics_url = "https://example.com/calendar.ics"
    assert parser.vault_files_changed(s) is True


def test_vault_files_changed_false_without_ics_url(tmp_path):
    """Zonder ICS-URL en zonder wijzigingen is er niets veranderd."""
    s = _seed_vault(tmp_path)
    conn = db.get_conn(s.index_db)
    db.init_schema(conn)
    parser.rebuild(conn, s)

    s.ics_url = ""
    assert parser.vault_files_changed(s) is False
