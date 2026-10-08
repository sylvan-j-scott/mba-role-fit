# Changelog

## 0.2.0 (2026-10-08)

- **One-page HTML report** (`scripts/report_html.py`, `templates/report.html`). Verdict up top,
  every role type or company as a dot strip, drill-down to best roles, records, gap words, and
  every posting in the group.
- **Big employers no longer set the bar.** The top-10% cutoff weights each company equally, and
  rows rank by how many companies have a reachable top-10% role.
- **Company boilerplate is filtered from gap words** (a word in 80%+ of one company's postings).
- **Registry grew from 33 to 128 boards.** New fetchers for Phenom, Oracle Recruiting Cloud, and
  Eightfold. Workday `myworkdaysite.com` hosts supported. Boards fetch in parallel (`--workers`)
  with retry on 429/5xx, and the archive saves after every board.
- **Consulting dropped as a discipline.** MBB and Big 4 boards are unreachable; users are sent to
  MBA Exchange instead.
- `reference/board-apis.md`: the vendor playbook for finding and adding job-board APIs.
