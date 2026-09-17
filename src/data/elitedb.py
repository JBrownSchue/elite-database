import json
from pathlib import Path
from typing import Any


class Database:
    def __init__(
        self, path: str | Path | None = None, data: dict[str, Any] | None = None
    ):
        self.path = Path(path) if path else None
        self.data = data.copy() if data else {"products": []}
        self.data.setdefault("products", [])

    @classmethod
    def load(cls, path: str | Path):
        path = Path(path)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError("Die Datenbank muss ein JSON-Objekt enthalten.")
        return cls(path, data)

    def save(self, path: str | Path | None = None):
        target = Path(path) if path else self.path
        if target is None:
            raise ValueError("Kein Speicherpfad angegeben.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as file:
            json.dump(self.data, file, ensure_ascii=False, indent=2)
        self.path = target

    def all(self, collection: str = "products") -> list[dict[str, Any]]:
        values = self.data.setdefault(collection, [])
        if not isinstance(values, list):
            raise ValueError(f"Die Sammlung '{collection}' ist keine Liste.")
        return values

    def find(
        self, record_id: str, collection: str = "products"
    ) -> dict[str, Any] | None:
        return next(
            (
                record
                for record in self.all(collection)
                if record.get("id") == record_id
            ),
            None,
        )

    def add(self, record: dict[str, Any], collection: str = "products"):
        if not isinstance(record, dict) or not record.get("id"):
            raise ValueError("Ein Datensatz benötigt eine ID.")
        if self.find(str(record["id"]), collection):
            raise ValueError(f"Die ID '{record['id']}' existiert bereits.")
        self.all(collection).append(record.copy())
        return record

    def update(
        self, record_id: str, record: dict[str, Any], collection: str = "products"
    ):
        records = self.all(collection)
        for index, current in enumerate(records):
            if current.get("id") == record_id:
                if not record.get("id"):
                    raise ValueError("Ein Datensatz benötigt eine ID.")
                duplicate = self.find(str(record["id"]), collection)
                if duplicate is not None and duplicate is not current:
                    raise ValueError(f"Die ID '{record['id']}' existiert bereits.")
                records[index] = record.copy()
                return records[index]
        raise KeyError(f"Datensatz '{record_id}' wurde nicht gefunden.")

    def delete(self, record_id: str, collection: str = "products"):
        records = self.all(collection)
        for index, record in enumerate(records):
            if record.get("id") == record_id:
                return records.pop(index)
        raise KeyError(f"Datensatz '{record_id}' wurde nicht gefunden.")

    def search(self, query: str, collection: str = "products"):
        query = query.strip().lower()
        if not query:
            return list(self.all(collection))
        return [
            record
            for record in self.all(collection)
            if query in json.dumps(record, ensure_ascii=False).lower()
        ]
