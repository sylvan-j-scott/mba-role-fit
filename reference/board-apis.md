# Job-board APIs: what works, learned the hard way

The technical companion to `find-the-board.md`. Read this when adding a company the registry
doesn't have, writing a new vendor function in `fetch.py`, or debugging a board that returns nothing.
Everything here was tested live on 2026-10-08 across ~150 large employers.

## The one trick that finds most boards

**Open one posting and look at its Apply link, not the page you're on.** Big employers put a branded
careers site (Phenom, Radancy/TalentBrew, Eightfold, Avature) in front of their real applicant
system. The apply button almost always points at the real one, usually Workday or Oracle, and
those have clean public JSON. Cisco, Mars, Citi, Bank of America, and PNC were all found this way.

## What large employers actually run

From the 2026-10 sweep of Fortune 500 and big MBA employers:

| Vendor | Share | How to spot it | Fetcher |
|---|---|---|---|
| **Workday** | about half | `{tenant}.wdN.myworkdayjobs.com/{site}` or `wdN.myworkdaysite.com/recruiting/{tenant}/{site}` | `workday` |
| **Phenom** | ~10% | `/widgets` calls in DevTools; often fronts Workday | `phenom` |
| **Oracle Recruiting Cloud** | ~10% | `*.oraclecloud.com/hcmUI/CandidateExperience/...` | `oracle` |
| iCIMS / Jibe | a few | `/api/jobs` on a careers subdomain (PepsiCo, Costco, ZS) | none yet |
| SuccessFactors, Avature, Eightfold, Taleo | a few | HTML-only or token-gated | none, go by hand |
| Greenhouse, Lever, Ashby | most startups and mid-size tech | in the URL | yes |
| Own site | Apple, Meta, Google, Microsoft, Amazon, most of MBB | no vendor in URL | special cases only |

Consulting (McKinsey, Bain, Deloitte, KPMG, PwC, EY) is almost entirely unreachable. That is why
the skill doesn't sweep consulting.

## Endpoints

All are no-login and were built for the company's own careers page to read.

**Workday**
- List: `POST https://{host}/wday/cxs/{tenant}/{site}/jobs` with body `{"appliedFacets":{},"limit":20,"offset":N,"searchText":""}`
- Detail: `GET https://{host}/wday/cxs/{tenant}/{site}{externalPath}` returns `jobPostingInfo.jobDescription`
- `host` is `{tenant}.{wd}.myworkdayjobs.com`, or `{wd}.myworkdaysite.com` for some tenants (Clorox, Mondelez). Set `host` in the registry entry for those.

**Phenom**
- List: `POST https://{host}/widgets` with body `{"lang":"en_us","deviceType":"desktop","country":"us","siteType":"external","pageName":"search-results","ddoKey":"refineSearch","from":N,"size":50,"jobs":true,"keywords":"","selected_fields":{}}` returns `refineSearch.data.jobs[]` and `refineSearch.totalHits`
- Detail: same URL with `"pageName":"job","ddoKey":"jobDetail","jobId":…,"jobSeqNo":…` returns `jobDetail.data.job.description`
- Check `applyUrl` on a job first. If it is Workday, register the Workday board instead: fewer calls, richer data.

**Oracle Recruiting Cloud**
- List: `GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={site},limit=100,offset=N,sortBy=POSTING_DATES_DESC` returns `items[0].requisitionList[]` and `items[0].TotalJobsCount`
- Detail: `GET …/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;Id="{Id}",siteNumber={site}` returns `ExternalDescriptionStr`, `ExternalResponsibilitiesStr`, and `ExternalQualificationsStr`
- `site` is usually `CX_1`, `CX_1001`, or similar; read it from the careers URL. Some companies use their own domain as host (Dell).

## Traps, all seen live

- **Workday counts cap at 2,000.** A `total` of exactly 2000 means "2,000 or more." `fetch.py` switches to per-term search on large boards.
- **Workday search is fuzzy OR.** "product manager" matches every product role and every manager role. Filter on titles after fetching; never trust search counts.
- **Never guess a Workday tenant or site.** Read both from a real URL. Agents that "remembered" tenants were sometimes right, but every one needs a live check.
- **Locale prefixes come in both cases.** `/en-US/` and `/en-us/` both appear before the site name. `find_board.py` handles both.
- **Boards are global and include hourly roles.** CVS, Kroger, Marriott, Costco, Lowe's, and Target are mostly store, warehouse, or hotel jobs. The title filter in `fetch.py` handles this. Never judge a board's value by its total count.
- **Mergers move boards.** Discover now redirects to Capital One's board. Check for redirects before registering a duplicate.
- **Same slug, different company** on Greenhouse and Lever (`bcg`, `linkedin`). Open one posting.
- **One company, several boards.** Unilever has separate experienced and early-career Workday sites. Pick the one MBA hires land on.
- **403, Cloudflare, or Akamai means stop.** Don't spoof, rotate, or log in. Record it under `not_found_yet` and point the user to manual saving.

## Etiquette

- Public, no-login feeds only. Never automate a site behind a school or personal login (MBA Exchange, LinkedIn).
- One board at a time per host. `fetch.py` runs boards in parallel but each board sequentially, with a 0.4s pause per request, and caches every response for 20 hours.
- Cap detail fetches per company (`--cap`, default 150). The title filter runs before any detail call.

## Adding a new vendor

1. Find the JSON call in DevTools → Network → Fetch/XHR on a search page.
2. Confirm it works with a plain request: no cookies, no tokens.
3. Write `def vendor(http, b, keep, terms, cap)` in `fetch.py`: list pages, then `keep(title)`, then detail calls up to `cap`, yielding `row(...)`. Copy `oracle()` as the template.
4. Add it to `VENDORS`, add a URL pattern and count check to `find_board.py`, and add the template string to `data/boards.json`.
5. **Build it only if it covers 3+ companies.** One-off custom sites cost more than saving 20 postings by hand.
