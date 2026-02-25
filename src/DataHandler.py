import os
import pandas as pd
from jinja2.lexer import newline_re

STANDARD_COLUMNS = [
    'Categorie', 'Naam', 'Eenheid', 'Aantal',
    'Eenheidsprijs', 'Totaal Prijs', 'Opmerkingen'
]


class DataHandler:
    def __init__(self):
        self.contracts = []

    def parse_metadata(self, df):
        """Extracts key-value pairs from the top rows."""
        metadata = {}
        # Iterate top rows to find key-value pairs (columns 0 and 1)
        # We limit to first 10 rows to avoid scanning the whole file
        for i in range(len(df)):
            row = df.iloc[i].dropna().values
            if len(row) == 2:
                key = str(row[0]).strip().rstrip(':')
                val = str(row[1]).strip()
                metadata[key] = val
            if len(row) > 2:
                break
        return metadata

    def parse_contract(self, file_path):
        # 1. Read the full file to find headers and metadata
        df_raw = pd.read_excel(file_path, header=None)

        # 2. Extract Metadata (Top section of Excel)
        metadata = self.parse_metadata(df_raw)
        metadata['Bestandsnaam'] = os.path.basename(file_path)

        # 3. Find the Table Header Row (where 'Categorie' and 'Totaal Prijs' exist)
        header_row_idx = None
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).tolist()
            if "Categorie" in row_str and "Totaal Prijs" in row_str:
                header_row_idx = i
                break

        if header_row_idx is None:
            raise ValueError(f"Could not find table headers in {file_path}")

        # 4. Read Data Table
        df_data = pd.read_excel(file_path, header=header_row_idx)

        # Clean Data
        df_data = df_data[df_data['Categorie'].notna()]
        df_data = df_data[df_data['Categorie'] != 'Totaal']  # Remove totals if they exist as rows

        # Filter Columns
        cols_to_keep = [c for c in STANDARD_COLUMNS if c in df_data.columns]
        df_data = df_data[cols_to_keep]

        # Numeric cleanup for calculations/display
        numeric_cols = ['Aantal', 'Eenheidsprijs', 'Totaal Prijs']
        for col in numeric_cols:
            if col in df_data.columns:
                df_data[col] = pd.to_numeric(df_data[col], errors='coerce').fillna(0)

        text_cols = [c for c in df_data.columns if c not in numeric_cols]
        df_data[text_cols] = df_data[text_cols].fillna("")

        return {
            "metadata": metadata,
            "data": df_data
        }

    def load_files(self, file_paths):
        """Returns a list of contract dictionaries."""
        parsed_contracts = []
        for f in file_paths:
            try:
                contract = self.parse_contract(f)
                parsed_contracts.append(contract)
            except Exception as e:
                print(f"Error loading {f}: {e}")
        return parsed_contracts

    def export_contracts(self, contracts, output_path, naam_width=None):
        if not contracts:
            return

        from xlsxwriter.utility import xl_rowcol_to_cell

        # 1. Create Master Index (Preserving original order!)
        all_keys = []
        seen = set()
        for c in contracts:
            df = c['data']
            if 'Categorie' in df.columns and 'Naam' in df.columns:
                for _, row in df.iterrows():
                    key = (row['Categorie'], row['Naam'])
                    if key not in seen:
                        seen.add(key)
                        all_keys.append(key)

        # Rebuild keys with Subtotals per category and a Grand Total
        master_rows = []
        current_cat = None
        for cat, naam in all_keys:
            if current_cat is None:
                current_cat = cat
            elif cat != current_cat:
                # Close out previous category with a subtotal
                master_rows.append((current_cat, 'Subtotaal'))
                current_cat = cat
            master_rows.append((cat, naam))

        # Add subtotal for the final category
        if current_cat is not None:
            master_rows.append((current_cat, 'Subtotaal'))

        # Add the Grand Total row
        master_rows.append(('Totaal', 'Eindtotaal'))

        # Create Master DataFrame to drive alignment
        df_master = pd.DataFrame(master_rows, columns=['Categorie', 'Naam'])

        # 2. Setup Excel Writer
        try:
            writer = pd.ExcelWriter(output_path, engine='xlsxwriter')
            workbook = writer.book
            worksheet = workbook.add_worksheet("Vergelijking")
        except Exception as e:
            print(f"Could not create Excel writer: {e}")
            return

        # --- FORMATTING DICTIONARY ---
        fmt_bold = workbook.add_format({'bold': True})
        fmt_merge_cat = workbook.add_format({'valign': 'vcenter', 'border': 1, 'bold': True, 'bg_color': '#F0F0F0'})

        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        fmt_header_right = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'right': 2})

        # Base formats mapping
        formats = {
            'normal': workbook.add_format({'border': 1}),
            'normal_right': workbook.add_format({'border': 1, 'right': 2}),
            'currency': workbook.add_format({'border': 1, 'num_format': '€ #,##0.00'}),
            'currency_right': workbook.add_format({'border': 1, 'right': 2, 'num_format': '€ #,##0.00'}),
            'subtotal': workbook.add_format({'bold': True, 'border': 1, 'top': 2, 'bg_color': '#F5F5F5'}),
            'subtotal_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'right': 2, 'bg_color': '#F5F5F5'}),
            'subtotal_currency': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bg_color': '#F5F5F5', 'num_format': '€ #,##0.00'}),
            'subtotal_currency_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'right': 2, 'bg_color': '#F5F5F5', 'num_format': '€ #,##0.00'}),
            'total': workbook.add_format({'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'bg_color': '#E8E8E8'}),
            'total_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'right': 2, 'bg_color': '#E8E8E8'}),
            'total_currency': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'bg_color': '#E8E8E8', 'num_format': '€ #,##0.00'}),
            'total_currency_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'right': 2, 'bg_color': '#E8E8E8',
                 'num_format': '€ #,##0.00'}),
        }

        col_widths = {
            'Categorie': 18,
            'Naam': naam_width if naam_width else 35,
            'Eenheid': 10,
            'Aantal': 10,
            'Eenheidsprijs': 15,
            'Totaal Prijs': 15,
            'Opmerkingen': 30
        }

        # Calculate Merge Spans for Categorie
        cat_spans = []
        if not df_master.empty:
            current_cat = df_master.iloc[0]['Categorie']
            start_row = 0
            for i in range(1, len(df_master)):
                val = df_master.iloc[i]['Categorie']
                if val != current_cat:
                    cat_spans.append((start_row, i - 1, current_cat))
                    current_cat = val
                    start_row = i
            cat_spans.append((start_row, len(df_master) - 1, current_cat))

        # 3. Iterate Contracts and Write
        DATA_START_ROW = 12
        col_offset = 0

        for i, contract in enumerate(contracts):
            df_data = contract['data']
            metadata = contract['metadata']

            # -- ALIGN DATA --
            df_aligned = pd.merge(df_master, df_data, on=['Categorie', 'Naam'], how='left')

            # -- WRITE METADATA (Top Section) --
            row_idx = 0
            worksheet.write(row_idx, col_offset, f"Contract {i + 1}", fmt_bold)
            row_idx += 1

            for k, v in metadata.items():
                worksheet.write(row_idx, col_offset, str(k) + ":", fmt_bold)
                worksheet.write(row_idx, col_offset + 1, str(v))
                row_idx += 1

            # -- WRITE DATA TABLE --
            headers = df_aligned.columns.tolist()

            # Write Headers and enforce predefined column widths / Hiding logic
            for c_idx, header in enumerate(headers):
                is_last_col = (c_idx == len(headers) - 1)
                fmt_h = fmt_header_right if is_last_col else fmt_header
                worksheet.write(DATA_START_ROW - 1, col_offset + c_idx, header, fmt_h)

                col_xl_idx = col_offset + c_idx
                if header == 'Opmerkingen':
                    # Hide column entirely if there are no opmerkingen
                    non_empty = df_aligned['Opmerkingen'].dropna().astype(str).str.strip()
                    if non_empty.eq("").all() or non_empty.empty:
                        worksheet.set_column(col_xl_idx, col_xl_idx, None, None, {'hidden': True})
                    else:
                        worksheet.set_column(col_xl_idx, col_xl_idx, col_widths['Opmerkingen'])
                else:
                    width = col_widths.get(header, 15)
                    worksheet.set_column(col_xl_idx, col_xl_idx, width)

            # Write data rows cell by cell to apply strict formats AND formulas
            data_values = df_aligned.values

            cat_start_row_xl = None
            subtotal_cells = []

            for r_idx, row_data in enumerate(data_values):
                excel_row = DATA_START_ROW + r_idx
                naam_val = row_data[headers.index('Naam')]

                is_subtotal = (naam_val == 'Subtotaal')
                is_total = (naam_val == 'Eindtotaal')

                # Track where categories start for SUM formulas
                if not is_subtotal and not is_total and cat_start_row_xl is None:
                    cat_start_row_xl = excel_row

                for c_idx, header in enumerate(headers):
                    cell_val = row_data[c_idx]
                    col_xl = col_offset + c_idx
                    is_last_col = (c_idx == len(row_data) - 1)
                    is_currency = header in ['Eenheidsprijs', 'Totaal Prijs']

                    # Format selection
                    if is_total:
                        key = 'total_currency' if is_currency else 'total'
                    elif is_subtotal:
                        key = 'subtotal_currency' if is_currency else 'subtotal'
                    else:
                        key = 'currency' if is_currency else 'normal'
                    if is_last_col: key += '_right'
                    fmt = formats[key]

                    # Value/Formula writing
                    if is_total:
                        if header == 'Totaal Prijs':
                            formula = "=" + "+".join(subtotal_cells) if subtotal_cells else "=0"
                            worksheet.write_formula(excel_row, col_xl, formula, fmt)
                        elif header in ['Categorie', 'Naam']:
                            worksheet.write(excel_row, col_xl, str(cell_val) if pd.notna(cell_val) else "", fmt)
                        else:
                            worksheet.write(excel_row, col_xl, "", fmt)

                    elif is_subtotal:
                        if header == 'Totaal Prijs' and cat_start_row_xl:
                            start_cell = xl_rowcol_to_cell(cat_start_row_xl, col_xl)
                            end_cell = xl_rowcol_to_cell(excel_row - 1, col_xl)
                            formula = f"=SUM({start_cell}:{end_cell})"
                            worksheet.write_formula(excel_row, col_xl, formula, fmt)
                            subtotal_cells.append(xl_rowcol_to_cell(excel_row, col_xl))
                        elif header in ['Categorie', 'Naam']:
                            worksheet.write(excel_row, col_xl, str(cell_val) if pd.notna(cell_val) else "", fmt)
                        else:
                            worksheet.write(excel_row, col_xl, "", fmt)

                    else:  # Normal rows
                        if header == 'Totaal Prijs':
                            a_idx = headers.index('Aantal') if 'Aantal' in headers else -1
                            p_idx = headers.index('Eenheidsprijs') if 'Eenheidsprijs' in headers else -1

                            a_val = row_data[a_idx] if a_idx >= 0 else None
                            p_val = row_data[p_idx] if p_idx >= 0 else None

                            if pd.notna(a_val) and pd.notna(p_val) and str(a_val).strip() != "" and str(
                                    p_val).strip() != "":
                                a_cell = xl_rowcol_to_cell(excel_row, col_offset + a_idx)
                                p_cell = xl_rowcol_to_cell(excel_row, col_offset + p_idx)
                                worksheet.write_formula(excel_row, col_xl, f"={a_cell}*{p_cell}", fmt)
                            else:
                                worksheet.write(excel_row, col_xl, cell_val if pd.notna(cell_val) else "", fmt)
                        else:
                            worksheet.write(excel_row, col_xl, cell_val if pd.notna(cell_val) else "", fmt)

                if is_subtotal:
                    cat_start_row_xl = None  # Reset for next category

            # 1. Merge 'Categorie' cells vertically
            if 'Categorie' in headers:
                cat_col_idx = col_offset + headers.index('Categorie')
                for (start_r, end_r, cat_val) in cat_spans:
                    if end_r > start_r:
                        worksheet.merge_range(
                            DATA_START_ROW + start_r, cat_col_idx,
                            DATA_START_ROW + end_r, cat_col_idx,
                            cat_val, fmt_merge_cat
                        )
                    else:
                        worksheet.write(DATA_START_ROW + start_r, cat_col_idx, cat_val, fmt_merge_cat)

            # Move offset for the next contract and add a slim empty column as a visual spacer
            col_offset += len(headers)
            worksheet.set_column(col_offset, col_offset, 2)
            col_offset += 1

        writer.close()
        return output_path