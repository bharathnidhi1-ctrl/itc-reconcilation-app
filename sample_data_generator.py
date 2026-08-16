"""
sample_data_generator.py
=========================
Generates two synthetic CSV files — a Purchase Register (Books) and a
GSTR-2B Statement (Portal) — with deliberately engineered overlaps and
discrepancies so you can demo / test every branch of the reconciliation
engine:

    - Exact matches                      -> Tier 1
    - Minor rounding differences (<= ₹1) -> Tier 2
    - Invoice-number typos/format diffs  -> Tier 3 (fuzzy)
    - Invoices only in Books             -> Missing in GSTR-2B
    - Invoices only in GSTR-2B           -> Missing in Books
    - Large tax differences              -> Value Mismatches

Run: python sample_data_generator.py
Produces: sample_books.csv, sample_gstr2b.csv in the current directory.
"""

import random
import pandas as pd

random.seed(42)

VENDORS = [
    ("Sundaram Textiles Pvt Ltd", "33AACCS1234A1Z5"),
    ("Vishal Steel Traders", "27AAAFV5678B1Z2"),
    ("Kavin Electricals", "29AABCK4321C1Z8"),
    ("Om Sai Logistics", "24AAECO9988D1Z1"),
    ("Bharat Packaging Co", "33AAGFB1122E1Z9"),
    ("Sri Lakshmi Enterprises", "33AAKFS3344F1Z6"),
    ("Everest IT Solutions", "07AABCE7766G1Z3"),
    ("Coastal Freight Movers", "37AADCC2211H1Z7"),
]

books_rows = []
gstr2b_rows = []
invoice_seq = 1000


def next_invoice_no():
    global invoice_seq
    invoice_seq += 1
    return f"INV/{2025}/{invoice_seq}"


def add_row_pair(vendor, gstin, taxable, cgst, sgst, igst, date_str, scenario):
    """Adds a Books row and a corresponding (possibly altered) GSTR-2B row
    depending on the scenario."""
    inv_no = next_invoice_no()

    books_rows.append(
        {
            "GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": inv_no,
            "Invoice Date": date_str, "Taxable Value": taxable,
            "CGST": cgst, "SGST": sgst, "IGST": igst,
        }
    )

    if scenario == "exact":
        gstr2b_rows.append(
            {"GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": inv_no,
             "Invoice Date": date_str, "Taxable Value": taxable,
             "CGST": cgst, "SGST": sgst, "IGST": igst}
        )
    elif scenario == "tolerance":
        gstr2b_rows.append(
            {"GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": inv_no,
             "Invoice Date": date_str, "Taxable Value": taxable,
             "CGST": round(cgst + 0.50, 2), "SGST": round(sgst + 0.50, 2), "IGST": igst}
        )
    elif scenario == "fuzzy":
        # genuine character-level typo (not just punctuation/spacing, which
        # the cleaning step already normalizes away) so this truly requires
        # Tier 3 Levenshtein matching, e.g. INV/2025/1001 -> INV/2025/10O1
        digits = inv_no.split("/")[-1]
        typo_digits = digits[:-2] + random.choice("OQ") + digits[-1]  # swap one digit for a look-alike letter
        messy_no = inv_no.rsplit("/", 1)[0] + "/" + typo_digits
        gstr2b_rows.append(
            {"GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": messy_no,
             "Invoice Date": date_str, "Taxable Value": taxable,
             "CGST": cgst, "SGST": sgst, "IGST": igst}
        )
    elif scenario == "missing_in_2b":
        pass  # books row added above, no counterpart in portal
    elif scenario == "missing_in_books":
        # remove the books row we just added and add only to GSTR-2B
        books_rows.pop()
        gstr2b_rows.append(
            {"GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": inv_no,
             "Invoice Date": date_str, "Taxable Value": taxable,
             "CGST": cgst, "SGST": sgst, "IGST": igst}
        )
    elif scenario == "value_mismatch":
        gstr2b_rows.append(
            {"GSTIN": gstin, "Vendor Name": vendor, "Invoice Number": inv_no,
             "Invoice Date": date_str, "Taxable Value": round(taxable * 0.7, 2),
             "CGST": round(cgst * 0.7, 2), "SGST": round(sgst * 0.7, 2), "IGST": igst}
        )


SCENARIOS = (
    ["exact"] * 15
    + ["tolerance"] * 8
    + ["fuzzy"] * 6
    + ["missing_in_2b"] * 7
    + ["missing_in_books"] * 5
    + ["value_mismatch"] * 4
)
random.shuffle(SCENARIOS)

for scenario in SCENARIOS:
    vendor, gstin = random.choice(VENDORS)
    taxable = round(random.uniform(5000, 250000), 2)
    is_intra_state = gstin[:2] in ("33", "29", "24")  # crude demo heuristic
    if is_intra_state:
        cgst = round(taxable * 0.09, 2)
        sgst = round(taxable * 0.09, 2)
        igst = 0.0
    else:
        cgst = 0.0
        sgst = 0.0
        igst = round(taxable * 0.18, 2)
    month = random.randint(4, 6)
    day = random.randint(1, 28)
    date_str = f"2025-{month:02d}-{day:02d}"

    add_row_pair(vendor, gstin, taxable, cgst, sgst, igst, date_str, scenario)

books_df = pd.DataFrame(books_rows)
gstr2b_df = pd.DataFrame(gstr2b_rows)

books_df.to_csv("sample_books.csv", index=False)
gstr2b_df.to_csv("sample_gstr2b.csv", index=False)

print(f"Generated sample_books.csv  ({len(books_df)} rows)")
print(f"Generated sample_gstr2b.csv ({len(gstr2b_df)} rows)")
