import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextEdit,
    QVBoxLayout, QWidget
)

from data.elitedb import Database

DATABASE_PATH = Path(__file__).resolve().parents[2] / "database"


class AttributeEditor(QWidget):
    def __init__(self, attributes=None, parent=None):
        super().__init__(parent)
        self.rows = []
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("＋ Eigenschaft hinzufügen")
        self.add_button.clicked.connect(self.add_row)
        self.main_layout.addWidget(self.add_button)
        for key, value in (attributes or {}).items():
            self.add_row(key, value)

    def add_row(self, key="", value=""):
        row = QHBoxLayout()
        name = QLineEdit(str(key))
        name.setPlaceholderText("Eigenschaft, z. B. Größe")
        kind = QComboBox()
        kind.addItems(["Text", "Zahl", "Ja/Nein", "Mehrzeiliger Text"])
        value_field = QLineEdit()
        value_field.setPlaceholderText("Wert")
        remove = QPushButton("Entfernen")
        remove.setObjectName("secondaryButton")
        row.addWidget(name, 2)
        row.addWidget(kind, 1)
        row.addWidget(value_field, 2)
        row.addWidget(remove)
        self.main_layout.insertLayout(self.main_layout.count() - 1, row)
        record = (row, name, kind, value_field)
        self.rows.append(record)
        remove.clicked.connect(lambda: self.remove_row(record))
        self.set_value_type(kind, value_field, value)
        kind.currentTextChanged.connect(lambda text: self.update_editor(text, value_field))

    def set_value_type(self, kind, field, value):
        if isinstance(value, bool):
            kind.setCurrentText("Ja/Nein")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            kind.setCurrentText("Zahl")
        elif isinstance(value, str) and "\n" in value:
            kind.setCurrentText("Mehrzeiliger Text")
        field.setText(str(value).lower() if isinstance(value, bool) else str(value))
        self.update_editor(kind.currentText(), field)

    def update_editor(self, text, field):
        field.setPlaceholderText("Ja oder Nein" if text == "Ja/Nein" else "Zahl eingeben" if text == "Zahl" else "Wert")

    def remove_row(self, record):
        row, *_ = record
        while row.count():
            item = row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.main_layout.removeItem(row)
        self.rows.remove(record)

    def values(self):
        result = {}
        for _, name, kind, field in self.rows:
            key = name.text().strip()
            value = field.text().strip()
            if not key:
                raise ValueError("Jede zusätzliche Eigenschaft benötigt einen Namen.")
            if key in result:
                raise ValueError(f"Die Eigenschaft '{key}' wurde doppelt verwendet.")
            if kind.currentText() == "Zahl":
                try:
                    value = float(value) if "." in value else int(value)
                except ValueError:
                    raise ValueError(f"'{value}' ist keine gültige Zahl.")
            elif kind.currentText() == "Ja/Nein":
                if value.lower() not in {"ja", "nein", "true", "false", "1", "0"}:
                    raise ValueError(f"'{value}' ist kein gültiger Ja/Nein-Wert.")
                value = value.lower() in {"ja", "true", "1"}
            result[key] = value
        return result


