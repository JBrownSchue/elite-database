import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: str | Path):
        self.root = Path(path)
        self.manifest_path = self.root / "manifest.json"
        self.documents = self.root / "documents"
        self.collections = self.root / "collections"
        self.indexes = self.root / "indexes"
        self.history = self.root / "history"
        self.manifest = {}
        self._ensure_layout()

    @classmethod
    def create(cls, path: str | Path):
        database = cls(path)
        if not database.manifest_path.exists():
            database.manifest = {
                "database": "elite-store",
                "format": "elite-document-store",
                "version": 1,
                "created": database._now(),
                "collections": {},
            }
            database._write_json(database.manifest_path, database.manifest)
        else:
            database._load_manifest()
        return database

    @classmethod
    def load(cls, path: str | Path):
        database = cls(path)
        if not database.manifest_path.exists():
            raise FileNotFoundError(f"Keine ELITE-Datenbank gefunden: {database.manifest_path}")
        database._load_manifest()
        return database

    def _ensure_layout(self):
        for folder in (self.documents, self.collections, self.indexes, self.history):
            folder.mkdir(parents=True, exist_ok=True)

    def _load_manifest(self):
        self.manifest = self._read_json(self.manifest_path)
        if self.manifest.get("format") != "elite-document-store":
            raise ValueError("Die Datei ist keine ELITE-Dokumentdatenbank.")

    def _now(self):
        return datetime.now(UTC).isoformat()

    def _read_json(self, path):
        with Path(path).open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_json(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
        temporary.replace(path)

    def create_collection(self, name: str):
        self._validate_name(name)
        self.manifest.setdefault("collections", {})[name] = {
            "path": f"documents/{name}",
            "index": f"indexes/{name}.json",
            "identity": "id",
        }
        (self.documents / name).mkdir(parents=True, exist_ok=True)
        self.rebuild_index(name)
        self._write_json(self.manifest_path, self.manifest)

    def collections_list(self):
        return sorted(self.manifest.get("collections", {}).keys())

    def _validate_name(self, value):
        if not value or not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Ungültiger Sammlungsname.")

    def _collection_path(self, collection):
        if collection not in self.manifest.get("collections", {}):
            self.create_collection(collection)
        return self.documents / collection

    def _document_path(self, collection, record_id):
        return self._collection_path(collection) / f"{record_id}.json"

    def insert(self, collection: str, document: dict[str, Any]):
        record_id = str(document.get("id", "")).strip()
        if not record_id:
            raise ValueError("Jedes Dokument benötigt eine ID.")
        path = self._document_path(collection, record_id)
        if path.exists():
            raise ValueError(f"Die ID '{record_id}' existiert bereits.")
        document = self._prepare(document, collection)
        self._write_json(path, document)
        self.rebuild_index(collection)
        return document

    def get(self, collection: str, record_id: str):
        path = self._document_path(collection, record_id)
        return self._read_json(path) if path.exists() else None

    def all(self, collection: str):
        folder = self._collection_path(collection)
        return [self._read_json(path) for path in sorted(folder.glob("*.json"))]

    def update(self, collection: str, record_id: str, document: dict[str, Any]):
        path = self._document_path(collection, record_id)
        if not path.exists():
            raise KeyError(f"Dokument '{record_id}' wurde nicht gefunden.")
        old = self._read_json(path)
        self._save_history(collection, record_id, old)
        document = self._prepare(document, collection, old)
        self._write_json(path, document)
        self.rebuild_index(collection)
        return document

    def delete(self, collection: str, record_id: str):
        path = self._document_path(collection, record_id)
        if not path.exists():
            raise KeyError(f"Dokument '{record_id}' wurde nicht gefunden.")
        old = self._read_json(path)
        self._save_history(collection, record_id, old)
        path.unlink()
        self.rebuild_index(collection)
        return old

    def search(self, collection: str, query: str = "", **filters):
        query = query.lower().strip()
        result = []
        for document in self.all(collection):
            haystack = json.dumps(document, ensure_ascii=False).lower()
            if query and query not in haystack:
                continue
            if any(self._value(document, key) != value for key, value in filters.items()):
                continue
            result.append(document)
        return result

    def rebuild_index(self, collection: str):
        documents = (
            self.all(collection) if collection in self.manifest.get("collections", {}) else []
        )
        index = {"byId": {}, "byType": {}, "updated": self._now()}
        for document in documents:
            record_id = str(document["id"])
            relative = str(
                self._document_path(collection, record_id).relative_to(self.root)
            ).replace("\\", "/")
            index["byId"][record_id] = relative
            if document.get("type"):
                index["byType"].setdefault(document["type"], []).append(record_id)
        self._write_json(self.indexes / f"{collection}.json", index)
        self._write_json(self.manifest_path, self.manifest)
        return index

    def revisions(self, collection: str, record_id: str):
        folder = self.history / collection / record_id
        return (
            [self._read_json(path) for path in sorted(folder.glob("*.json"))]
            if folder.exists()
            else []
        )

    def _save_history(self, collection, record_id, document):
        folder = self.history / collection / record_id
        revision = len(list(folder.glob("*.json"))) + 1 if folder.exists() else 1
        self._write_json(folder / f"revision-{revision:04d}.json", document)

    def _prepare(self, document, collection, old=None):
        result = dict(document)
        result["id"] = str(result["id"])
        result.setdefault("type", collection.rstrip("s"))
        meta = dict(old.get("meta", {}) if old else {})
        meta.update({"updated": self._now(), "revision": int(meta.get("revision", 0)) + 1})
        meta.setdefault("created", self._now())
        result["meta"] = meta
        return result

    def _value(self, document, path):
        value = document
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value


def migrate_json(source: str | Path, destination: str | Path, collection="products"):
    source = Path(source)
    database = Database.create(destination)
    database.create_collection(collection)
    data = json.loads(source.read_text(encoding="utf-8"))
    records = data.get(collection, []) if isinstance(data, dict) else data
    for record in records:
        database.insert(collection, record)
    return database
