import json
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
)


DATABASE_FILE = Path(__file__).resolve().parents[2] / "database.json"


class ActionDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(500, 300)

        layout = QVBoxLayout(self)

        text_edit = QTextEdit()
        text_edit.setPlainText(message)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        close_button = QPushButton("Schließen")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ELITE Datenbankverwaltung")
        self.resize(1100, 600)

        self.database = self.load_database()

        self.create_toolbar()
        self.create_data_table()

    def load_database(self) -> dict:
        try:
            with DATABASE_FILE.open("r", encoding="utf-8") as file:
                return json.load(file)

        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Datei nicht gefunden",
                f"Die Datei wurde nicht gefunden:\n{DATABASE_FILE}",
            )
            return {}

        except json.JSONDecodeError as error:
            QMessageBox.critical(
                self,
                "Ungültiges JSON",
                f"Die Datenbank enthält ungültiges JSON:\n{error}",
            )
            return {}

    def create_toolbar(self):
        toolbar = QToolBar("CRUD-Aktionen")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        create_button = QPushButton("Create")
        create_button.clicked.connect(self.open_create_dialog)
        toolbar.addWidget(create_button)

        read_button = QPushButton("Read")
        read_button.clicked.connect(self.open_read_dialog)
        toolbar.addWidget(read_button)

        update_button = QPushButton("Update")
        update_button.clicked.connect(self.open_update_dialog)
        toolbar.addWidget(update_button)

        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self.open_delete_dialog)
        toolbar.addWidget(delete_button)

    def format_table_value(self, value):
        if value is None:
            return "—"

        if isinstance(value, bool):
            return "Ja" if value else "Nein"

        if isinstance(value, list):
            return f"{len(value)} Einträge"

        if isinstance(value, dict):
            return f"{len(value)} Felder"

        return str(value)

    def create_data_table(self):
        records = self.database.get("products", [])

        if not records:
            self.setCentralWidget(QLabel("Keine Produkte vorhanden."))
            return

        columns = list(
            dict.fromkeys(
                column_name
                for record in records
                for column_name in record.keys()
            )
        )

        self.table = QTableWidget()
        self.table.setRowCount(len(records))
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        for row_index, record in enumerate(records):
            for column_index, column_name in enumerate(columns):
                value = record.get(column_name)
                display_value = self.format_table_value(value)

                item = QTableWidgetItem(display_value)

                if isinstance(value, (dict, list)):
                    item.setToolTip(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                            indent=2,
                        )
                    )
                else:
                    item.setToolTip(display_value)

                self.table.setItem(row_index, column_index, item)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setMinimumSectionSize(36)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        for column_name in ["id", "sku", "category", "brand"]:
            if column_name in columns:
                column_index = columns.index(column_name)
                self.table.setColumnWidth(column_index, 140)

        for column_name in ["name", "description"]:
            if column_name in columns:
                column_index = columns.index(column_name)
                self.table.setColumnWidth(column_index, 220)

        if "prices" in columns:
            prices_index = columns.index("prices")
            self.table.setColumnWidth(prices_index, 120)

        self.table.cellDoubleClicked.connect(
            self.show_cell_details
        )

        self.setCentralWidget(self.table)

    def show_cell_details(self, row, column):
        item = self.table.item(row, column)

        if item is None:
            return

        header_item = self.table.horizontalHeaderItem(column)

        if header_item is None:
            return

        column_name = header_item.text()
        record = self.database["products"][row]
        value = record.get(column_name)

        if not isinstance(value, (dict, list)):
            return

        details = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )

        dialog = ActionDialog(
            f"Details: {column_name}",
            details,
            self,
        )
        dialog.exec()

    def open_create_dialog(self):
        dialog = ActionDialog(
            "Create",
            "Hier wird später ein neuer Datensatz angelegt.",
            self,
        )
        dialog.exec()

    def open_read_dialog(self):
        dialog = ActionDialog(
            "Read",
            "Hier werden später Datensätze angezeigt.",
            self,
        )
        dialog.exec()

    def open_update_dialog(self):
        dialog = ActionDialog(
            "Update",
            "Hier wird später ein Datensatz bearbeitet.",
            self,
        )
        dialog.exec()

    def open_delete_dialog(self):
        dialog = ActionDialog(
            "Delete",
            "Hier wird später ein Datensatz gelöscht.",
            self,
        )
        dialog.exec()


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()