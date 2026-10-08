---
name: mba-role-fit
description: Find where an MBA student fits in the job market. Builds an evidence bank from every resume version they have, pulls hundreds of real postings from public company job boards, sorts them into role shapes within PM, finance, marketing/brand, operations, and supply chain, and scores each shape against what their record can defend. Use when someone asks "what roles should I target", "where do I fit", "which kind of PM / brand / finance role", "which companies fit me in supply chain", "is there a role for me at X", or before rewriting a resume or LinkedIn for a search.
---

# MBA Role Fit

Most job searches pick a target, then look for evidence it was right. This flips it: **sample the
market, let role shapes emerge, then check which ones your record can defend.**

Think of it as customer segmentation where the population is jobs. You wouldn't pick a customer
segment on gut feel and then go find three customers who fit. You'd sample, cluster, size, and pick
one you can actually serve.

## The three questions this answers

Start every session by asking which one the user wants. Each has a fixed report.

| # | Question | Command |
|---|---|---|
| Q1 | **Where do I fit?** Every role type across all five disciplines in one ranking. For the marketer wondering about PM, strategy, or ops. | `score.py --question where` |
| Q2 | **In [discipline], which companies fit me best?** | `score.py --question companies --discipline supply-chain` |
| Q3 | **In [discipline], what kinds of roles exist, and which am I strongest for?** Also gives the gap words for the interview. | `score.py --question roles --discipline marketing` |

Disciplines: `product`, `finance`, `marketing`, `operations`, `supply-chain`.

**Consulting is not swept.** McKinsey, Bain, Deloitte, KPMG, and PwC block automated reads or have no
public feed, and consulting roles differ by case and staffing model more than by posting text, so
word-overlap fit says little. Send consulting recruiters to **MBA Exchange** (search by hand) and their
school's consulting club. If they also want a non-consulting read, run the five disciplines here.
All three run on the same archive and the same bank, so switching questions costs nothing.

## Two ideas everything follows from

**1. The unit is the ROLE, not the employer.** "Amazon is a logistics company" describes its center,
not its range. Amazon also runs Kindle, Audible, and Prime Video. P&G hires finance, supply chain,
and brand people with nothing in common. Filtering by company makes two errors: ruling out a company
that holds a pocket of roles that fit, and keeping a company that fits on paper but has no role of
your shape. Sweep the roles. Judge the roles.

**2. Discovery filters and evaluation filters are different tools.** A discovery filter is visible
from outside: the posting, the location policy, the title, whether the JD says "own the P&L." An
evaluation filter needs inside knowledge: manager quality, culture, whether people are respected.
Values exercises are almost all evaluation filters, so they can't narrow a search yet. Pull out the
few observable pieces and use only those now. The rest waits for interviews.

## Setup

Repo files live next to this SKILL.md (`$SKILL` below). The user's data lives in a separate
**workspace** folder they own. Default `~/role-fit-workspace`. Never put their data in the repo.

```
mkdir -p ~/role-fit-workspace/{resumes,manual}
cp $SKILL/templates/criteria.example.json ~/role-fit-workspace/criteria.json
```

Python 3.9+, standard library only. No installs. Scripts print counts and tables, never raw
postings. **Never read raw job JSON into the conversation;** parse it in a script.

---

## Pass 1. Build the evidence bank

Follow `reference/intake.md`. In short: collect **every resume version**, run `scripts/harvest.py`,
settle facts and conflicting numbers role by role, score each record, then ask round 1 of
**"What else can you claim?"**

This pass is required. Without a bank the method finds segments but can't say which ones the user
can defend, and it drifts into "apply to whatever is most common." If they want to skip it, say so
plainly and offer a 20-minute minimum: their current resume plus round 1 of the interview.

## Pass 2. Lock the criteria

Fill `workspace/criteria.json` with them. Before any data comes in:

1. **Core discipline and the sweep.** `core` is where they come from or expect to land (starred in Q1). Keep
   `disciplines` at all five by default: the sweep is cheap, and the report's **"Where else you fit"**
   table ranks every slice across all five together. That's how a marketer finds the growth-PM or
   internal-strategy pocket they'd never have searched for. Narrow only after a direction is clear.
2. **`max_years`.** Pre-MBA full-time years + 2. Higher stated minimums are marked out of reach, not removed.
3. **Location. Ask explicitly:** US only, international, anywhere, or specific places (e.g. Utah).
   Set `location.mode` to `us`, `us-strict`, `international`, `anywhere`, or `custom` with an
   `include` list (see the template). Applied when scoring, so it can change any time without
   re-fetching. Workday lists office names, not countries, so `us` keeps unplaceable postings and
   flags them; `custom` also checks the top of the description for the place name.
4. **Observable preferences only** (see idea 2).
5. **Stopping budget.** Usually 150-250 relevant postings. Decide now, before sunk cost.

## Pass 3. Choose companies and resolve boards

1. Show the companies already in `data/boards.json` (79: tech, CPG, retail, banks, healthcare, industrials).
2. **Ask for their list:** companies they're curious about, plus ones known for hiring their
   discipline. Push for 10-25. For finance, CPG brand, and supply chain, most big
   employers run **Workday** and need one pasted job URL each.
