from pathlib import Path
import pandas as pd
from PySide6.QtCore import QThread, Signal, QObject

from src.Backend.scoring import ScoringEngine


class WorkerSignals(QObject):
    finished = Signal(object, object, object)
    error = Signal(str)


class AIWorker(QThread):
    """
    Background worker thread to load and compare Excel contracts without
    blocking the main GUI event loop.
    """

    def __init__(self, documents: dict[Path, pd.DataFrame], parent: QObject | None = None):
        super().__init__(parent)
        self.documents = documents
        self.signals = WorkerSignals()

    def run(self) -> None:
        """
        Executes the loading and matching process.
        This method runs in a separate thread.
        """
        try:
            #  Convert dictionary keys from Path to string (e.g. "DeCock.xlsx")
            string_keyed_docs = {path.name: df for path, df in self.documents.items()}

            #  Initialize the engine with the exact threshold we tuned
            matcher = ScoringEngine(threshold=0.40)

            #  Run the N-Document matching
            clusters, lookup, unmatched_dict = matcher.match(string_keyed_docs)

            #  Emit the dynamic results safely back to the main thread
            self.signals.finished.emit(clusters, lookup, unmatched_dict)
        except Exception as e:
            import traceback
            traceback.print_exc()
            # Emit the exception string to be handled by the UI
            self.signals.error.emit(str(e))