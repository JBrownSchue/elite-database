import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
)

from data.elitedb import Database

DATABASE_FILE = Path(__file__).resolve().parents[2] / "database.json"


class ProductDialog(QDialog):
    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Produkt bearbeiten" if product else "Produkt anlegen")
        self.resize(650, 600)
        self.fields = {}
        form = QFormLayout()
        for key, label in [
            ("id", "ID"),
            ("sku", "SKU"),
            ("name", "Name"),
            ("description", "Beschreibung"),
            ("category", "Kategorie"),
            ("brand", "Marke"),
            ("stockQuantity", "Bestand"),
            ("isActive", "Aktiv"),
        ]:
            field = QLineEdit(str((product or {}).get(key, "")))
            form.addRow(label, field)
            self.fields[key] = field
        self.prices = QTextEdit()
        self.prices.setPlainText(
            json.dumps((product or {}).get("prices", []), ensure_ascii=False, indent=2)
        )
        form.addRow("Preise als JSON", self.prices)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def accept(self):
        try:
            prices = json.loads(self.prices.toPlainText() or "[]")
            if not isinstance(prices, list):
                raise ValueError("Preise müssen eine JSON-Liste sein.")
            product = {key: self.fields[key].text().strip() for key in self.fields}
            product["stockQuantity"] = int(product["stockQuantity"] or 0)
            product["isActive"] = product["isActive"].lower() in {
                "true",
                "1",
                "ja",
                "yes",
            }
            product["prices"] = prices
            if any(not product[key] for key in ("id", "sku", "name")):
                raise ValueError("ID, SKU und Name sind erforderlich.")
            self.result = product
            super().accept()
        except (ValueError, json.JSONDecodeError) as error:
            QMessageBox.warning(self, "Ungültige Eingabe", str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ELITE Datenbankverwaltung")
        self.resize(1200, 700)
        try:
            self.database = Database.load(DATABASE_FILE)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            QMessageBox.critical(self, "Datenbankfehler", str(error))
            self.database = Database(data={"products": []})
        self.build_ui()
        self.refresh_table()

    def build_ui(self):
        toolbar = QToolBar("Aktionen")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for label, handler in [
            ("Neu", self.create_product),
            ("Bearbeiten", self.update_product),
            ("Löschen", self.delete_product),
            ("Speichern", self.save_database),
        ]:
            button = QPushButton(label)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
        toolbar.addSeparator()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Produkte durchsuchen …")
        self.search.textChanged.connect(self.refresh_table)
        toolbar.addWidget(self.search)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(lambda *_: self.update_product())
        self.setCentralWidget(self.table)

    def refresh_table(self):
        columns = [
            "id",
            "sku",
            "name",
            "category",
            "brand",
            "stockQuantity",
            "isActive",
            "prices",
        ]
        products = self.database.search(self.search.text())
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(products))
        for row, product in enumerate(products):
            for column, key in enumerate(columns):
                value = product.get(key)
                text = (
                    f"{len(value)} Einträge"
                    if key == "prices" and isinstance(value, list)
                    else (
                        "Ja"
                        if value is True
                        else "Nein"
                        if value is False
                        else str(value if value is not None else "—")
                    )
                )
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, product.get("id"))
                if isinstance(value, (dict, list)):
                    item.setToolTip(json.dumps(value, ensure_ascii=False, indent=2))
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.statusBar().showMessage(f"{len(products)} Produkte")

    def selected_id(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def create_product(self):
        dialog = ProductDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.add(dialog.result)
                self.save_database()
                self.refresh_table()
            except ValueError as error:
                QMessageBox.warning(self, "Ungültige Eingabe", str(error))

    def update_product(self):
        record_id = self.selected_id()
        product = self.database.find(record_id) if record_id else None
        if not product:
            QMessageBox.information(
                self, "Auswahl", "Bitte zuerst ein Produkt auswählen."
            )
            return
        dialog = ProductDialog(product, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.update(record_id, dialog.result)
                self.save_database()
                self.refresh_table()
            except (ValueError, KeyError) as error:
                QMessageBox.warning(self, "Fehler", str(error))

    def delete_product(self):
        record_id = self.selected_id()
        product = self.database.find(record_id) if record_id else None
        if not product:
            QMessageBox.information(
                self, "Auswahl", "Bitte zuerst ein Produkt auswählen."
            )
            return
        if (
            QMessageBox.question(
                self,
                "Löschen bestätigen",
                f"Produkt „{product.get('name', record_id)}“ löschen?",
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.database.delete(record_id)
            self.save_database()
            self.refresh_table()

    def save_database(self):
        try:
            self.database.save(DATABASE_FILE)
            self.statusBar().showMessage("Gespeichert")
        except OSError as error:
            QMessageBox.critical(self, "Speicherfehler", str(error))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
