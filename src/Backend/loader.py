import pandas as pd
from pathlib import Path


class ContractLoader:
    def load_excel(self, file_path) -> pd.DataFrame:
        if isinstance(file_path, str):
            file_path = Path(file_path)

        # 1. Read the raw file without headers to find out where the table actually starts
        raw_df = pd.read_excel(file_path, header=None)

        table_start_row = -1

        # 2. Dynamically search for the header row
        for idx, row in raw_df.iterrows():
            # Convert row to a list of lowercase strings for easy searching
            row_vals = row.astype(str).str.lower().str.strip().tolist()

            # If we find our core columns in this row, we know it's the header!
            if 'naam' in row_vals and ('aantal' in row_vals or 'eenheid' in row_vals):
                table_start_row = idx
                break

        if table_start_row == -1:
            raise ValueError(f"Fout: Kon de tabelkop (met o.a. 'Naam' en 'Aantal') niet vinden in {file_path.name}.")

        # 3. --- Extract Metadata (Scan everything ABOVE the table) ---
        project_name = "Onbekend Project"
        contractor_name = file_path.stem

        metadata_df = raw_df.iloc[:table_start_row].fillna("")

        for _, row in metadata_df.iterrows():
            # Clean up the cells and filter out empty ones
            cells = [str(cell).strip() for cell in row.values if str(cell).strip()]

            # Slide through the cells to find Key-Value pairs
            for i in range(len(cells) - 1):
                label = cells[i].lower()
                value = cells[i + 1]

                if "werf" in label or "project" in label:
                    project_name = value
                elif "bedrijfsnaam" in label or "aannemer" in label or "contractant" in label:
                    contractor_name = value

        # 4. --- Load the Actual Data Table ---
        # Now we know exactly where the header is, we let pandas parse it properly!
        df = pd.read_excel(file_path, header=table_start_row)

        # Strip accidental whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]

        # 5. Clean up the data
        if 'Naam' in df.columns:
            # Drop rows where 'Naam' is empty (often artifacts of formatting at the bottom of sheets)
            df = df.dropna(subset=['Naam'])
            # Drop items where 'Naam' is just whitespace
            df = df[df['Naam'].astype(str).str.strip() != ""]

        # 6. Attach metadata
        df.attrs['project'] = str(project_name).strip()
        df.attrs['contractor'] = str(contractor_name).strip()

        return df