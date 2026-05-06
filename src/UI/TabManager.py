from pathlib import Path
from PySide6.QtWidgets import QTabWidget, QTabBar
from PySide6.QtCore import Signal, QSize
from PySide6.QtGui import QIcon

from src.UI.Utils import get_asset_path
from src.UI.DataRepresentation.ComparisonTab import ComparisonTab
from src.UI.DataRepresentation.PreviewTab import PreviewTab
from src.UI.DataRepresentation.DocumentTab import DocumentTab


class MainTabWidget(QTabWidget):
    # Emits the Path object of the document that was closed by the user
    documentUnloaded = Signal(object)

    # Bubbles up the comparison state change to the main app
    stateChanged = Signal()

    def __init__(self):
        super().__init__()
        # Enable close buttons on tabs
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.handle_tab_close)

        # Initialize fixed tabs
        self.comparison_tab = ComparisonTab()
        self.preview_tab = PreviewTab()

        self.comparison_tab.stateChanged.connect(self.stateChanged.emit)
        self.currentChanged.connect(self.on_tab_changed)

        # Track active document tabs: { Path: DocumentTabWidget }
        self.doc_tabs = {}

        # Add fixed tabs (and remove their close buttons)
        self.add_fixed_tab(self.comparison_tab, "AI Vergelijking", "columns")
        self.add_fixed_tab(self.preview_tab, "Rapport Voorbeeld", "table")

        close_icon = get_asset_path("assets/close.svg")
        close_hover_icon = get_asset_path("assets/close-hover.svg")

        self.setStyleSheet(f"""
            QTabBar::close-button {{
                image: url({close_icon});
                subcontrol-position: right;
            }}
            QTabBar::close-button:hover {{
                background-color: rgba(255, 255, 255, 50); /* Optional: slight highlight */
                image: url({close_hover_icon});
            }}
        """)

    def add_fixed_tab(self, widget, title, icon):
        idx = self.addTab(widget, title)

        self.setTabIcon(idx, QIcon(get_asset_path(f"assets/{icon}.svg")))
        self.setIconSize(QSize(16, 16))

        # Hide the close button for these specific tabs
        self.tabBar().tabButton(idx, QTabBar.ButtonPosition.RightSide).deleteLater()
        self.tabBar().setTabButton(idx, QTabBar.ButtonPosition.RightSide, None)

    def add_document_tab(self, df, path: Path):
        """Adds a new document tab, preventing duplicates."""
        if path in self.doc_tabs:
            # If already loaded, just switch to it
            self.setCurrentWidget(self.doc_tabs[path])
            return


        doc_tab = DocumentTab(df, path.name)

        # Insert document tabs at the far left (index 0 or len of current docs)
        insert_idx = len(self.doc_tabs)
        idx = self.insertTab(insert_idx, doc_tab, f"{path.name}")

        self.setTabIcon(idx, QIcon(get_asset_path("assets/file.svg")))
        self.setIconSize(QSize(16, 16))

        self.doc_tabs[path] = doc_tab
        self.setCurrentIndex(idx)

    def handle_tab_close(self, index):
        """Handles the user clicking the 'X' on a document tab."""
        widget = self.widget(index)

        path_to_remove = None
        for path, tab_widget in self.doc_tabs.items():
            if tab_widget == widget:
                path_to_remove = path
                break

        if path_to_remove:
            self.removeTab(index)
            widget.deleteLater()
            del self.doc_tabs[path_to_remove]

            # Tell the main app to drop this from memory
            self.documentUnloaded.emit(path_to_remove)

    def on_tab_changed(self, index):
        if self.widget(index) == self.preview_tab:
            self.preview_tab.force_resize()