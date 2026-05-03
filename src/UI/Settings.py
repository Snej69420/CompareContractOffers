from PySide6.QtCore import QObject, Signal

class AppSettings(QObject):
    # These signals will broadcast the new values to the whole app
    fontSizeChanged = Signal(int)
    decimalsChanged = Signal(int)

    def __init__(self):
        super().__init__()
        self.font_size = 14
        self.decimals = 2

    def adjust_font_size(self, delta: int):
        self.font_size += delta
        # Don't let the font get too small or ridiculously large
        self.font_size = max(8, min(self.font_size, 24))
        self.fontSizeChanged.emit(self.font_size)

    def adjust_decimals(self, delta: int):
        self.decimals += delta
        # Don't let decimals go below 0
        self.decimals = max(0, min(self.decimals, 5))
        self.decimalsChanged.emit(self.decimals)

# The Singleton Instance: Every file will import THIS specific object
settings = AppSettings()