# elite-database

## Installation

### Voraussetzungen
- Python 3.14 oder neuer
- [uv](https://docs.astral.sh/uv/) (empfohlen) oder pip

### Abhängigkeiten installieren

Im Projektordner ausführen:

```bash
uv sync
```

Falls du `uv` nicht verwendest, kannst du das Projekt auch mit pip installieren:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate
python -m pip install -e .
```

### Anwendung starten

Mit `uv`:

```bash
uv run gui
```

Oder nach der pip-Installation:

```bash
python -m gui.main
```

## Hinweis

Die Anwendung lädt die Daten aus `database.json` im Projektstammverzeichnis.