import pandas as pd
from pathlib import Path

class ContractLoader:
    """Handles reading and initial formatting of the contract templates."""

    @staticmethod
    def load_excel(file_path: Path, skiprows: int = 9) -> pd.DataFrame:
        df = pd.read_excel(file_path, skiprows=skiprows)
        df = df.dropna(subset=['Categorie', 'Naam']).reset_index(drop=True)
        # Ensure numeric columns are clean
        df['Aantal'] = pd.to_numeric(df['Aantal'], errors='coerce').fillna(0.0)
        return df
