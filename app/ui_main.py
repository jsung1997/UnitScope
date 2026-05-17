from __future__ import annotations

import html
import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFileDialog,
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QTextEdit, QMessageBox,
    QToolButton, QAbstractItemView, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit
)


from engine.config import PdkConfig, load_pdk_config, normalize_list
from engine.api import analyze_netlist


def _list_text(values: list[str]) -> str:
    return ", ".join(values)


class PdkConfigDialog(QDialog):
    FIELD_LABELS = {
        "name": "Config name",
        "nmos_models": "NMOS model patterns",
        "pmos_models": "PMOS model patterns",
        "supply_nets": "Supply net names",
        "ground_nets": "Ground net names",
        "width_params": "Width parameter names",
        "length_params": "Length parameter names",
        "multiplier_params": "Multiplier parameter names",
        "finger_params": "Finger parameter names",
        "fin_params": "FinFET parameter names",
        "ignored_models": "Ignored model names",
    }

    def __init__(self, config: PdkConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDK / Project Config")
        self.resize(620, 520)
        self.config = config
        self.edits: dict[str, QLineEdit] = {}

        root = QVBoxLayout(self)
        intro = QLabel(
            "Use comma-separated values. Model and net patterns are matched case-insensitively."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        root.addLayout(form)

        for field, label in self.FIELD_LABELS.items():
            edit = QLineEdit()
            value = getattr(config, field)
            edit.setText(_list_text(value) if isinstance(value, list) else str(value))
            self.edits[field] = edit
            form.addRow(label, edit)

        file_row = QHBoxLayout()
        btn_load = QPushButton("Load JSON")
        btn_load.clicked.connect(self.load_json)
        file_row.addWidget(btn_load)
        btn_save = QPushButton("Save JSON")
        btn_save.clicked.connect(self.save_json)
        file_row.addWidget(btn_save)
        root.addLayout(file_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self):
        config = self.get_config()
        required = {
            "NMOS model patterns": config.nmos_models,
            "PMOS model patterns": config.pmos_models,
            "Supply net names": config.supply_nets,
            "Ground net names": config.ground_nets,
            "Width parameter names": config.width_params,
            "Length parameter names": config.length_params,
        }
        missing = [name for name, values in required.items() if not values]
        if missing:
            QMessageBox.warning(
                self,
                "Invalid PDK config",
                "These fields cannot be empty:\n\n" + "\n".join(missing),
            )
            return
        self.config = config
        super().accept()

    def get_config(self) -> PdkConfig:
        data = {"name": self.edits["name"].text().strip() or "Project PDK"}
        for field in self.FIELD_LABELS:
            if field == "name":
                continue
            data[field] = normalize_list(self.edits[field].text())
        return PdkConfig.from_dict(data)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load PDK Config",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            self.config = load_pdk_config(path)
        except Exception as e:
            QMessageBox.critical(self, "Config load error", str(e))
            return
        for field in self.FIELD_LABELS:
            value = getattr(self.config, field)
            self.edits[field].setText(_list_text(value) if isinstance(value, list) else str(value))

    def save_json(self):
        config = self.get_config()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDK Config",
            "unitwise_pdk_config.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            config.save(path)
        except Exception as e:
            QMessageBox.critical(self, "Config save error", str(e))
            return


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UnitWise - Analog Unit Analyzer")
        self.resize(1240, 780)
        self.setMinimumSize(980, 640)

        self.netlist_path = None
        self.results = None
        self.pdk_config = load_pdk_config()

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        # Main layout: left controls + right results
        main_layout = QHBoxLayout(root)
        main_layout.setContentsMargins(22, 22, 22, 22)
        main_layout.setSpacing(18)

        # -------------------------
        # Left panel (controls)
        # -------------------------
        left_panel = QWidget()
        left_panel.setObjectName("SidePanel")
        left = QVBoxLayout()
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(12)
        left_panel.setLayout(left)
        main_layout.addWidget(left_panel, 1)

        app_title = QLabel("UnitWise")
        app_title.setObjectName("AppTitle")
        left.addWidget(app_title)

        subtitle = QLabel("Analog weak-point review")
        subtitle.setObjectName("Subtitle")
        left.addWidget(subtitle)

        self.path_label = QLabel("Netlist: (none)")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setWordWrap(True)
        left.addWidget(self.path_label)

        btn_open = QPushButton("Open Netlist (.sp/.cdl)")
        btn_open.setObjectName("PrimaryButton")
        btn_open.clicked.connect(self.open_file)
        left.addWidget(btn_open)

        btn_run = QPushButton("Analyze")
        btn_run.setObjectName("AccentButton")
        btn_run.clicked.connect(self.run_analysis)
        left.addWidget(btn_run)

        btn_pdk = QPushButton("PDK / Project Config")
        btn_pdk.setObjectName("SecondaryButton")
        btn_pdk.clicked.connect(self.edit_pdk_config)
        left.addWidget(btn_pdk)

        btn_export_json = QPushButton("Export JSON")
        btn_export_json.setObjectName("SecondaryButton")
        btn_export_json.clicked.connect(self.export_json)
        left.addWidget(btn_export_json)

        btn_export_html = QPushButton("Export HTML Report")
        btn_export_html.setObjectName("SecondaryButton")
        btn_export_html.clicked.connect(self.export_html)
        left.addWidget(btn_export_html)

        left.addStretch(1)

        hint = QLabel("Local static review. No netlist leaves this machine.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        left.addWidget(hint)

        # -------------------------
        # Right panel (results)
        # -------------------------
        right_panel = QWidget()
        right_panel.setObjectName("ContentPanel")
        right = QVBoxLayout()
        right.setContentsMargins(18, 18, 18, 18)
        right.setSpacing(12)
        right_panel.setLayout(right)
        main_layout.addWidget(right_panel, 3)

        # Header row: title on left + ? button on right
        header_row = QHBoxLayout()
        title = QLabel("Ranked Weak Points")
        title.setObjectName("SectionTitle")
        header_row.addWidget(title)
        header_row.addStretch(1)

        help_btn = QToolButton()
        help_btn.setObjectName("HelpButton")
        help_btn.setText("?")
        help_btn.setToolTip("What do Risk, L, I, C mean?")
        help_btn.setFixedSize(28, 28)
        help_btn.clicked.connect(self.show_help)
        header_row.addWidget(help_btn)

        right.addLayout(header_row)

        # Table with C column added
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("ResultsTable")
        self.table.setHorizontalHeaderLabels(["Unit ID", "Type", "Risk", "L", "I", "C"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellClicked.connect(self.on_row_clicked)
        right.addWidget(self.table, 2)

        details_title = QLabel("Unit Details")
        details_title.setObjectName("SectionTitleSmall")
        right.addWidget(details_title)
        self.details = QTextEdit()
        self.details.setObjectName("DetailsPane")
        self.details.setReadOnly(True)
        right.addWidget(self.details, 3)

        self.apply_theme()

    def edit_pdk_config(self):
        dialog = PdkConfigDialog(self.pdk_config, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.pdk_config = dialog.get_config()
        self.details.setPlainText(
            f"PDK config active: {self.pdk_config.name}\n\n"
            "Run analysis again to apply this configuration."
        )

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #121212;
            }
            QDialog {
                background: #1d1d1d;
                color: #eeeeee;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QWidget#Root {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #1b1b1b,
                    stop: 0.50 #111111,
                    stop: 1 #242424
                );
                color: #eeeeee;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 13px;
            }
            QWidget#SidePanel,
            QWidget#ContentPanel {
                background: rgba(34, 34, 34, 165);
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 8px;
            }
            QLabel#AppTitle {
                color: #ffffff;
                font-size: 28px;
                font-weight: 700;
                padding-bottom: 0;
            }
            QLabel#Subtitle {
                color: #c7c7c7;
                font-size: 13px;
                padding-bottom: 12px;
            }
            QLabel#PathLabel {
                background: rgba(255, 255, 255, 18);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 6px;
                color: #dddddd;
                padding: 10px;
                line-height: 1.35;
            }
            QLabel#Hint {
                color: #a8a8a8;
                font-size: 12px;
            }
            QLabel#SectionTitle {
                color: #ffffff;
                font-size: 19px;
                font-weight: 650;
            }
            QLabel#SectionTitleSmall {
                color: #d7d7d7;
                font-size: 13px;
                font-weight: 650;
                padding-top: 4px;
            }
            QPushButton {
                min-height: 34px;
                border-radius: 6px;
                padding: 8px 12px;
                text-align: left;
                font-weight: 600;
            }
            QPushButton#PrimaryButton,
            QPushButton#SecondaryButton {
                background: rgba(255, 255, 255, 22);
                color: #f1f1f1;
                border: 1px solid rgba(255, 255, 255, 58);
            }
            QPushButton#PrimaryButton:hover,
            QPushButton#SecondaryButton:hover {
                background: rgba(255, 255, 255, 42);
                border-color: rgba(255, 255, 255, 105);
            }
            QPushButton#AccentButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #f3f3f3,
                    stop: 1 #bdbdbd
                );
                color: #111111;
                border: 1px solid #ffffff;
            }
            QPushButton#AccentButton:hover {
                background: #ffffff;
            }
            QPushButton:pressed {
                background: #9f9f9f;
            }
            QToolButton#HelpButton {
                background: rgba(255, 255, 255, 24);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 65);
                border-radius: 14px;
                font-weight: 700;
            }
            QToolButton#HelpButton:hover {
                background: rgba(255, 255, 255, 45);
            }
            QTableWidget#ResultsTable {
                background: rgba(255, 255, 255, 18);
                alternate-background-color: rgba(255, 255, 255, 30);
                color: #eeeeee;
                gridline-color: rgba(255, 255, 255, 28);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 6px;
                selection-background-color: rgba(255, 255, 255, 82);
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background: rgba(255, 255, 255, 36);
                color: #ffffff;
                border: 0;
                border-right: 1px solid rgba(255, 255, 255, 28);
                padding: 8px;
                font-weight: 700;
            }
            QTextEdit#DetailsPane {
                background: rgba(255, 255, 255, 18);
                color: #eeeeee;
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 6px;
                padding: 10px;
                font-family: Consolas, "Cascadia Mono", monospace;
                font-size: 12px;
                selection-background-color: rgba(255, 255, 255, 90);
            }
            QLineEdit {
                background: rgba(255, 255, 255, 24);
                color: #f2f2f2;
                border: 1px solid rgba(255, 255, 255, 58);
                border-radius: 5px;
                padding: 7px;
            }
            QLineEdit:focus {
                border-color: rgba(255, 255, 255, 130);
            }
            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 80);
                border-radius: 5px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 135);
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Netlist",
            "",
            "Netlist Files (*.sp *.cdl *.cir *.net);;All Files (*)"
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
            self.results = analyze_netlist(self.netlist_path, pdk_config=self.pdk_config)
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
            self.table.setItem(r, 5, QTableWidgetItem(str(u["confidence"])))

        self.table.resizeColumnsToContents()

        self.details.setPlainText(
            f"Parsed MOSFETs: {self.results['mos_count']}\n"
            f"Parsed passives: {self.results['passive_count']}\n"
            f"Detected units: {len(units)}\n\n"
            f"PDK config: {self.results['pdk_config']['name']}\n\n"
            "Click a row to see explainable details.\n"
            "Click the (?) button for help on terms."
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
        for d in u.get("member_details", []):
            pins = d["pins"]
            size = f"w={d['w']} l={d['l']} m={d['m']} nf={d['nf']}"
            lines.append(
                f"  line {d['line_no']} {d['name']}: D={pins['d']} G={pins['g']} "
                f"S={pins['s']} B={pins['b']} model={d['model']} type={d['device_type']} {size}"
            )
        lines.append("")
        lines.append("Why detected:")
        for w in u["why_detected"]:
            lines.append(f"  - {w}")
        lines.append("")
        lines.append("Top checks:")
        for c in u["top_checks"]:
            lines.append(f"  - {c['name']}: sev={c['severity']:.2f} ({c['severity_label']}), observed={c['observed']}")
            lines.append(f"    expected: {c['expected']}")
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

    def export_json(self):
        if not self.results:
            QMessageBox.warning(self, "No results", "Run analysis before exporting.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export JSON",
            "unitwise_report.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)

    def export_html(self):
        if not self.results:
            QMessageBox.warning(self, "No results", "Run analysis before exporting.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export HTML Report",
            "unitwise_report.html",
            "HTML Files (*.html);;All Files (*)"
        )
        if not path:
            return

        rows = []
        for u in self.results["units"]:
            checks = "".join(
                "<li><b>{}</b>: {} ({})<br><small>Expected: {}</small></li>".format(
                    html.escape(c["name"]),
                    html.escape(str(c["observed"])),
                    html.escape(c["severity_label"]),
                    html.escape(str(c["expected"])),
                )
                for c in u.get("checks", [])
            )
            rows.append(
                "<section>"
                f"<h2>{html.escape(u['id'])} - {html.escape(u['type'])}</h2>"
                f"<p><b>Risk:</b> {u['risk']} &nbsp; <b>L:</b> {u['likelihood']} "
                f"<b>I:</b> {u['impact']} <b>C:</b> {u['confidence']}</p>"
                f"<p><b>Members:</b> {html.escape(', '.join(u['members']))}</p>"
                f"<pre>{html.escape(chr(10).join(d['raw'] for d in u.get('member_details', []) if d.get('raw')))}</pre>"
                f"<p>{html.escape(u['explanation'])}</p>"
                f"<h3>Why detected</h3><ul>{''.join('<li>' + html.escape(w) + '</li>' for w in u['why_detected'])}</ul>"
                f"<h3>Checks</h3><ul>{checks}</ul>"
                "</section>"
            )

        doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>UnitWise Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #222; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background: #f2f2f2; }}
    section {{ border-top: 2px solid #ddd; padding-top: 16px; margin-top: 20px; }}
    small {{ color: #555; }}
    pre {{ background: #f3f3f3; padding: 10px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>UnitWise Analog Weak-Point Report</h1>
  <p><b>Netlist:</b> {html.escape(self.results['netlist'])}</p>
  <p><b>PDK config:</b> {html.escape(self.results.get('pdk_config', {}).get('name', 'unknown'))}</p>
  <p><b>MOSFETs:</b> {self.results['mos_count']} &nbsp; <b>Passives:</b> {self.results['passive_count']} &nbsp; <b>Units:</b> {len(self.results['units'])}</p>
  {''.join(rows)}
</body>
</html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)

    def show_help(self):
        text = (
            "<b>How to read the table</b><br><br>"
            "<b>Risk</b>: Overall priority score (0..1). Higher = review first.<br>"
            "Computed as: <code>Risk = L * I * C</code><br><br>"

            "<b>L (Likelihood)</b>: How likely this unit is to fail or be fragile.<br>"
            "Based on explainable unit checks such as fanout, headroom, sizing, body ties, and symmetry.<br><br>"

            "<b>I (Impact)</b>: How much damage happens if this unit fails.<br>"
            "Estimated from dependency blast radius and unit type criticality.<br><br>"

            "<b>C (Confidence)</b>: How confident the tool is about detection and checks.<br>"
            "Lower confidence means the result is more uncertain, not necessarily safe.<br><br>"

            "<b>Tip</b>: Click a row to see detection evidence, top checks, device lines, and blast radius."
        )
        QMessageBox.information(self, "Help: Risk metrics", text)


def run():
    app = QApplication([])
    w = MainWindow()
    w.show()
    app.exec()
