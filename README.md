# mba-role-fit

A Claude Code skill that shows an MBA student where they fit in the job market.

1. **Builds your evidence bank** from every resume version you have, then asks what else you can claim.
2. **Pulls hundreds of real postings** from public company job boards (no logins, no scraping).
3. **Sorts them into role shapes** across PM, finance, marketing/brand, operations, and supply chain.
4. **Scores each shape** against what your record can defend, and shows where else you fit
   and which companies post the most roles that suit you.

## Install

```
git clone https://github.com/<you>/mba-role-fit ~/.claude/skills/mba-role-fit
```

Then in Claude Code: *"Where do I fit? Use mba-role-fit."*

Needs Python 3.9+. No packages. `pdftotext` (from poppler) helps with PDF resumes but isn't required.

## What's inside

| Path | What |
|---|---|
| `SKILL.md` | The method, pass by pass |
| `reference/intake.md` | Resume versions → evidence bank, and the "what else can you claim" interview |
| `reference/find-the-board.md` | How to find any company's public job feed |
| `reference/board-apis.md` | Vendor endpoints and traps, for adding a company or a new vendor |
| `data/boards.json` | Job boards that ship with the skill. Add yours in your workspace |
| `disciplines/*.json` | Title patterns, slices, and vocabulary per discipline. Edit freely |
| `scripts/` | `harvest.py`, `find_board.py`, `fetch.py`, `score.py`, `report_html.py` |
| `templates/report.html` | The one-page report the user reads |

## Your data stays yours

Resumes, your bank, and postings live in a workspace folder outside this repo
(default `~/role-fit-workspace`). Nothing is uploaded. The scripts only read public job-board feeds.
Login-only sites like MBA Exchange are used by hand, never automated.

## Adding a discipline

Copy `disciplines/marketing.json`, change the title patterns, slices, and vocabulary. Pull requests welcome.
