"""De enige schrijfactie in Fase 1: één logregel toevoegen aan de dagnotitie.

Regelformaat:  - {tekst} #log/{thema}
Plaatsing:     bovenaan (onder frontmatter + H1), nieuwste eerst.
Ontbreekt de dagnotitie? Dan maken we een minimale notitie (alleen de H1-datum).
Verder lezen we read-only.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .clock import today_local
from .config import Settings


def daily_path(settings: Settings, d: date) -> Path:
    return settings.daily_dir / f"{d.isoformat()}.md"


def format_log_line(text: str, theme: str) -> str:
    text = " ".join(text.split())  # alles op één regel; collapse witruimte
    theme = theme.strip().lstrip("#").removeprefix("log/").strip() or "algemeen"
    return f"- {text} #log/{theme}"


def _insert_top(content: str, line: str) -> str:
    """Voeg `line` toe als bovenste bullet, onder frontmatter en een eventuele H1."""
    lines = content.splitlines()
    n = len(lines)
    i = 0

    # Frontmatter overslaan.
    if n and lines[0].strip() == "---":
        j = 1
        while j < n and lines[j].strip() != "---":
            j += 1
        i = j + 1 if j < n else n

    # Lege regels na frontmatter overslaan.
    while i < n and lines[i].strip() == "":
        i += 1

    # Een eventuele H1 overslaan zodat de titel bovenaan blijft.
    if i < n and lines[i].lstrip().startswith("# "):
        i += 1

    head = lines[:i]
    tail = lines[i:]
    while tail and tail[0].strip() == "":
        tail.pop(0)

    block: list[str] = []
    if head:
        block.extend(head)
        block.append("")  # lege regel tussen kop en logs
    block.append(line)
    block.extend(tail)

    result = "\n".join(block)
    if not result.endswith("\n"):
        result += "\n"
    return result


def append_log(settings: Settings, text: str, theme: str, d: date | None = None) -> dict:
    if d is None:
        d = today_local(settings.dashboard_tz)
    path = daily_path(settings, d)
    line = format_log_line(text, theme)

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"# {d.isoformat()}\n\n{line}\n", encoding="utf-8")
        created = True
    else:
        content = path.read_text(encoding="utf-8")
        path.write_text(_insert_top(content, line), encoding="utf-8")
        created = False

    return {
        "path": str(path),
        "date": d.isoformat(),
        "line": line,
        "theme": format_log_line("", theme).split("#log/")[-1],
        "created": created,
    }
