import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QColor


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
            # Tuples break pd.isna(), so check if it's a tuple first!
            is_tuple = isinstance(value, tuple)

            if not is_tuple and pd.isna(value):
                return ""

            delta_str = ""
            if is_tuple:
                value, delta = value
                sign = "+" if delta > 0 else ""
                delta_fmt = f"{float(delta):.4f}".rstrip('0').rstrip('.').replace('.', ',')
                delta_str = f" ({sign}{delta_fmt})"

            # Smart Belgian Float Formatting
            if isinstance(value, (float, int)):
                if value == int(value):
                    return str(int(value)) + delta_str
                formatted = f"{float(value):.4f}".rstrip('0').rstrip('.').replace('.', ',')
                return formatted + delta_str

            return str(value) + delta_str

        # --- 2. ALIGNMENT ROLE ---
        if role == Qt.ItemDataRole.TextAlignmentRole:
            # --- FIXED: Center everything horizontally and vertically ---
            return int(Qt.AlignmentFlag.AlignCenter)

        # --- 3. BACKGROUND ROLE (Highlighting Differences) ---
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