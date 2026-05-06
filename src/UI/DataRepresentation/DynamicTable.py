from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtCore import Qt
from src.UI.Settings import settings


class DynamicTable(QTableView):
    """
    A custom Table View that automatically scales its fonts, decimals,
    and column widths based on global AppSettings.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Standard table setup
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Wire up the global settings ONCE here!
        settings.decimalsChanged.connect(self._on_view_settings_changed)
        settings.fontSizeChanged.connect(self._on_view_settings_changed)

        # Apply initial styling
        self._apply_styles()

    def setModel(self, model):
        super().setModel(model)
        self._apply_layout()

    def _apply_layout(self):
        model = self.model()
        if not model: return

        header = self.horizontalHeader()

        # This tells columns to be only as wide as their content (ignores headers)
        self.resizeColumnsToContents()

        stretch_candidates = ['naam', 'omschrijving']
        compact_candidates = ['hoev', 'eh', 'ep', 'tot', '%']

        for i in range(model.columnCount()):
            col_name = str(model.headerData(i, Qt.Orientation.Horizontal)).lower()

            if any(c in col_name for c in stretch_candidates):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif any(c in col_name for c in compact_candidates):
                # ResizeToContents makes it as small as the numbers allow
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

    def _apply_styles(self):
        self.setStyleSheet(f"""
            QTableView {{
                font-size: {settings.font_size}pt;
                alternate-background-color: #f9f9f9;
                background-color: #ffffff;
            }}
            QHeaderView::section {{
                font-size: {settings.font_size}pt;
                font-weight: bold;
            }}
        """)

    def _on_view_settings_changed(self, _=None):
        """Safely updates fonts and decimals without destroying the table layout."""
        model = self.model()
        if not model:
            return

        # 1. Force the new font size
        self._apply_styles()

        # 2. Tell the model to safely recalculate decimals
        top_left = model.index(0, 0)
        bottom_right = model.index(model.rowCount() - 1, model.columnCount() - 1)
        model.dataChanged.emit(top_left, bottom_right)

        # 3. Resize columns to fit the new text
        self._apply_layout()