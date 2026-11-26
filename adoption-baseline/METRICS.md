# Metric definitions

Definitions version 1.0. This file is the written definition for every number the tool reports.
If a definition changes, bump `DEFINITIONS_VERSION` in `baseline/__init__.py`; `compare` refuses
to compare baselines built on different versions.

Personal portfolio demo. Synthetic data. Not legal advice.

## Sources

- **Roster** (`roster.csv`). The only source of denominators. One row per person, or several rows
  with different `effective_from` dates when a person changed practice, office or role.
- **Usage exports.** Any CSV, read through a JSON column mapping into the canonical day table:
  `person_id, date, tool, feature, interactions`.
- **Survey responses.** Anonymous. Carry role, practice and office but no person id.

An **interaction** is whatever one unit in the export is: a row in an event log, or a count in a
daily summary. Interactions from different tools are not the same unit. Counts are compared
within a tool; "any approved tool" figures are about whether someone was active, not how much.

**Lawyers** are the roles listed in `lawyer_roles` in `data/config.json` (partner, counsel,
associate by default). Targets are about lawyers.

## The denominator rule

For each ISO week (Monday to Sunday), a person on the roster is **eligible** unless:

1. **Not yet started**: their start date is after the Sunday of that week.
2. **Left**: their end date is before the Monday of that week.
3. **On leave all week**: their leave periods cover every weekday, Monday to Friday, of that week.

Someone who starts on a Thursday, or is on leave Monday to Thursday, is eligible that week.
Only eligible people are in that week's denominator, and only eligible people can be in its
numerator. If someone on leave all week has logged usage, it is left out of that week and
counted under data quality.

People on the roster with no usage rows are in the denominator and count as zero. They are
never treated as missing.

## Grouping when someone moves

Weekly measures use the practice, office and role in effect on the Monday of each week (or on
the start date for a person who starts mid-week). A person who changes practice mid-period
counts under the old practice for earlier weeks and the new one for later weeks. Regular use
uses the latest week in its window. Period-end measures (any use in period, licences) use the
assignment in effect on the last day of the period.

## Measures

| Measure | Numerator | Denominator |
|---|---|---|
| **Weekly active, latest week** | Eligible people with at least one interaction with an approved tool in the last complete ISO week | Eligible people that week |
| **Weekly active, last 4 weeks** | Eligible person-weeks with at least one interaction, over the last 4 complete ISO weeks | Eligible person-weeks in those weeks. The `people` field gives the distinct people behind them |
| **Regular use** | People active in at least 3 of the last 4 weeks | People eligible in at least 3 of those 4 weeks. Nobody else could meet the test |
| **Any use in period** (activated) | People with at least one interaction in the whole period | People on the roster on the last day of the period |
| **Licensed** | - | People on the roster at period end whose licence flag for the tool is yes |
| **Unused licence** | Licensed people with no interaction with that tool in the last 30 days of the period | Licensed people. A sub-count shows how many of the unused were away for every working day of the window (on leave or not yet started) |
| **Per-tool weekly active** | As weekly active, counting only that tool | Eligible people who hold a licence for that tool |

The window sizes (4 weeks, 3 of 4, 30 days) are in `data/config.json`.

Use of a tool by someone without a licence for it counts towards "any approved tool" (they did
use it) but not towards any figure for that tool. The rows are flagged under data quality. See
"Who is counted in a per-tool figure" below.

### Who is counted in a per-tool figure

One rule for every figure about a named tool: **only people who hold that tool's licence are
counted**. That covers any use in period, weekly active, regular use, unused licences,
intensity, breadth and the per-feature counts. Figures for "any approved tool" count everyone in
the population, licensed or not.

So an unlicensed person's use of Assistant A appears in the any-tool figures, is flagged under
data quality (`usage_without_licence`), and appears in no Assistant A figure. The any-tool row
can therefore cover people who are in neither tool row, and the tool rows do not add up to it.

### Breadth

- **Who:** people of any role on the roster on the last day of the period, with at least one
  interaction in the window. For a named tool, licence holders for that tool only. For "any
  approved tool", everyone.
- **Window:** the last 4 complete ISO weeks of the period (`regular_use.window_weeks`).
- **What:** distinct features used per person. For a named tool, that tool's features. For any
  approved tool, features across all tools, where a feature is a (tool, feature) pair.

Reported as lower quartile, median and upper quartile, plus the share who used two or more
features. `breadth.features` in `baseline.json` gives the number of licence holders who used each
(tool, feature) pair in the window. Feature names come from the mapping file, so breadth is only
as good as the mapping.

### Intensity

- **Who and window:** the same as breadth. Any role, on the roster at period end, at least one
  interaction in the last 4 complete ISO weeks; licence holders only for a named tool.
- **What:** interactions per person in the window. For a named tool, interactions with that
  tool. For any approved tool, interactions with all tools added together, which mixes units
  (see Sources) and is shown for the shape of the distribution, not the level.

