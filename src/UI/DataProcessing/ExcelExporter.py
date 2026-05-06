import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter


class ExcelExporter:
    NAME_WIDTH = 40
    NUMBER_WIDTH = 6
    UNIT_WIDTH = 4
    TOTAL_WIDTH = 8
    NOTES_WIDTH = 20
    def __init__(self, contract_names: dict[str, str]):
        self.contract_keys = list(contract_names.keys())
        self.contract_names = contract_names

        # Formatting styles
        self.yellow_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        self.header_font = Font(bold=True)

        # Alignments
        self.center_align = Alignment(horizontal="center", vertical="center")
        self.wrap_align = Alignment(vertical="center", wrap_text=True)  # Text wrap for names
        self.valign_top = Alignment(vertical="top")

        # Borders
        thin = Side(border_style="thin", color="000000")
        self.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def _safe_float(self, val) -> float:
        try:
            if isinstance(val, str): val = val.replace(',', '.')
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def export(self, norm_clusters: list[dict], norm_unmatched: list,
               filepath: str = "Tilia - Prjs VGL dakwerken.xlsx"):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Project Comparison"

        self._write_headers(ws)

        current_row = 3  # Data starts at row 3 (after 2 rows of headers)

        # 1. Included Clusters
        included_clusters = [c for c in norm_clusters if not c.get('is_excluded', False)]
        for cluster in included_clusters:
            current_row = self._write_cluster(ws, cluster, current_row)

        # 2. Unmatched Items (Treated identically thanks to normalizer)
        if norm_unmatched:
            ws.cell(row=current_row, column=1, value="ONGEKOPPELDE ITEMS").font = self.header_font
            current_row += 1
            for pseudo_cluster in norm_unmatched:
                # We just pass the pseudo_cluster directly now!
                current_row = self._write_cluster(ws, pseudo_cluster, current_row)

        # 3. Excluded Clusters
        excluded_clusters = [c for c in norm_clusters if c.get('is_excluded', False)]
        if excluded_clusters:
            current_row += 1
            ws.cell(row=current_row, column=1, value="ONGEVRAAGDE / BUITEN SCOPE").font = self.header_font
            current_row += 1
            for cluster in excluded_clusters:
                current_row = self._write_cluster(ws, cluster, current_row)

        wb.save(filepath)

    def _write_headers(self, ws):
        # --- 1. Shared 'Algemeen' Headers ---
        alg_header = ws.cell(row=1, column=1, value="ALGEMEEN")
        alg_header.font = self.header_font
        alg_header.alignment = self.center_align
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)

        for col in range(1, 4): ws.cell(row=1, column=col).border = self.border

        shared_headers = ["Naam", "Hoev", "EH"]
        for col_idx, header in enumerate(shared_headers, start=1):
            cell = ws.cell(row=2, column=col_idx, value=header)
            cell.font = self.header_font
            cell.border = self.border
            cell.alignment = self.center_align

        ws.column_dimensions['A'].width = self.NAME_WIDTH  # Naam
        ws.column_dimensions['B'].width = self.NUMBER_WIDTH  # Hoev
        ws.column_dimensions['C'].width = self.UNIT_WIDTH  # EH
        ws.column_dimensions['D'].width = 3  # Spacer

        # --- 2. Contractor Headers ---
        col_offset = 5
        contractor_headers = ["Naam", "Hoev", "EH", "EP", "Tot", "Notities"]

        for k in self.contract_keys:
            c_name = self.contract_names[k]

            header_cell = ws.cell(row=1, column=col_offset, value=c_name.upper())
            header_cell.font = self.header_font
            header_cell.alignment = self.center_align
            ws.merge_cells(start_row=1, start_column=col_offset, end_row=1, end_column=col_offset + 5)

            for col in range(col_offset, col_offset + 6): ws.cell(row=1, column=col).border = self.border

            for i, header in enumerate(contractor_headers):
                cell = ws.cell(row=2, column=col_offset + i, value=header)
                cell.font = self.header_font
                cell.border = self.border
                cell.alignment = self.center_align

            ws.column_dimensions[get_column_letter(col_offset)].width = self.NAME_WIDTH
            ws.column_dimensions[get_column_letter(col_offset + 1)].width = self.NUMBER_WIDTH
            ws.column_dimensions[get_column_letter(col_offset + 2)].width = self.UNIT_WIDTH
            ws.column_dimensions[get_column_letter(col_offset + 3)].width = self.NUMBER_WIDTH
            ws.column_dimensions[get_column_letter(col_offset + 4)].width = self.TOTAL_WIDTH
            ws.column_dimensions[get_column_letter(col_offset + 5)].width = self.NOTES_WIDTH

            col_offset += 6

    def _write_cluster(self, ws, cluster: dict, start_row: int) -> int:
        lists = cluster.get('items', cluster)
        max_len = max(len(lists.get(k, [])) for k in self.contract_keys)

        current_row = start_row
        for i in range(max_len):
            current_row = self._write_row(ws, lists, current_row, i)

        return current_row

    def _write_row(self, ws, lists: dict, row_idx: int, item_idx: int) -> int:
        quantities, units = [], []

        # Calculate shared general numbers (ignoring purely blank unmatched fillers)
        for k in self.contract_keys:
            items = lists.get(k, [])
            if item_idx < len(items) and not getattr(items[item_idx], 'is_unmatched_blank', False):
                quantities.append(self._safe_float(items[item_idx].qty))
                units.append(items[item_idx].unit)

        qty_consensus = len(set(quantities)) == 1 and len(quantities) == len(self.contract_keys)
        unit_consensus = len(set(units)) == 1 and len(units) == len(self.contract_keys)

        cell_a = ws.cell(row=row_idx, column=1, value="")
        cell_a.border = self.border
        cell_a.alignment = self.wrap_align

        cell_b = ws.cell(row=row_idx, column=2)
        cell_b.border = self.border
        cell_b.alignment = self.center_align
        if qty_consensus and quantities:
            cell_b.value = quantities[0]
        else:
            cell_b.fill = self.yellow_fill

        cell_c = ws.cell(row=row_idx, column=3)
        cell_c.border = self.border
        cell_c.alignment = self.center_align
        if unit_consensus and units:
            cell_c.value = units[0]
        else:
            cell_c.fill = self.yellow_fill

        col_offset = 5
        shared_qty_col_letter = "B"

        for k in self.contract_keys:
            items = lists.get(k, [])
            c_cells = [ws.cell(row=row_idx, column=col_offset + i) for i in range(6)]
            for c in c_cells: c.border = self.border

            c_cells[0].alignment = self.wrap_align
            c_cells[1].alignment = self.center_align
            c_cells[2].alignment = self.center_align
            c_cells[3].alignment = self.center_align
            c_cells[4].alignment = self.center_align
            c_cells[5].alignment = self.valign_top

            if item_idx < len(items):
                item = items[item_idx]

                # Apply yellow background if marked as missing/blank by the normalizer
                if getattr(item, 'is_missing', False):
                    for c in c_cells: c.fill = self.yellow_fill

                # Populate text/formulas only if it's not an unmatched pure-blank slot
                if not getattr(item, 'is_unmatched_blank', False):
                    qty = self._safe_float(item.qty)
                    ep = self._safe_float(item.raw_data.get('Eenheidsprijs', 0.0))

                    c_cells[0].value = item.name
                    c_cells[1].value = qty
                    c_cells[2].value = item.unit
                    c_cells[3].value = ep

                    c_qty_letter = get_column_letter(c_cells[1].column)
                    c_ep_letter = get_column_letter(c_cells[3].column)

                    formula = f"=IF(ISBLANK(${shared_qty_col_letter}{row_idx}), {c_qty_letter}{row_idx}, ${shared_qty_col_letter}{row_idx}) * {c_ep_letter}{row_idx}"
                    c_cells[4].value = formula

            col_offset += 6

        return row_idx + 1