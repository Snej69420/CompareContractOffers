import pandas as pd
import random
import os

# Base items derived from your provided text
BASE_ITEMS = [
    ("Afdek Kelder", "Waterdichting Horizontaal", "m²", 970.25, 28.95),
    ("Afdek Kelder", "Waterdichting Verticaal", "m²", 107.00, 33.37),
    ("Afdek Kelder", "XPS-Isolatie", "m²", 970.25, 9.51),
    ("Afdek Gevel", "Dampscherm horizontaal", "m²", 457.86, 16.89),
    ("Afdek Gevel", "Thermische Isolatie", "m²", 457.86, 27.77),
    ("Afdek Gevel", "Waterdichting Horizontaal", "m²", 457.86, 38.12),
    ("Afdek Gevel", "Betonplex", "lm", 145.90, 28.83),
    ("Afdek 1e V", "Thermische isolatie", "m²", 1024.68, 24.81),
    ("Afdek 1e V", "Waterdichting horizontaal", "m²", 1024.68, 30.79),
]


def create_mock_contract(filename, site_name, price_multiplier=1.0, has_extra_col=False):
    """
    Creates an Excel file matching the specific structure of the user's template.
    """

    # 1. Build the Header Section (Rows 0-8)
    # Note: In the template, the value is in column F (index 5)
    header_rows = [
        ["Werf Info", "", "", "", "", "", ""],
        ["", "", "", "", "", "", ""],
        ["Werf Naam", "", "", "", "", site_name, ""],
        ["Werf Status", "", "", "", "", "In Uitvoering", ""],
        ["Straatnaam", "", "", "", "", "Voorbeeldstraat 123", ""],
        ["Postcode", "", "", "", "", "1000 Brussel", ""],
        ["", "", "", "", "", "", ""],  # Spacer
        ["", "", "", "", "", "", ""],  # Spacer
    ]

    # 2. Build the Table Header
    cols = ["Categorie", "Naam", "Eenheid", "Aantal", "Eenheidsprijs", "Totaal Prijs", "Opmerkingen"]
    if has_extra_col:
        cols.append("Interne Code")  # Test for extra column detection

    header_rows.append(cols)

    # 3. Build the Data Rows
    data_rows = []
    grand_total = 0

    for category, name, unit, qty, base_price in BASE_ITEMS:
        # Vary the price and quantity slightly per contract
        final_price = round(base_price * price_multiplier, 2)
        final_qty = round(qty * random.uniform(0.9, 1.1), 2)
        total_price = round(final_price * final_qty, 2)
        grand_total += total_price

        row = [category, name, unit, final_qty, final_price, total_price, ""]
        if has_extra_col:
            row.append(f"CODE-{random.randint(100, 999)}")

        data_rows.append(row)

    # 4. Build Footer
    footer_row = ["Totaal", "", "", "", "", grand_total, ""]
    if has_extra_col: footer_row.append("")
    data_rows.append(footer_row)

    # Combine all parts
    full_data = header_rows + data_rows

    # Create DataFrame (header=None because the header is inside the data grid)
    df = pd.DataFrame(full_data)

    # Save to Excel
    # We turn off the header and index because we manually built the structure
    df.to_excel(filename, header=False, index=False)
    print(f"✅ Generated: {filename}")


if __name__ == "__main__":
    # Create 3 variants
    create_mock_contract("../data/Contract_A_Suites.xlsx", "The Suites", price_multiplier=1.0)
    create_mock_contract("../data/Contract_B_Riverside.xlsx", "Riverside Project", price_multiplier=1.15)  # 15% more expensive
    create_mock_contract("../data/Contract_C_Brussels.xlsx", "Brussels Tower", price_multiplier=0.95,
                         has_extra_col=True)  # Cheaper + Extra Col

    print("\nDone! You can now load these 3 files into the Contract App.")