from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtGui import QIcon, QCursor
from PySide6.QtCore import Qt, Signal, QSize

from src.UI.Utils import get_asset_path
from src.UI.Settings import settings
from src.UI.DataRepresentation.Shortcut import ShortcutDialog


class TopBarControls(QWidget):
    loadRequested = Signal()
    analyzeRequested = Signal()
    exportRequested = Signal()  # <-- New Signal for Export

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)


        # --- Load Documents ---
        self.load_btn = QPushButton(" Offertes inladen")
        self.load_btn.setIcon(QIcon(get_asset_path("assets/folder.svg")))
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
            }
            QPushButton:hover { background-color: #f5f5f5; border-color: #bbbbbb; }
            QPushButton:pressed { background-color: #ebebeb; }
        """)
        self.load_btn.clicked.connect(self.loadRequested.emit)

        # --- Start Analysis (primary colour) ---
        self.run_btn = QPushButton(" Start analyse")
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
            }
            QPushButton:hover { background-color: #0069d9; }
            QPushButton:pressed { background-color: #0056b3; }
            QPushButton:disabled { background-color: #80bdff; color: #f8f9fa; }
        """)
        self.run_btn.clicked.connect(self.analyzeRequested.emit)

        # --- Export to Excel ---
        self.export_btn = QPushButton(" Exporteer Excel")
        # Ensure you have an appropriate icon, fallback to text if missing
        self.export_btn.setIcon(QIcon(get_asset_path("assets/file-spreadsheet.svg")))
        self.export_btn.setIconSize(QSize(18, 18))
        self.export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
            QPushButton:disabled { background-color: #94d3a2; color: #f8f9fa; }
        """)
        self.export_btn.clicked.connect(self.exportRequested.emit)
        # Optional: Disable it initially until analysis is run
        self.export_btn.setEnabled(False)

        # --- STATUS LABEL ---
        self.status_label = QLabel("Klaar voor gebruik.")
        self.status_label.setStyleSheet("color: #555555; font-style: italic; margin-left: 10px;")

        layout.addWidget(self.load_btn)
        layout.addWidget(self.run_btn)
        layout.addWidget(self.export_btn)  # <-- Added to layout
        layout.addWidget(self.status_label)
        layout.addStretch()

        # ==========================================
        # --- VIEW CONTROLS (RIGHT SIDE) ---
        # ==========================================

        mini_btn_style = """
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 7px 10px; 
            }
            QPushButton:hover { background-color: #f5f5f5; border-color: #bbbbbb; }
            QPushButton:pressed { background-color: #ebebeb; }
        """
        view_icon_size = QSize(20, 20)

        # --- Info Button ---
        self.info_btn = QPushButton()
        self.info_btn.setIcon(QIcon(get_asset_path("assets/info.svg")))
        self.info_btn.setIconSize(view_icon_size)
        self.info_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.info_btn.setToolTip("Bekijk sneltoetsen")
        self.info_btn.setStyleSheet(mini_btn_style)
        self.info_btn.clicked.connect(self.show_shortcuts_info)
        layout.addWidget(self.info_btn)

        # Separator
        # sep1 = QFrame()
        # sep1.setFrameShape(QFrame.Shape.VLine)
        # sep1.setFrameShadow(QFrame.Shadow.Sunken)
        # sep1.setStyleSheet("color: #ccc; margin: 0px 5px;")
        # layout.addWidget(sep1)

        # --- Font Controls ---
        # btn_font_min = QPushButton()
        # btn_font_min.setIcon(QIcon(get_asset_path("assets/decrease-fontsize.svg")))
        # btn_font_min.setIconSize(view_icon_size)
        # btn_font_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # btn_font_min.setStyleSheet(mini_btn_style)
        # btn_font_min.clicked.connect(lambda checked=False: settings.adjust_font_size(-1))
        #
        # btn_font_plus = QPushButton()
        # btn_font_plus.setIcon(QIcon(get_asset_path("assets/increase-fontsize.svg")))
        # btn_font_plus.setIconSize(view_icon_size)
        # btn_font_plus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # btn_font_plus.setStyleSheet(mini_btn_style)
        # btn_font_plus.clicked.connect(lambda checked=False: settings.adjust_font_size(1))
        #
        # layout.addWidget(btn_font_min)
        # layout.addWidget(btn_font_plus)

        # Separator
        # sep2 = QFrame()
        # sep2.setFrameShape(QFrame.Shape.VLine)
        # sep2.setFrameShadow(QFrame.Shadow.Sunken)
        # sep2.setStyleSheet("color: #ccc; margin: 0px 5px;")
        # layout.addWidget(sep2)

        # --- Decimal Controls ---
        # btn_dec_min = QPushButton()
        # btn_dec_min.setIcon(QIcon(get_asset_path("assets/decrease-precision.svg")))
        # btn_dec_min.setIconSize(view_icon_size)
        # btn_dec_min.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # btn_dec_min.setStyleSheet(mini_btn_style)
        # btn_dec_min.clicked.connect(lambda checked=False: settings.adjust_decimals(-1))
        #
        # btn_dec_plus = QPushButton()
        # btn_dec_plus.setIcon(QIcon(get_asset_path("assets/increase-precision.svg")))
        # btn_dec_plus.setIconSize(view_icon_size)
        # btn_dec_plus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # btn_dec_plus.setStyleSheet(mini_btn_style)
        # btn_dec_plus.clicked.connect(lambda checked=False: settings.adjust_decimals(1))

        # layout.addWidget(btn_dec_min)
        # layout.addWidget(btn_dec_plus)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_analyze_enabled(self, enabled: bool):
        self.run_btn.setEnabled(enabled)

    def set_export_enabled(self, enabled: bool):
        self.export_btn.setEnabled(enabled)

    def show_shortcuts_info(self):
        dialog = ShortcutDialog(self)
        dialog.exec()