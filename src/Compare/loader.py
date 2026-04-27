import pandas as pd
from pathlib import Path


class ContractLoader:
    def load_excel(self, file_path) -> pd.DataFrame:
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # --- PASS 1: SCRAPE ONLY THE METADATA (Rows 1 to 9) ---
        header_data = pd.read_excel(file_path, nrows=9, header=None).fillna("")

        project_name = "Onbekend Project"
        contractor_name = file_path.stem

        for _, row in header_data.iterrows():
            # Convert the row into a clean list of strings
            cells = [str(cell).strip() for cell in row.values]

            # If the row has at least two columns, check the first column (the label)
            if len(cells) >= 2:
                label = cells[0].lower()
                value = cells[1]

                # Check for Project Name keywords
                if "werf naam" in label or "project" in label:
                    if value:
                        project_name = value

                # Check for Contractor Name keywords
                elif "bedrijfsnaam" in label or "aannemer" in label or "contractant" in label:
                    if value:
                        contractor_name = value

        # --- PASS 2: LOAD THE ACTUAL DATA (Skip the metadata) ---
        df = pd.read_excel(file_path, header=9)

        if 'Naam' in df.columns:
            df = df.dropna(subset=['Naam'])

        # --- ATTACH METADATA TO DATAFRAME ---
        df.attrs['project'] = str(project_name).strip()
        df.attrs['contractor'] = str(contractor_name).strip()
        print(f"HMMM: project: {str(project_name)}  contractor: {str(contractor_name)}")

        return df