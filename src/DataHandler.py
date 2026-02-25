import os
import pandas as pd

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
        df_raw = pd.read_excel(file_path, header=None)

        metadata = self.parse_metadata(df_raw)
        metadata['Bestandsnaam'] = os.path.basename(file_path)

        header_row_idx = None
        for i, row in df_raw.iterrows():
            row_str = row.astype(str).tolist()
            if "Categorie" in row_str and "Totaal Prijs" in row_str:
                header_row_idx = i
                break

        if header_row_idx is None:
            raise ValueError(f"Could not find table headers in {file_path}")

        df_data = pd.read_excel(file_path, header=header_row_idx)

        df_data = df_data[df_data['Categorie'].notna()]
        df_data = df_data[df_data['Categorie'] != 'Totaal']

        cols_to_keep = [c for c in STANDARD_COLUMNS if c in df_data.columns]
        df_data = df_data[cols_to_keep]

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

        # 1. Create Master Index (Groups all unique items strictly by Align_Cat)
        master_dict = {}
        for c in contracts:
            df = c['data']
            if 'Align_Cat' in df.columns and 'Align_Naam' in df.columns:
                for _, row in df.iterrows():
                    cat = str(row['Align_Cat']).strip()
                    naam = str(row['Align_Naam']).strip()

                    if not cat or cat == 'nan' or not naam or naam == 'nan':
                        continue

                    if cat not in master_dict:
                        master_dict[cat] = []

                    if naam not in master_dict[cat] and naam not in ['Subtotaal', 'Eindtotaal']:
                        master_dict[cat].append(naam)

        master_rows = []
        for cat, items in master_dict.items():
            for naam in items:
                master_rows.append((cat, naam))
            master_rows.append((cat, 'Subtotaal'))
        master_rows.append(('Totaal', 'Eindtotaal'))

        df_master = pd.DataFrame(master_rows, columns=['Align_Cat', 'Align_Naam'])

        cat_spans = []
        if not df_master.empty:
            current_cat = df_master.iloc[0]['Align_Cat']
            start_row = 0
            for i in range(1, len(df_master)):
                val = df_master.iloc[i]['Align_Cat']
                if val != current_cat:
                    cat_spans.append((start_row, i - 1, current_cat))
                    current_cat = val
                    start_row = i
            cat_spans.append((start_row, len(df_master) - 1, current_cat))

        # 2. Setup Excel Writer
        try:
            writer = pd.ExcelWriter(output_path, engine='xlsxwriter')
            workbook = writer.book
            worksheet = workbook.add_worksheet("Vergelijking")
        except Exception as e:
            print(f"Could not create Excel writer: {e}")
            return

        fmt_bold = workbook.add_format({'bold': True})

        # CATEGORY MERGE FORMATS (Thick Left, Top, and Bottom borders to frame the left side of the box)
        fmt_merge_cat = workbook.add_format({
            'valign': 'vcenter', 'border': 1, 'left': 2, 'top': 2, 'bottom': 2,
            'bold': True, 'bg_color': '#F0F0F0', 'text_wrap': True
        })
        fmt_empty_cat = workbook.add_format({
            'valign': 'vcenter', 'align': 'center', 'border': 1, 'left': 2, 'top': 2, 'bottom': 2,
            'bg_color': '#E0E0E0', 'font_color': '#777777', 'text_wrap': True
        })

        fmt_header = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1})
        fmt_header_right = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3', 'border': 1, 'right': 2})

        # DYNAMIC BORDER FORMATS (1 = thin inside borders, 2 = thick outer bounding box borders)
        formats = {
            # Standard Data Rows
            'normal': workbook.add_format({'border': 1}),
            'normal_right': workbook.add_format({'border': 1, 'right': 2}),
            'normal_first': workbook.add_format({'border': 1, 'top': 2}),
            'normal_first_right': workbook.add_format({'border': 1, 'top': 2, 'right': 2}),

            # Currency Rows
            'currency': workbook.add_format({'border': 1, 'num_format': '€ #,##0.00'}),
            'currency_right': workbook.add_format({'border': 1, 'right': 2, 'num_format': '€ #,##0.00'}),
            'currency_first': workbook.add_format({'border': 1, 'top': 2, 'num_format': '€ #,##0.00'}),
            'currency_first_right': workbook.add_format(
                {'border': 1, 'top': 2, 'right': 2, 'num_format': '€ #,##0.00'}),

            # Empty/Missing Data Rows
            'empty': workbook.add_format(
                {'border': 1, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter', 'font_color': '#777777'}),
            'empty_right': workbook.add_format(
                {'border': 1, 'right': 2, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter',
                 'font_color': '#777777'}),
            'empty_first': workbook.add_format(
                {'border': 1, 'top': 2, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter',
                 'font_color': '#777777'}),
            'empty_first_right': workbook.add_format(
                {'border': 1, 'top': 2, 'right': 2, 'bg_color': '#E0E0E0', 'align': 'center', 'valign': 'vcenter',
                 'font_color': '#777777'}),

            # Subtotal Rows (Closes the bottom of the bounding box)
            'subtotal': workbook.add_format({'bold': True, 'border': 1, 'bottom': 2, 'bg_color': '#E8F4F8'}),
            'subtotal_right': workbook.add_format(
                {'bold': True, 'border': 1, 'bottom': 2, 'right': 2, 'bg_color': '#E8F4F8'}),
            'subtotal_currency': workbook.add_format(
                {'bold': True, 'border': 1, 'bottom': 2, 'bg_color': '#E8F4F8', 'num_format': '€ #,##0.00'}),
            'subtotal_currency_right': workbook.add_format(
                {'bold': True, 'border': 1, 'bottom': 2, 'right': 2, 'bg_color': '#E8F4F8',
                 'num_format': '€ #,##0.00'}),

            # Grand Total
            'total': workbook.add_format({'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'bg_color': '#D3D3D3'}),
            'total_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'right': 2, 'bg_color': '#D3D3D3'}),
            'total_currency': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'bg_color': '#D3D3D3', 'num_format': '€ #,##0.00'}),
            'total_currency_right': workbook.add_format(
                {'bold': True, 'border': 1, 'top': 2, 'bottom': 2, 'right': 2, 'bg_color': '#D3D3D3',
                 'num_format': '€ #,##0.00'}),
        }

        col_widths = {'Categorie': 18, 'Naam': naam_width if naam_width else 35, 'Eenheid': 10, 'Aantal': 10,
                      'Eenheidsprijs': 15, 'Totaal Prijs': 15, 'Opmerkingen': 30}

        DATA_START_ROW = 12
        col_offset = 0

        for i, contract in enumerate(contracts):
            df_data = contract['data'].copy()
            metadata = contract['metadata']

            if 'Categorie' in df_data.columns and 'Naam' in df_data.columns:
                df_data['Categorie'] = df_data['Categorie'].astype(str).str.strip()
                df_data['Naam'] = df_data['Naam'].astype(str).str.strip()

            if not df_data.empty and 'Align_Cat' in df_data.columns and 'Align_Naam' in df_data.columns:
                agg_funcs = {}
                for col in df_data.columns:
                    if col in ['Align_Cat', 'Align_Naam']: continue
                    if col in ['Aantal', 'Totaal Prijs']:
                        df_data[col] = pd.to_numeric(df_data[col], errors='coerce').fillna(0)
                        agg_funcs[col] = 'sum'
                    elif col == 'Eenheidsprijs':
                        df_data[col] = pd.to_numeric(df_data[col], errors='coerce').fillna(0)
                        agg_funcs[col] = 'mean'
                    elif col in ['Categorie', 'Naam']:
                        agg_funcs[col] = lambda x: ' | '.join(pd.unique([str(v) for v in x.dropna() if str(v).strip()]))
                    else:
                        agg_funcs[col] = lambda x: ' | '.join([str(v) for v in set(x.dropna()) if
                                                               str(v).strip() and str(v).lower() not in ['0.0', 'nan',
                                                                                                         'none']])

                df_data = df_data.groupby(['Align_Cat', 'Align_Naam'], as_index=False).agg(agg_funcs)

            df_aligned = pd.merge(df_master, df_data, on=['Align_Cat', 'Align_Naam'], how='left')
            df_aligned.fillna("", inplace=True)

            headers = [c for c in STANDARD_COLUMNS if c in df_aligned.columns]

            row_idx = 0
            worksheet.write(row_idx, col_offset, f"Contract {i + 1}", fmt_bold)
            row_idx += 1

            for k, v in metadata.items():
                worksheet.write(row_idx, col_offset, str(k) + ":", fmt_bold)
                worksheet.write(row_idx, col_offset + 1, str(v))
                row_idx += 1

            for c_idx, header in enumerate(headers):
                is_last_col = (c_idx == len(headers) - 1)
                fmt_h = fmt_header_right if is_last_col else fmt_header
                worksheet.write(DATA_START_ROW - 1, col_offset + c_idx, header, fmt_h)

                col_xl_idx = col_offset + c_idx
                if header == 'Opmerkingen':
                    non_empty = df_aligned['Opmerkingen'].astype(str).str.replace('0.0', '').str.strip()
                    if non_empty.eq("").all() or non_empty.empty:
                        worksheet.set_column(col_xl_idx, col_xl_idx, None, None, {'hidden': True})
                    else:
                        worksheet.set_column(col_xl_idx, col_xl_idx, col_widths['Opmerkingen'])
                else:
                    worksheet.set_column(col_xl_idx, col_xl_idx, col_widths.get(header, 15))

            data_values = df_aligned[headers].values
            align_names = df_aligned['Align_Naam'].values

            # Map out which rows are the START of a category box
            start_rows = {s[0] for s in cat_spans}

            cat_start_row_xl = None
            subtotal_cells = []

            for r_idx, row_data in enumerate(data_values):
                excel_row = DATA_START_ROW + r_idx
                naam_val = align_names[r_idx]

                is_subtotal = (naam_val == 'Subtotaal')
                is_total = (naam_val == 'Eindtotaal')
                is_first_row = r_idx in start_rows

                if not is_subtotal and not is_total and cat_start_row_xl is None:
                    cat_start_row_xl = excel_row

                for c_idx, header in enumerate(headers):
                    cell_val = row_data[c_idx]
                    col_xl = col_offset + c_idx
                    is_last_col = (c_idx == len(row_data) - 1)
                    is_currency = header in ['Eenheidsprijs', 'Totaal Prijs']
                    is_missing_data = str(cell_val).strip() == "" and not is_subtotal and not is_total

                    # Dynamically build the style key depending on where we are in the box
                    if is_total:
                        key = 'total_currency' if is_currency else 'total'
                        if is_last_col: key += '_right'
                    elif is_subtotal:
                        key = 'subtotal_currency' if is_currency else 'subtotal'
                        if is_last_col: key += '_right'
                    elif is_missing_data:
                        key = 'empty'
                        if is_first_row: key += '_first'
                        if is_last_col: key += '_right'
                    else:
                        key = 'currency' if is_currency else 'normal'
                        if is_first_row: key += '_first'
                        if is_last_col: key += '_right'

                    fmt = formats[key]

                    if is_missing_data:
                        worksheet.write(excel_row, col_xl, "-", fmt)
                        continue

                    if is_total:
                        if header == 'Totaal Prijs':
                            formula = "=" + "+".join(subtotal_cells) if subtotal_cells else "=0"
                            worksheet.write_formula(excel_row, col_xl, formula, fmt)
                        elif header == 'Categorie':
                            worksheet.write(excel_row, col_xl, 'Totaal', fmt)
                        elif header == 'Naam':
                            worksheet.write(excel_row, col_xl, 'Eindtotaal', fmt)
                        else:
                            worksheet.write(excel_row, col_xl, "", fmt)

                    elif is_subtotal:
                        if header == 'Totaal Prijs' and cat_start_row_xl is not None:
                            if excel_row - 1 >= cat_start_row_xl:
                                start_cell = xl_rowcol_to_cell(cat_start_row_xl, col_xl)
                                end_cell = xl_rowcol_to_cell(excel_row - 1, col_xl)
                                formula = f"=SUM({start_cell}:{end_cell})"
                            else:
                                formula = "=0"
                            worksheet.write_formula(excel_row, col_xl, formula, fmt)
                            subtotal_cells.append(xl_rowcol_to_cell(excel_row, col_xl))
                        elif header == 'Naam':
                            worksheet.write(excel_row, col_xl, 'Subtotaal', fmt)
                        else:
                            worksheet.write(excel_row, col_xl, "", fmt)

                    else:
                        if header == 'Totaal Prijs':
                            a_idx = headers.index('Aantal') if 'Aantal' in headers else -1
                            p_idx = headers.index('Eenheidsprijs') if 'Eenheidsprijs' in headers else -1
                            a_val = row_data[a_idx] if a_idx >= 0 else ""
                            p_val = row_data[p_idx] if p_idx >= 0 else ""

                            if str(a_val).strip() != "" and str(p_val).strip() != "":
                                a_cell = xl_rowcol_to_cell(excel_row, col_offset + a_idx)
                                p_cell = xl_rowcol_to_cell(excel_row, col_offset + p_idx)
                                worksheet.write_formula(excel_row, col_xl, f"={a_cell}*{p_cell}", fmt)
                            else:
                                worksheet.write(excel_row, col_xl, str(cell_val) if cell_val else "", fmt)
                        else:
                            try:
                                if header in ['Aantal', 'Eenheidsprijs']:
                                    worksheet.write_number(excel_row, col_xl, float(cell_val), fmt)
                                else:
                                    worksheet.write(excel_row, col_xl, str(cell_val) if cell_val else "", fmt)
                            except ValueError:
                                worksheet.write(excel_row, col_xl, str(cell_val), fmt)

                if is_subtotal:
                    cat_start_row_xl = None

            if 'Categorie' in headers:
                cat_col_idx = col_offset + headers.index('Categorie')
                for (start_r, end_r, _) in cat_spans:
                    span_cats = df_aligned['Categorie'].iloc[start_r:end_r]
                    unique_cats = pd.unique([str(c) for c in span_cats if str(c).strip() != ""])
                    display_cat = " / ".join(unique_cats) if len(unique_cats) > 0 else "-"

                    cat_fmt = fmt_empty_cat if display_cat == "-" else fmt_merge_cat

                    if end_r > start_r:
                        worksheet.merge_range(
                            DATA_START_ROW + start_r, cat_col_idx,
                            DATA_START_ROW + end_r, cat_col_idx,
                            display_cat, cat_fmt
                        )
                    else:
                        worksheet.write(DATA_START_ROW + start_r, cat_col_idx, display_cat, cat_fmt)

            col_offset += len(headers)
            worksheet.set_column(col_offset, col_offset, 2)
            col_offset += 1

        writer.close()
        return output_path