---
name: table-parsing
description: Activates when an asset pass is parsing a correlation matrix or demographics table
activates_on:
  - asset_pass
  - table
---

Table-parsing rules
===================

When the attached asset is a table image:

- Triangle notation ("women above diagonal, men below") — read the two halves as
  separate groups; cite the cell coordinates in the evidence quote.
- Significance stars (`*`, `**`, `***`) after a number are NOT part of the
  numeric value. Strip them before returning the coefficient.
- Table notes (italic rows beneath the table) often disambiguate N by gender;
  quote the exact note text when using it as evidence.
- If a table cell contains a range or a `±` standard error, return the point
  estimate in `value` and preserve the range in the evidence `quote`.
