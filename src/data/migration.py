import shutil
from pathlib import Path

from data.elitedb import migrate_json


def main():
    project_root = Path(__file__).resolve().parents[2]
    database_path = project_root / "database"
    source_path = project_root / "database.json"

    if database_path.exists():
        shutil.rmtree(database_path)

    migrate_json(
        source=source_path,
        destination=database_path,
        collection="products",
    )

    print("Migration erfolgreich abgeschlossen.")


if __name__ == "__main__":
    main()