Reported as lower quartile, median, upper quartile, 90th percentile and mean, plus the share of
all interactions that comes from the top tenth of users. The mean is never shown without the
median. The maximum is not reported because it describes one person.

Because the per-tool population (licence holders on the roster at period end) is the same as
for "any use in period", the number of people in a per-tool intensity or breadth row can never
exceed that tool's any-use-in-period count. A test checks this.

Weekly active and regular use are different in one respect: they count each week's eligible
people, including someone who was active earlier and left before the period ended. Such a
person is in those weekly figures but not in the period-end figures.

Quartiles use linear interpolation between closest ranks (the same as
`statistics.quantiles(..., method="inclusive")`).

### Survey-versus-log gap

For a group and the survey week: the share of survey respondents in the group who ticked
Assistant A or Assistant B for "last 7 days", minus the logged weekly active rate for that
group in that week, in percentage points. By practice the group is lawyers; by role it is
everyone.

The two rates have different denominators (respondents, and everyone eligible). The gap mixes
over-claiming with non-response bias and cannot separate them. Respondents are not matched to
log records.

## Small-group suppression

This is a privacy choice, not a statistical one. A rate for three people says too much about
each of them.

- Any cell describing fewer than 5 people is withheld (`suppression_threshold` in the config,
  or `--min-group`).
- Complementary suppression: where the cells in a column add up to a published total, one
  hidden cell could be recovered by subtraction. Further cells, smallest first, are withheld
  until at least two are hidden and together they describe at least 5 people.
- It is applied column by column, so a group can be shown for one measure and withheld for
  another.
- Survey tallies under 5 are withheld. For single-choice questions the complementary rule
  applies too.
- A target or gate for a group under the threshold reports "cannot tell" and shows no numbers.
- Individual-level output is off by default. `baseline.json`, the CSVs and the HTML report
  contain no person ids, names or emails. `--include-individuals` and `--write-events` exist
  for people who are entitled to that data, and say so when used.

Limits of this approach are listed in the README.

## Targets and gates

Read from `data/targets.json`. Each is a measure, a population, a basis (`last_4_weeks`,
`latest_week` or `regular_use`) and a threshold. The status is one of:

- **pass**: the rate is at or above the threshold.
- **not yet**: the rate is below the threshold.
- **cannot tell**: any of these is true: the group has fewer people than `min_people`; the
  period has fewer complete weeks than the measure needs; a licensed tool has no usage rows at
  all; more than `max_unknown_user_row_share` of export rows could not be matched to the roster.

A gate with `each_practice` is evaluated separately for each listed practice.

The only comparison is with the firm's own targets. The tool makes no comparison with other
organisations.

## Change between periods

`compare` takes two `baseline.json` files. For each measure and group it shows both rates with
their numerators and denominators, and the change in percentage points. It **calls** a change
(up or down) only when:

1. both periods describe at least 30 people in the group (`compare.min_people`), and
2. the rate moved by at least 5 percentage points (`compare.min_change_points`).

Otherwise it says "no clear change" (big enough group, small movement), "too small to call"
(group under 30 in either period, whatever the movement) or "suppressed". No confidence
intervals or p-values are given: these are whole populations of modest size measured with known
gaps, and a p-value would suggest precision the data does not have. "Any use in period" is not
compared, because it accumulates with period length.

## Data quality counts

Each export row meets these checks in order; the first failure decides the reason:

| Order | Check | Outcome |
|---|---|---|
| 1 | Row is entirely blank | dropped: `blank_row` |
| 2 | User cell is blank | dropped: `missing_user` |
| 3 | Date does not fit any format listed in the mapping | dropped: `bad_date` |
| 4 | A count is not a whole number of zero or more | dropped: `bad_count` |
| 5 | All counts are zero | dropped: `zero_count` |
| 6 | Same dedupe key as an earlier row, same content | dropped: `duplicate` |
| 6 | Same dedupe key as an earlier row, different content | dropped: `conflicting_duplicate` (first row kept) |
| 7 | User matches nobody on the roster | dropped: `unknown_user` (rows, interactions and distinct identifiers counted) |
| 7 | User matches more than one roster entry | dropped: `ambiguous_user` |
| 8 | Date outside the period | dropped: `outside_period` |

Kept rows can also be counted as **repaired** (`identifier_repaired`: matched only after
ignoring case and spacing; `unmapped_feature`: feature not in the mapping, counted as "other")
or **flagged** (`usage_without_licence`, `usage_before_start_date`, `usage_after_end_date`).

For every source, rows read = rows kept + rows dropped. A test checks this.

Time zones: with `"timezone": "as_given"` the calendar date is taken as written in the export,
whatever offset the timestamp carries. With `"convert"` a timestamp that carries an offset is
moved to `target_utc_offset_minutes` first. Dates without an offset are always taken as written.
