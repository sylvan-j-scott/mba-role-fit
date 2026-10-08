# Finding a company's job board

Technical details (endpoints, vendor shares, traps, adding a vendor) live in `board-apis.md`.

**Most companies rent their job board, and that software publishes every open role as public,
no-login JSON.** These feeds exist so the company's own careers page and job aggregators can read
them. You almost never need to scrape a careers page.

## The process, in order

1. **Check `data/boards.json` and `workspace/my_boards.json`.** If it's there, done.
2. **Ask the user for one job-posting URL** from the company's careers site. Not the careers home
   page: a single posting. Then:
   ```
   python3 scripts/find_board.py "<url>" --name "Company"
   ```
   The address bar usually names the vendor and the account:

   | In the URL | Vendor |
   |---|---|
   | `boards.greenhouse.io/{co}` or `job-boards.greenhouse.io/{co}` | Greenhouse |
   | `jobs.lever.co/{co}` | Lever |
   | `jobs.ashbyhq.com/{co}` | Ashby |
   | `jobs.smartrecruiters.com/{Co}` | SmartRecruiters |
   | `ats.rippling.com/{co}` | Rippling |
   | `{co}.bamboohr.com` | BambooHR |
   | `{tenant}.wd{N}.myworkdayjobs.com/{site}` | Workday (most large companies: CPG, banks, retailers, industrials) |
   | `wdN.myworkdaysite.com/recruiting/{tenant}/{site}` | Workday (alternate host) |
   | `*.oraclecloud.com/hcmUI/CandidateExperience/.../sites/{site}` | Oracle Recruiting Cloud |
   | branded careers site with `/widgets` calls | Phenom. **Check the posting's Apply link first**: it often points at the real Workday or Oracle board |
   | `amazon.jobs` | Amazon's own |
   | `?gh_jid=123` on the company's own domain | Greenhouse, embedded. Use step 3 |

3. **No URL handy? Guess:** `python3 scripts/find_board.py --name "Company"` tries likely slugs on
   Greenhouse, Lever, Ashby, SmartRecruiters. **Open one posting to confirm it's the right company.**
4. **Save it.** Append the printed JSON line to `workspace/my_boards.json` (a JSON list).
5. **Custom careers site** (no vendor in the URL; Google, Microsoft, Apple, most consulting firms
   and banks): try DevTools. Open a search results page, DevTools → Network → Fetch/XHR, reload,
   and look for a response holding the job list. If it is a plain GET or POST with no login, it
   can be added as a new vendor function in `fetch.py`. If not, use step 6 or 7.
6. **Paid aggregator fallback:** jobdataapi.com and similar services index many custom sites and
   return full descriptions. Costs money; worth it only for a long list of custom-site companies.
7. **By hand.** Search the site, copy each relevant posting into `workspace/manual/` as a `.md` file
   with `company:`, `title:`, `url:`, `posted:` lines at the top. `fetch.py` picks them up.

## Traps, all seen live

- **Never guess Workday.** Tenant and site names are unguessable. A guessing round resolved 1 of 6;
  pasted URLs resolved 6 of 6 in one message. Ask.
- **Workday search is fuzzy.** "product manager" matches anything with *product* OR *manager*.
  One board reported 2,000 hits. `fetch.py` filters on titles after the fact. Never trust its counts.
- **Same slug, different company.** `bcg` and `linkedin` on Greenhouse were sandboxes or other
  companies. Check one posting.
- **A board can resolve and be empty.** The company moved vendors. Find the new one.
- **One company, two boards.** Use the one with more and fresher roles.
- **Anti-bot sites aren't worth the fight.** If a site needs a full browser session or a login,
  go by hand.

## Login-only job sites (MBA Exchange, school job boards, LinkedIn)

**Never automate these.** They sit behind your school login, their terms restrict reuse, and their
robots.txt files block automated access. They are a **manual backup**: search by hand, open the
roles worth keeping, and save each one to `workspace/manual/` with `source: mba-exchange` (or
wherever it came from).

They are worth it for one thing the public boards lack: **recent history.** Public boards show only
what is open today. MBA Exchange keeps roughly the last 4 months, closed roles included, sorted
into MBA job families. If the public boards come up thin for a discipline, spend 20 minutes there
and save the 15-30 best matches.

Re-running `fetch.py` every week or two also builds history: the archive keeps every role it has
ever seen, with `first_seen` and `last_seen` dates.
