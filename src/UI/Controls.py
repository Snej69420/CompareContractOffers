from pathlib import Path
from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import Qt, Signal, QSize

class TopBarControls(QWidget):
    loadRequested = Signal()
    analyzeRequested = Signal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10) # Added slight bottom margin for breathing room

        icon_dir = Path(__file__).parent.parent.parent / "assets"

        # --- Load Documents ---
        self.load_btn = QPushButton(" Offertes inladen")
        self.load_btn.setIcon(QIcon(str(icon_dir / "folder.svg")))
        self.load_btn.setIconSize(QSize(18, 18))
        self.load_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #f5f5f5; border-color: #bbbbbb; }
            QPushButton:pressed { background-color: #ebebeb; }
        """)
        self.load_btn.clicked.connect(self.loadRequested.emit)

        # --- Start Analysis (primary colour) ---
        self.run_btn = QPushButton(" Start analyse")
        # self.run_btn.setIcon(QIcon(str(icon_dir / "play.svg")))
        self.run_btn.setIconSize(QSize(18, 18))
        self.run_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #0069d9; }
            QPushButton:pressed { background-color: #0056b3; }
            QPushButton:disabled { background-color: #80bdff; color: #f8f9fa; }
        """)
        self.run_btn.clicked.connect(self.analyzeRequested.emit)

        # --- STATUS LABEL ---
        self.status_label = QLabel("Klaar voor gebruik.")
        self.status_label.setStyleSheet("color: #555555; font-style: italic; margin-left: 10px;")

        # Assemble the layout
        layout.addWidget(self.load_btn)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_analyze_enabled(self, enabled: bool):
        self.run_btn.setEnabled(enabled)