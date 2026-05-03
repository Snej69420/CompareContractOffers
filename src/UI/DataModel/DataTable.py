import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QColor
from src.UI.Settings import settings

class DataTableModel(QAbstractTableModel):
    """
    A reactive PySide6 Table Model for Pandas DataFrames.
    Supports MultiIndex headers and secondary DataFrames for color masking.
    """

    def __init__(self, data: pd.DataFrame, colors: pd.DataFrame = None):
        super().__init__()
        self._data = data
        # If no color mask is provided, create an empty one of the same shape
        if colors is not None:
            self._colors = colors
        else:
            self._colors = pd.DataFrame(False, index=data.index, columns=data.columns)

    def rowCount(self, parent=None) -> int:
        return self._data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        value = self._data.iloc[row, col]

        # --- 1. DISPLAY ROLE (Text & Numbers) ---
        if role == Qt.ItemDataRole.DisplayRole:
            is_tuple = isinstance(value, tuple)
            delta_str = ""
            base_val = value

            if is_tuple:
                base_val, delta = value
                sign = "+" if delta > 0 else ""
                delta_fmt = f"{float(delta):.{settings.decimals}f}".replace('.', ',')
                delta_str = f" ({sign}{delta_fmt})"

            if pd.isna(base_val) or base_val == "":
                return ""

            # THE STRING TRAP FIX: Try to cast it to a float just like ProductItem!
            try:
                # Convert comma to dot and parse to float
                float_val = float(str(base_val).replace(',', '.'))
                formatted = f"{float_val:.{settings.decimals}f}".replace('.', ',')
                return formatted + delta_str
            except (ValueError, TypeError):
                # If it fails (because it's a Name or Unit), just return the text
                return str(base_val) + delta_str

        # --- 2. ALIGNMENT ROLE ---
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignmentFlag.AlignCenter)

        # --- 3. BACKGROUND ROLE ---
        if role == Qt.ItemDataRole.BackgroundRole:
            color_val = self._colors.iloc[row, col]
            if isinstance(color_val, str) and color_val.startswith("#"):
                return QColor(color_val)

        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            # --- FLATTEN MULTI-INDEX COLUMNS FOR QT ---
            if orientation == Qt.Orientation.Horizontal:
                col_name = self._data.columns[section]
                if isinstance(col_name, tuple):
                    return "\n".join(str(x) for x in col_name)
                return str(col_name)

            # Vertical row numbers
            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section] + 1)
        return None