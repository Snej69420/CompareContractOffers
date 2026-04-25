from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt

from src.UI.MatchItem import MatchItem

class ProductItem(QWidget):
    def __init__(self, match_item: MatchItem, eject_callback=None):  # Added callback
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.name_lbl = QLabel(match_item.name)
        self.qty_lbl = QLabel(str(match_item.qty))
        self.unit_lbl = QLabel(match_item.unit if match_item.unit else "-")

        # --- NEW: Eject Button ---
        self.eject_btn = QPushButton("✕")
        self.eject_btn.setFixedSize(22, 22)
        self.eject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eject_btn.setStyleSheet("background-color: transparent; color: #d32f2f; font-weight: bold; border: none;")
        self.eject_btn.setToolTip("Verwijder uit cluster (Naar Parking Lot)")

        if match_item.is_parked:
            # Neutral Styling for Parked Items (Hide Eject Button)
            neutral_style = "background-color: #f0f0f0; border-radius: 4px; padding: 4px; color: #555;"
            self.name_lbl.setStyleSheet(neutral_style)
            self.qty_lbl.setStyleSheet(neutral_style + " font-weight: bold;")
            self.unit_lbl.setStyleSheet(neutral_style)
            self.eject_btn.setVisible(False)
        else:
            # Semantic Colors
            name_color = self._get_score_color(match_item.current_score)
            self.name_lbl.setStyleSheet(f"background-color: {name_color}; border-radius: 4px; padding: 4px;")

            qty_color = "#c8e6c9" if match_item.is_qty_balanced else "#ffcdd2"
            self.qty_lbl.setStyleSheet(
                f"background-color: {qty_color}; border-radius: 4px; padding: 4px; font-weight: bold;")

            unit_color = "#c8e6c9" if match_item.is_unit_matched else "#ffcdd2"
            if match_item.unit in ['ff', '']: unit_color = "#fff9c4"
            self.unit_lbl.setStyleSheet(f"background-color: {unit_color}; border-radius: 4px; padding: 4px;")

            # Wire up the callback
            self.eject_btn.clicked.connect(lambda: eject_callback(match_item) if eject_callback else None)

        layout.addWidget(self.name_lbl, stretch=1)
        layout.addWidget(self.qty_lbl)
        layout.addWidget(self.unit_lbl)
        layout.addWidget(self.eject_btn)

    def _get_score_color(self, score: float) -> str:
        if score >= 0.70:
            return "#c8e6c9"  # Green
        elif score >= 0.40:
            return "#fff9c4"  # Yellow
        else:
            return "#ffcdd2"  # Red