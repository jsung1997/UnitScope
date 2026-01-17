from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox
)

from engine.api import analyze_netlist


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Analog Unit Analyzer (Local Only)")
        self.resize(1100, 700)

        self.netlist_path = None
        self.results = None

        root = QWidget()
        self.setCentralWidget(root)

        # Layout
        main_layout = QHBoxLayout(root)

        # Left panel
        left = QVBoxLayout()
        main_layout.addLayout(left, 1)

        self.path_label = QLabel("Netlist: (none)")
        self.path_label.setWordWrap(True)
        left.addWidget(self.path_label)

        btn_open = QPushButton("Open Netlist (.sp/.cdl)")
        btn_open.clicked.connect(self.open_file)
        left.addWidget(btn_open)

        btn_run = QPushButton("Analyze")
        btn_run.clicked.connect(self.run_analysis)
        left.addWidget(btn_run)

        left.addStretch(1)

        # Right panel
        right = QVBoxLayout()
        main_layout.addLayout(right, 3)

        right.addWidget(QLabel("Ranked Weak Points"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Unit ID", "Type", "Risk", "L", "I"])
        self.table.cellClicked.connect(self.on_row_clicked)
        right.addWidget(self.table, 2)

        right.addWidget(QLabel("Unit Details (Explainable)"))
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        right.addWidget(self.details, 3)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Netlist", "", "Netlist Files (*.sp *.cdl *.cir *.net);;All Files (*)"
        )
        if path:
            self.netlist_path = path
            self.path_label.setText(f"Netlist: {path}")
            self.details.clear()
            self.table.setRowCount(0)
            self.results = None

    def run_analysis(self):
        if not self.netlist_path:
            QMessageBox.warning(self, "Missing file", "Please open a netlist first.")
            return

        try:
            self.results = analyze_netlist(self.netlist_path)
        except Exception as e:
            QMessageBox.critical(self, "Analysis error", str(e))
            return

        units = self.results["units"]
        self.table.setRowCount(len(units))

        for r, u in enumerate(units):
            self.table.setItem(r, 0, QTableWidgetItem(u["id"]))
            self.table.setItem(r, 1, QTableWidgetItem(u["type"]))
            self.table.setItem(r, 2, QTableWidgetItem(str(u["risk"])))
            self.table.setItem(r, 3, QTableWidgetItem(str(u["likelihood"])))
            self.table.setItem(r, 4, QTableWidgetItem(str(u["impact"])))

        self.table.resizeColumnsToContents()
        self.details.setPlainText(
            f"Parsed MOSFETs: {self.results['mos_count']}\n"
            f"Parsed passives: {self.results['passive_count']}\n"
            f"Detected units: {len(units)}\n\n"
            "Click a row to see explainable details."
        )

    def on_row_clicked(self, row: int, col: int):
        if not self.results:
            return

        u = self.results["units"][row]
        lines = []
        lines.append(f"{u['id']}  [{u['type']}]")
        lines.append(f"Risk={u['risk']}  (L={u['likelihood']}, I={u['impact']}, C={u['confidence']})")
        lines.append("")
        lines.append("Members:")
        lines.append("  " + ", ".join(u["members"]))
        lines.append("")
        lines.append("Why detected:")
        for w in u["why_detected"]:
            lines.append(f"  - {w}")
        lines.append("")
        lines.append("Top checks:")
        for c in u["top_checks"]:
            lines.append(f"  - {c['name']}: sev={c['severity']:.2f} ({c['severity_label']}), observed={c['observed']}")
        lines.append("")
        lines.append("Blast radius (downstream units):")
        if u["blast_radius"]:
            lines.append("  " + ", ".join(u["blast_radius"]))
        else:
            lines.append("  (none inferred)")
        lines.append("")
        lines.append("Explanation:")
        lines.append("  " + u["explanation"])

        self.details.setPlainText("\n".join(lines))


def run():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