3. For each one not in the registry, follow `reference/find-the-board.md` (technical details in `reference/board-apis.md`). Save results to
   `workspace/my_boards.json`.
4. Set `companies` in criteria to `"all"` or their list.

If a discipline has fewer than ~40 postings after the sweep, it's under-sampled. Add companies, or
spend 20 minutes on MBA Exchange (by hand, see find-the-board.md) and save the best postings to `manual/`.

## Pass 4. Sweep

```
python3 $SKILL/scripts/fetch.py --workspace ~/role-fit-workspace
```

Pulls every board, keeps titles that match the chosen disciplines, fetches full descriptions,
and adds them to `postings.jsonl`. Re-runs are cheap (cached for 20 hours) and **build history**:
roles that close stay in the archive with `first_seen` / `last_seen` dates. Suggest re-running
every week or two during recruiting.

**Stopping rule. Count shapes, not listings.** A big employer may post 2,000 roles in 15 shapes.
The 200th listing adds a row and no information. If the budget is passed and new shapes keep
appearing, the discipline scope is too wide. Narrow it and say so. That's a finding.

## Pass 5. Answer the question

Run the command for their question (table above). Reports land in the workspace as
`report_where.md`, `report_companies_<discipline>.md`, `report_roles_<discipline>.md`.

Then build the page the user actually reads:

```
python3 $SKILL/scripts/report_html.py --workspace ~/role-fit-workspace
```

`report.html` is one self-contained file answering all three questions: a verdict up top, then
every role type or company as a row of dots on a fit scale, yellow where a role is both reachable
and in the top 10%. Clicking a row opens its best roles, the records they lean on, the words the
bank is missing, and **every posting in that group** ranked by fit with links (top 300 shown;
the rest are in `postings.jsonl`). Open it with `open ~/role-fit-workspace/report.html`.

Two corrections run automatically, so new companies need no setup:

- **Big employers can't set the bar.** The top-10% cutoff weights each company equally, and rows
  rank by how many *companies* have a reachable top-10% role. One employer with 1,000 postings
  can't push everyone else out of the top 10%.
- **Company boilerplate isn't a gap.** A word that appears in 80%+ of one company's postings
  (with 5 or more) is that company describing itself, like "payments" at Visa. It doesn't
  count toward that company's gap words.

Every report header states the location filter, how many roles each filter dropped, and warns when
one company is over 40% of the corpus. **Read that header out loud before any ranking.** A ranking
built on one employer describes that employer.

Three measures stay separate. **Never blend them into one score.** One blended number ranks word
overlap and calls it fit.

- **reach:** can they be hired into it (title level, stated minimum years)
- **fit:** how much of the bank's vocabulary the posting uses, weighted by record strength
- **axes:** what kind of work it is (owns a number, 0-to-1, plus discipline flags like client-facing)

**Slices are title patterns,** a starting grouping. Before recommending one, read 3-5 of its top
postings (pull bodies from `postings.jsonl` in a script, first 1,500 chars each). The same title
means different jobs at different companies. If a slice holds two shapes, say so.

Then:

1. **Size it.** Postings and companies. A slice living at one employer is a lottery ticket.
2. **Score against the bank.** Which records support it, which requirements have no record,
   what an interviewer would push on.
3. **After Q3, run round 2 of "What else can you claim?"** from the report's gap words
   (see intake.md). Update the bank, rerun.
4. **Report gaps as gaps.** Missing from the record is a fact about the record. Never write a
   framing over a gap to hide it.

Recommend one direction and argue for it. **The user picks.** The person whose career it is knows
things the bank doesn't.

Sample-size bands bind: n ≥ 100 medians are trustworthy, 40-99 directional, under 40 list roles
individually and say it's under-sampled.

## Pass 6. Hand off

Pull the chosen segment's 5-10 best postings (full text is already in `postings.jsonl`). Use them
to tailor the resume and LinkedIn from bank records. Mine the words they share. Every bullet must
trace to a record.

If the postings in the chosen segment still look scattered (no shared language, different jobs
under one name), the clustering was too loose. Go back to pass 5.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Every segment looks great | No bank, or pass 5 step 2 skipped | Score against records |
| Sweep never ends | Counting listings, not shapes | Stopping rule |
| One discipline has 6 postings | Registry is light there | Add Workday companies by pasted URL; MBA Exchange by hand |
| A company was ruled out early | Filtered by employer, not role | Sweep it anyway |
| A dream company yields nothing | Right company, no role of their shape | Real finding. Say so |
| Fit table ranks B2B tech roles top for a consumer person | Fit is word overlap | That's why axes stay separate. Check axes |
| Preferences don't narrow anything | They're evaluation filters | Keep only the observable ones |

## Privacy

`bank.json`, resumes, and postings stay in the user's workspace. Nothing is uploaded anywhere.
The scripts only call public job-board feeds. Never automate login-only sites.

## Credit

Method from a live run by Sylvan Scott (BYU MBA '27), Sept-Oct 2026. Both core ideas came from the
user pushing back on the analysis, not from the analysis.
