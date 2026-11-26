# Format notes

Personal portfolio demo. Fictional data. Not legal or billing advice.

## LEDES 1998B reader

Status: **structure checked on 2026-11-26 against the publisher's format page and sample file; field types, lengths and required-field rules not checked.**

### What was read, and how

| Source | Publisher | What it gave |
|---|---|---|
| Web page "LEDES 98B Format" (ledes.org/ledes-98b-format/), which names the format document "Ledes 1998B Format Rev 7-2014" | LEDES Oversight Committee | "LEDES 1998B is an ASCII, pipe delimited format containing 24 fields." The page says the format is not intended to change. |
| "Ledes98B Sample File Rev 7-2014" (.txt, linked from that page) | LEDES Oversight Committee | First line, header names and order, delimiter, terminator, date format, line types, number spellings, blank fields. |
| "Ledes 1998B Format Rev 7-2014" (.xls, linked from that page) | LEDES Oversight Committee | **Could not be read.** It is a binary spreadsheet; the fetch tool returned no text and direct download was blocked by the network proxy. |
| "LEDES 1998B Format Specifications", a vendor help page (success.mitratech.com) | an e-billing vendor, not the publisher | Field types and lengths, the line total formula, `IE` as a line type. Recorded below as third-party, not enforced. |

All reading was on 2026-11-26. The pages were read through a fetch tool that returns a model's answers about the page, not the raw bytes, so the sample file was checked by asking for its first line, header names, each field of each record, terminators and sums. It was not compared byte for byte.

### Checked against the publisher's page and sample file

| Point | Result | In the reader before? |
|---|---|---|
| First record is `LEDES1998B[]` | confirmed | yes |
| Second record is a header of field names, ending in `[]` | confirmed | yes |
| 24 fields, names and order as in the table below | confirmed, all 24 | yes, no corrections needed |
| Fields separated by `\|` | confirmed | yes |
| Every record ends with `[]` followed by a line break, nothing before the `[]` | confirmed | yes |
| Dates are `YYYYMMDD` | confirmed (`19990225`) | yes |
| Line types `F`, `E` and `IF` | confirmed in the sample | yes |
| Line type `IE` | **not in the sample**; listed only on the vendor page | accepted, unverified from the publisher |
| Units x unit cost + adjustment = line total | consistent with the sample (2.00 x 350 - 70 = 630) and stated on the vendor page | yes |
| Sum of line totals = invoice total | consistent with the sample (1684.45 and 1250) | yes |
| Fields may be blank: expense code on fee lines; task, activity and timekeeper fields on expense lines | confirmed | yes |
| An `IF` line may leave unit cost and all timekeeper fields blank | confirmed | yes |
| Numbers may be written `2.00`, `0.200`, `-70`, `1250.`, `289.5` | confirmed | read correctly; tests added |
| A file may hold several invoices, and line numbers may continue from one invoice to the next | confirmed (second invoice starts at line 6) | read correctly; test added |
| The format is ASCII | stated on the format page | **changed**: the writer now refuses non-ASCII text and the reader reports it as a format note (it still reads the file) |
| No quoting of fields | confirmed in the sample | yes |

Nothing in the field list, order, delimiter, terminator, date format or line types had to be corrected. The changes made were the ASCII handling and new tests for each checked point (`tests/test_readers.py`, the block marked "points checked against the publisher").

### Not checked, still assumptions

- Field data types, maximum lengths and which fields are mandatory. These are in the publisher's spreadsheet, which could not be opened. The vendor page gives, for example, 20 characters for most identifiers, 8 for `TIMEKEEPER_ID`, 30 for `TIMEKEEPER_NAME`, 2,000 for descriptions, two decimal places for units and totals and up to five for unit cost. The reader enforces none of these.
- `TIMEKEEPER_CLASSIFICATION` values. The sample file shows `PARTNR` and `ASSOC`. The publisher's current classification list is in a spreadsheet that could not be opened. The reader accepts any text. This project's synthetic files use `PT`, `AS` and `LA`, which are not checked against any list.
- Whether line breaks are allowed inside a record, and whether there is any way to escape `|` or `[]` in text. The reader removes line breaks inside a record; the writer refuses `|` and `[]` in text.
- `TIMEKEEPER_NAME` layout. The sample shows "Last, First". The reader takes the text as given.
- How `IE` differs from `IF`. The reader treats both as invoice-level adjustments. The writer writes every adjustment as `IF`.

### What the reader does

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

Field list, in order (24 fields, confirmed against the published sample file). The header must match these names exactly, ignoring case and surrounding spaces.

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

- It does not read LEDES 1998BI, 2000 or any XML variant.
- It does not check field lengths, decimal places, or which fields are mandatory.
- The format has no receipt flag, cost-to-firm or AI-assisted flag (none of the 24 fields carries them), so checks that need them report "not checked" for LEDES files rather than guessing.
- Apart from a file built to the shape of the published sample, it has only read synthetic files written by this project's own writer and by the independent held-out author.

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

Status: **code numbers and names checked on 2026-11-26 against a secondary source; counts checked against the publisher's pages; the publisher's spreadsheets could not be opened.**

- The code sets are published at utbms.com, which says it is hosted by the LEDES Oversight Committee. Its pages "ABA Litigation Codes", "ABA Activity Codes" and "ABA Expense Codes" say the original 1997 sets have 5 phases and 29 task codes, 11 activity codes and 24 expense codes. The lists themselves are in linked spreadsheets ("ABA UTBMS Litigation Codes 1997" and the like), which the fetch tool could not read.
- The code numbers and names in `data/utbms_sample_codes.json` were compared with the lists in the Wikipedia article "Uniform Task-Based Management System" (read 2026-11-26). All codes written from memory in the first version matched; the table was then completed to the full 1997 litigation set: L100 to L530 (34 entries), A101 to A111, E101 to E124. The counts match the publisher's pages.
- Not included: the revised activity and expense codes from 2013, other practice-area code sets, and the code definitions.
- The engine uses the code structure in two places: phase budgets group fee lines by the first two characters of the task code (`L3xx` is phase `L300`), and activity codes `A105` and `A102` are read as in-firm communication and research.
- A rule can ask for codes to be checked against the table (`check_against_sample_table`). It is off in every sample guideline, and when on it only raises a review-level finding, because the table covers one code set and was checked against a secondary source only.
