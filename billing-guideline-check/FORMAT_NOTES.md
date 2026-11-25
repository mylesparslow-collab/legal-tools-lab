# Format notes

Personal portfolio demo. Fictional data. Not legal or billing advice.

## LEDES 1998B reader

Status: **implemented from memory, not checked against the published specification.**
The container this was built in has no network access, so the specification could not be consulted.
Treat every point below as an assumption. Check them against the published specification before reading a real file.

### What the reader assumes

File structure

- Plain text. A leading byte-order mark is ignored.
- The first record is the literal `LEDES1998B[]`.
- The second record is a header listing the field names.
- Every later record is one line item. Invoice-level values are repeated on every line item of that invoice.
- Fields are separated by the pipe character `|`.
- Every record, including the first and the header, ends with `[]`.
- Line breaks are not significant. The reader splits on `[]` and removes any carriage returns or line feeds inside a record.
- The last record must end with `[]`. A file that does not is refused.
- A file may hold more than one invoice. Lines are grouped by `INVOICE_NUMBER`.
- Text fields cannot contain `|` or `[]`. There is no escape mechanism that the reader knows of. The writer refuses such text.

Field list, in order (24 fields). The header must match these names exactly, ignoring case and surrounding spaces.

| # | Field | How the reader uses it |
|---|---|---|
| 1 | INVOICE_DATE | invoice date, `YYYYMMDD` |
| 2 | INVOICE_NUMBER | invoice id |
| 3 | CLIENT_ID | client id; must match the guideline file's `client_id` |
| 4 | LAW_FIRM_MATTER_ID | matter id; used to look up the matter record |
| 5 | INVOICE_TOTAL | declared invoice total |
| 6 | BILLING_START_DATE | `YYYYMMDD`, may be blank |
| 7 | BILLING_END_DATE | `YYYYMMDD`, may be blank |
| 8 | INVOICE_DESCRIPTION | free text |
| 9 | LINE_ITEM_NUMBER | integer, unique within the invoice |
| 10 | EXP/FEE/INV_ADJ_TYPE | `F` fee, `E` expense, `IF` and `IE` invoice-level adjustments |
| 11 | LINE_ITEM_NUMBER_OF_UNITS | hours for fees, quantity for expenses |
| 12 | LINE_ITEM_ADJUSTMENT_AMOUNT | signed amount, blank read as 0 |
| 13 | LINE_ITEM_TOTAL | line amount |
| 14 | LINE_ITEM_DATE | `YYYYMMDD` |
| 15 | LINE_ITEM_TASK_CODE | task code, may be blank |
| 16 | LINE_ITEM_EXPENSE_CODE | expense code, may be blank |
| 17 | LINE_ITEM_ACTIVITY_CODE | activity code, may be blank |
| 18 | TIMEKEEPER_ID | timekeeper id |
| 19 | LINE_ITEM_DESCRIPTION | narrative |
| 20 | LAW_FIRM_ID | read and ignored |
| 21 | LINE_ITEM_UNIT_COST | hourly rate for fees, unit cost for expenses |
| 22 | TIMEKEEPER_NAME | name as given; the reader does not split or reorder it |
| 23 | TIMEKEEPER_CLASSIFICATION | read as given (sample data uses `PT`, `AS`, `LA`) |
| 24 | CLIENT_MATTER_ID | read and ignored |

Values

- Dates are eight digits, `YYYYMMDD`.
- Numbers are plain decimals with a full stop, no currency symbol and no thousands separator. Anything else is refused.
- Numbers are read as `decimal.Decimal`. The reader does not enforce field lengths or a maximum number of decimal places.
- Line arithmetic assumed: `LINE_ITEM_NUMBER_OF_UNITS x LINE_ITEM_UNIT_COST + LINE_ITEM_ADJUSTMENT_AMOUNT = LINE_ITEM_TOTAL`, within one cent.
- Invoice arithmetic assumed: the sum of `LINE_ITEM_TOTAL` over the invoice's lines equals `INVOICE_TOTAL`, within one cent.
- Invoice-level adjustment lines (`IF`, `IE`) count toward the invoice total. No rule is applied to them and their units and unit cost may be blank.

### What the reader does not do

- It does not read LEDES 1998BI, 1998B-INTL, 2000 or any XML variant.
- It does not check field lengths, character sets, or which fields the specification makes mandatory.
- It does not know of any fields beyond the 24 above. The format has no receipt flag, cost-to-firm or AI-assisted flag, so checks that need them report "not checked" for LEDES files rather than guessing.
- It has been run only on the synthetic files in `data/invoices/`, which this project's own writer produced. Agreement between a reader and a writer built from the same memory is not evidence that either matches the specification.

## Plain CSV layout (this project's own)

One row per line item. UTF-8, comma separated, standard CSV quoting, header row required. Invoice-level columns repeat on every row and must agree within an invoice.

| Column | Required | Notes |
|---|---|---|
| invoice_id | yes | |
| invoice_date | yes | `YYYY-MM-DD` |
| client_id | yes | must match the guideline file |
| matter_id | yes | |
| invoice_total | yes | declared total |
| billing_start, billing_end | column yes, value optional | `YYYY-MM-DD` or blank |
| line_no | yes | integer, unique within the invoice |
| kind | yes | `fee`, `expense` or `adjustment` |
| date | yes | `YYYY-MM-DD` |
| timekeeper_id, timekeeper_name, classification | column yes | blank on expense rows |
| units | yes | hours for fees, quantity for expenses |
| rate | yes | hourly rate or unit cost |
| adjustment | no | blank read as 0 |
| amount | yes | line amount |
| task_code, activity_code, expense_code | column yes | value may be blank |
| narrative | yes | |
| receipt | no | `yes`, `no` or blank (unknown) |
| cost | no | what the firm paid for an expense; blank means unknown |
| ai_assisted | no | `yes`, `no` or blank (unknown); a flag from the time system |

Numbers follow the same rules as above: plain decimals, read as `decimal.Decimal`.

## UTBMS task, activity and expense codes

Status: **sample subset, unverified against the published code set.**

- `data/utbms_sample_codes.json` holds a subset of litigation task codes (L100 to L400 series), activity codes (A101 to A111) and expense codes (E101 to E124), with descriptions written from memory.
- The sample invoices use these codes so the data looks like e-billing data.
- The engine uses the code structure in two places: phase budgets group fee lines by the first two characters of the task code (`L3xx` is phase `L300`), and activity code `A105` and `A102` are read as in-firm communication and research.
- A rule can ask for codes to be checked against the sample table (`check_against_sample_table`). It is off in every sample guideline, and when on it only raises a review-level finding, because the table is incomplete and unverified.
