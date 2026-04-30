from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject

from src.Compare.loader import ContractLoader
from src.Compare.scoring import ScoringEngine


class WorkerSignals(QObject):
    finished = Signal(object, object, object, object)
    error = Signal(str)


class AIWorker(QThread):
    """
    Background worker thread to load and compare Excel contracts without
    blocking the main GUI event loop.
    """

    def __init__(self, path_a: Path | str, path_b: Path | str, parent: QObject | None = None):
        super().__init__(parent)
        self.path_a = path_a
        self.path_b = path_b
        self.signals = WorkerSignals()

    def run(self) -> None:
        """
        Executes the loading and matching process.
        This method runs in a separate thread.
        """
        try:
            loader = ContractLoader()
            # Loading data from paths
            contract_a = loader.load_excel(self.path_a)
            contract_b = loader.load_excel(self.path_b)

            # Initializing the scoring engine[cite: 1]
            matcher = ScoringEngine(threshold=0.4)

            # Retrieving the updated tuple from match()[cite: 1]
            clusters, lookup, unmatched_a, unmatched_b = matcher.match(contract_a, contract_b)

            # Emit results safely back to the main thread[cite: 1]
            self.signals.finished.emit(clusters, lookup, unmatched_a, unmatched_b)

        except Exception as e:
            # Emit the exception string to be handled by the UI[cite: 1]
            self.signals.error.emit(str(e))