class ProductDialog(QDialog):
    def __init__(self, product=None, parent=None):
        super().__init__(parent)
        self.product = product or {}
        self.setWindowTitle("Produkt bearbeiten" if product else "Neues Produkt")
        self.resize(720, 650)
        layout = QVBoxLayout(self)
        title = QLabel(self.windowTitle())
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        form = QFormLayout()
        self.fields = {}
        definitions = [("id", "ID *"), ("sku", "SKU *"), ("name", "Name *"), ("description", "Beschreibung"), ("category", "Kategorie"), ("brand", "Marke")]
        for key, label in definitions:
            field = QLineEdit(str(self.product.get(key, "")))
            form.addRow(label, field)
            self.fields[key] = field
        stock = QSpinBox()
        stock.setRange(0, 1000000000)
        stock.setValue(int(self.product.get("stockQuantity", 0) or 0))
        self.fields["stockQuantity"] = stock
        form.addRow("Bestand", stock)
        active = QCheckBox("Produkt ist aktiv")
        active.setChecked(bool(self.product.get("isActive", True)))
        self.fields["isActive"] = active
        form.addRow("Status", active)
        layout.addLayout(form)
        label = QLabel("Zusätzliche Eigenschaften")
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
        layout.addWidget(QLabel("Ergänze Eigenschaften wie Größe, Verlag oder Spieleranzahl ohne JSON.") )
        attributes = self.product.get("attributes", {})
        if not isinstance(attributes, dict):
            attributes = {}
        self.attributes = AttributeEditor(attributes)
        layout.addWidget(self.attributes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        try:
            values: dict[str, object] = {
                key: field.text().strip() for key, field in self.fields.items() if isinstance(field, QLineEdit)
            }
            if any(not values[key] for key in ("id", "sku", "name")):
                raise ValueError("ID, SKU und Name sind erforderlich.")
            values["stockQuantity"] = self.fields["stockQuantity"].value()
            values["isActive"] = self.fields["isActive"].isChecked()
            values["attributes"] = self.attributes.values()
            self.document = values
            super().accept()
        except ValueError as error:
            QMessageBox.warning(self, "Eingabe prüfen", str(error))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ELITE · Produktdatenbank")
        self.resize(1200, 760)
        try:
            self.database = Database.create(DATABASE_PATH)
            if "products" not in self.database.collections_list():
                self.database.create_collection("products")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            QMessageBox.critical(self, "Datenbankfehler", str(error))
            self.database = Database.create(DATABASE_PATH)
            if "products" not in self.database.collections_list():
                self.database.create_collection("products")
        self.products = []
        self.build_ui()
        self.refresh()

    def build_ui(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        heading = QHBoxLayout()
        title = QLabel("Produktdatenbank")
        title.setObjectName("title")
        heading.addWidget(title)
        heading.addStretch()
        add = QPushButton("＋ Neues Produkt")
        add.setObjectName("primaryButton")
        add.clicked.connect(self.create_product)
        heading.addWidget(add)
        layout.addLayout(heading)
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Suchen …")
        self.search.textChanged.connect(self.refresh)
        tools.addWidget(self.search, 1)
        self.category = QComboBox()
        self.category.currentTextChanged.connect(self.refresh)
        tools.addWidget(self.category)
        edit = QPushButton("Bearbeiten")
        edit.clicked.connect(self.edit_product)
        tools.addWidget(edit)
        delete = QPushButton("Löschen")
        delete.setObjectName("dangerButton")
        delete.clicked.connect(self.delete_product)
        tools.addWidget(delete)
        layout.addLayout(tools)
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_product())
        layout.addWidget(self.table, 3)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Produkt auswählen, um die Details zu sehen.")
        layout.addWidget(self.details, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Bereit")

    def refresh(self):
        records = self.database.all("products")
        current = self.category.currentText()
        categories = sorted({str(record.get("category", "Ohne Kategorie")) for record in records})
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Alle Kategorien")
        self.category.addItems(categories)
        if current in categories:
            self.category.setCurrentText(current)
        self.category.blockSignals(False)
        query = self.search.text().lower().strip()
        self.products = [record for record in records if (not query or query in json.dumps(record, ensure_ascii=False).lower()) and (self.category.currentText() == "Alle Kategorien" or str(record.get("category", "Ohne Kategorie")) == self.category.currentText())]
        columns = [("name", "Produkt"), ("sku", "SKU"), ("category", "Kategorie"), ("brand", "Marke"), ("stockQuantity", "Bestand"), ("isActive", "Status")]
        self.table.setSortingEnabled(False)
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels([label for _, label in columns])
        self.table.setRowCount(len(self.products))
        for row, record in enumerate(self.products):
            for col, (key, _) in enumerate(columns):
                value = record.get(key, "—")
                text = "Aktiv" if value is True else "Inaktiv" if value is False else str(value)
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, record.get("id"))
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 240)
        self.statusBar().showMessage(f"{len(self.products)} Produkte angezeigt")

    def selected(self):
        row = self.table.currentRow()
        return self.products[row] if 0 <= row < len(self.products) else None

    def show_details(self):
        product = self.selected()
        self.details.setPlainText(json.dumps(product, ensure_ascii=False, indent=2) if product else "")

    def create_product(self):
        dialog = ProductDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.insert("products", dialog.document)
                self.save_database()
                self.refresh()
            except ValueError as error:
                QMessageBox.warning(self, "Nicht gespeichert", str(error))

    def edit_product(self):
        product = self.selected()
        if not product:
            QMessageBox.information(self, "Auswahl", "Bitte zuerst ein Produkt auswählen.")
            return
        dialog = ProductDialog(product, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.database.update("products", product["id"], dialog.document)
                self.save_database()
                self.refresh()
            except (ValueError, KeyError) as error:
                QMessageBox.warning(self, "Nicht gespeichert", str(error))

    def delete_product(self):
        product = self.selected()
        if not product:
            QMessageBox.information(self, "Auswahl", "Bitte zuerst ein Produkt auswählen.")
            return
        answer = QMessageBox.question(self, "Löschen bestätigen", f"„{product.get('name', product['id'])}“ löschen?")
        if answer == QMessageBox.StandardButton.Yes:
            self.database.delete("products", product["id"])
            self.save_database()
            self.refresh()

    def save_database(self):
        try:
            self.database.rebuild_index("products")
            self.statusBar().showMessage("Änderungen gespeichert")
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Speicherfehler", str(error))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
