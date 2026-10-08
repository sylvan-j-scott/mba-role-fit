# Career intake: from resume versions to an evidence bank

The bank is what makes this skill different from browsing job boards. Without it you can find
segments but not tell which ones your record can defend. Build it first. It takes 45-90 minutes
and it is reusable for every resume, cover letter, and interview story afterward.

## Step 1. Collect every version

Ask for **every resume version they have**, not just the current one. Old ones, tailored ones,
the one for the consulting club, the LinkedIn export. Each version holds wording, numbers, and
details the others dropped. More versions = more raw material.

Put them in `workspace/resumes/`. `.docx`, `.txt`, `.md` work directly. For `.pdf`, `harvest.py`
uses `pdftotext` if installed. If not, read the PDF yourself and save its text as `.txt`.

Also accept: LinkedIn "About" and experience text, performance reviews, award write-ups,
a brag doc. Save each as `.txt` in the same folder.

## Step 2. Harvest

```
python3 scripts/harvest.py --workspace <ws>
```

It pulls every bullet, groups bullets that describe the same achievement across versions, and flags
groups where **the numbers disagree** ("grew revenue 30%" in one version, "35%" in another).
Read `harvest.json` in a script. Print cluster ids, version counts, and the longest variant only.

## Step 3. Settle the facts, one role at a time

Go role by role, not cluster by cluster. For each role, ask once:
"In one or two sentences: what did you own, how big was it (team, revenue, users), and who did you report to?"

Then for each cluster under that role, in order of how many versions use it:

1. Show the longest variant and any number conflict.
2. Ask: **"What actually happened?"** Plain words. Tell them not to polish.
3. For each number: **"How was it measured, over what window, and what else could explain it?"**
   If two versions disagree, ask which is right. Never pick for them.
4. Write the record (shape in `templates/bank.example.json`).

Ask two or three clusters per message, not twenty. Let them answer in fragments.

### Scoring each record (1-5)

| Score | Question |
|---|---|
| impact | How big was the result for the business? |
| defensibility | If an interviewer asks "how do you know?" three times, does it hold? **This is the gate.** |
| differentiation | Could most of their classmates claim the same thing? |
| recency | 5 = last 2 years, 1 = 8+ years ago |

Set `confidence` on every number: `verified` (they can show it), `estimated` (reasonable math),
`directional` (a model, a test, a guess). Directional numbers stay in, labeled as such.

### Keywords

5-12 per record, lowercase, in the words **a job posting would use**, not the words on the resume.
"Rewrote the onboarding emails" → `lifecycle marketing`, `email marketing`, `onboarding`,
`retention`, `crm`. These are what `score.py` matches against postings, so they decide fit.

## Step 4. "What ELSE can you claim?"

Resumes are lossy. Every version dropped things to fit one page. This interview gets them back.
Two rounds.

**Round 1, before the sweep. Prompts that recover what resumes cut:**

- What did you do that was never on any version because it didn't fit the story?
- What tools did you use weekly? (SQL, Excel models, Tableau, Figma, Salesforce, SAP, Python)
- What did you own a budget, a number, or a team for, even briefly or informally?
- What did you start that didn't exist before you?
- What would your old manager say you were the go-to person for?
- MBA so far: class projects with real companies, case competitions, club leadership, treks,
  consulting projects, TA roles. Each can be a record.
- Side projects, volunteering, a business you ran. Count them.
- Industry knowledge: which industries could you talk about for 20 minutes without notes?

**Round 2, after the first `score.py` run. Driven by the gaps.**

The report lists, per discipline, **words the postings use that the bank never does**, with the
share of postings using each. Turn the top 5-8 into questions:

> 41% of brand management postings mention "Nielsen" or syndicated data. Have you ever worked
> with market share data, retail scan data, or a panel, even in a class?

Ask in the posting's words, then listen for the experience under different words. A "yes" becomes
a new record (`source: "interview"`) or new keywords on an existing one. A "no" is useful too:
it's a real gap. Note it and move on.

Rerun `score.py` after round 2. The fit table usually moves.

## Rules

- **Never invent.** Every claim, number, and keyword traces to something they said or wrote.
- **Never write over a gap** to make it disappear. "Absent from the record" is a fact about the
  record. Report it as a gap.
- Their words go in `what_happened`. Resume language is for later.
- If a number's `how` is blank, the record's defensibility is at most 2.
- Keep `bank.json` private. It lives in their workspace, never in this repo.
