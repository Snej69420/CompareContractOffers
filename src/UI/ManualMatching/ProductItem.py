from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QListWidget, QApplication
from PySide6.QtCore import Qt, QPoint

from src.UI.Utils import get_asset_path
from src.UI.ManualMatching.MatchItem import MatchItem
from src.UI.ManualMatching.ItemTooltip import ProductTooltip
from src.UI.Settings import settings

class ProductItem(QWidget):
    def __init__(self, match_item: MatchItem, eject_callback=None):
        super().__init__()
        self.match_item = match_item

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.name_lbl = QLabel(match_item.name)
        self.name_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name_lbl.setMinimumWidth(30)

        self.qty_lbl = QLabel(str(match_item.qty))
        self.qty_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        self.unit_lbl = QLabel(match_item.unit if match_item.unit else "-")
        self.unit_lbl.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)

        settings.decimalsChanged.connect(self.refresh_numbers)
        self.refresh_numbers()

        normal_path = get_asset_path("assets/close.svg")
        hover_path = get_asset_path("assets/close-hover.svg")

        self.eject_btn = QPushButton()
        self.eject_btn.setFixedSize(22, 22)
        self.eject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eject_btn.setToolTip("Verwijder uit Cluster")

        self.eject_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                /* Use 'image' instead of 'qproperty-icon' to match the Tab look */
                image: url({normal_path});
                width: 16px; 
                height: 16px;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 50); /* Matches your tab highlight */
                image: url({hover_path});
                border-radius: 3px;
            }}
        """)

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

        self.tooltip_widget = ProductTooltip(None)

    def _get_score_color(self, score: float) -> str:
        if score >= 0.70:
            return "#c8e6c9"  # Green
        elif score >= 0.40:
            return "#fff9c4"  # Yellow
        else:
            return "#ffcdd2"  # Red

    def refresh_numbers(self):
        """This runs when the widget is created AND whenever the +/- buttons are clicked."""
        fmt = f"{{:.{settings.decimals}f}}"

        try:
            val = float(str(self.match_item.qty).replace(',', '.'))
            formatted_qty = fmt.format(val)
        except (ValueError, TypeError):
            formatted_qty = str(self.match_item.qty)

        self.qty_lbl.setText(formatted_qty)

    def _is_single_selection(self):
        # Navigate to the parent list
        parent = self.parent()
        # Look for the QListWidget in the hierarchy
        while parent and not isinstance(parent, QListWidget):
            parent = parent.parent()

        if parent and isinstance(parent, QListWidget):
            return len(parent.selectedItems()) == 1
        return True  # Default to True if no list found

    def show_tooltip(self):
        width = self.width()
        score = self.match_item.current_score
        name = self.match_item.name

        self.tooltip_widget.update_content(name, score, width)
        global_pos = self.mapToGlobal(QPoint(0, self.height() + 5))

        screen = QApplication.screenAt(global_pos)
        if not screen:
            screen = QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        tooltip_height = self.tooltip_widget.height()

        if global_pos.y() + tooltip_height > screen_geo.bottom():
            item_top_global = self.mapToGlobal(QPoint(0, 0)).y()
            global_pos.setY(item_top_global - tooltip_height - 5)

        self.tooltip_widget.move(global_pos)
        self.tooltip_widget.show()
        self.tooltip_widget.adjustSize()

    def hide_tooltip(self):
        self.tooltip_widget.hide()

    def enterEvent(self, event):
        self.show_tooltip()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hide_tooltip()
        super().leaveEvent(event)