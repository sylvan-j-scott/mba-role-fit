#!/usr/bin/env python3
"""Find a company's public job board.

    python3 scripts/find_board.py "https://boards.greenhouse.io/duolingo/jobs/123"   # best: paste a job URL
    python3 scripts/find_board.py --name "Warby Parker"                              # fallback: try slugs

With a URL: reads the vendor and account straight from it, then confirms the board has jobs.
With a name: tries likely slugs on the four vendors that allow it (Greenhouse, Lever, Ashby,
SmartRecruiters). Workday tenants can NOT be guessed; ask for a job URL.

Prints one JSON line ready to paste into workspace/my_boards.json, or says what to try next.
"""
import argparse, json, re, sys, urllib.error, urllib.request

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/126.0 Safari/537.36', 'Accept': 'application/json'}

PATTERNS = [
    ('greenhouse', r'(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([\w-]+)'),
    ('greenhouse', r'[?&]gh_jid=\d+.*'),  # company site embedding Greenhouse; board name not in URL
    ('lever', r'jobs\.lever\.co/([\w.-]+)'),
    ('ashby', r'jobs\.ashbyhq\.com/([\w.%-]+)'),
    ('smartrecruiters', r'(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)'),
    ('rippling', r'ats\.rippling\.com/([\w-]+)'),
    ('bamboohr', r'([\w-]+)\.bamboohr\.com'),
    ('workday', r'([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)'),
    ('amazon', r'amazon\.jobs'),
]


def fetch(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    h = dict(UA, **({'Content-Type': 'application/json'} if data else {}))
    req = urllib.request.Request(url, data=data, headers=h, method='POST' if data else 'GET')
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'ignore'))


def count(vendor, b):
    """Number of open jobs on the board, or None if it doesn't resolve."""
    try:
        if vendor == 'greenhouse':
            return len(fetch(f"https://boards-api.greenhouse.io/v1/boards/{b['board']}/jobs").get('jobs', []))
        if vendor == 'lever':
            return len(fetch(f"https://api.lever.co/v0/postings/{b['board']}?mode=json"))
        if vendor == 'ashby':
            return len(fetch(f"https://api.ashbyhq.com/posting-api/job-board/{b['board']}").get('jobs', []))
        if vendor == 'smartrecruiters':
            return fetch(f"https://api.smartrecruiters.com/v1/companies/{b['board']}/postings?limit=1").get('totalFound', 0)
        if vendor == 'rippling':
            return len(fetch(f"https://api.rippling.com/platform/api/ats/v1/board/{b['board']}/jobs"))
        if vendor == 'bamboohr':
            return len(fetch(f"https://{b['board']}.bamboohr.com/careers/list").get('result', []))
        if vendor == 'workday':
            base = f"https://{b['tenant']}.{b['wd']}.myworkdayjobs.com/wday/cxs/{b['tenant']}/{b['site']}"
            return fetch(base + '/jobs', {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}).get('total', 0)
        if vendor == 'amazon':
            return fetch("https://www.amazon.jobs/en/search.json?result_limit=1").get('hits', 0)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError):
        return None


def from_url(url, company):
    for vendor, rx in PATTERNS:
        m = re.search(rx, url)
        if not m:
            continue
        if vendor == 'greenhouse' and not m.groups():
            return None, "Greenhouse embedded on the company's own site. Try --name with the company name."
        if vendor == 'workday':
            b = {'tenant': m.group(1), 'wd': m.group(2), 'site': m.group(3)}
        elif vendor == 'amazon':
            b = {}
        else:
            b = {'board': m.group(1)}
        return dict({'company': company or b.get('board') or b.get('tenant'), 'type': vendor}, **b), None
    return None, ("Vendor not recognized. It's a custom careers site. Options: (1) open the job page, "
                  "open DevTools > Network, filter Fetch/XHR, reload, and look for a JSON response "
                  "with the job list; (2) a paid aggregator such as jobdataapi.com; (3) save postings "
                  "by hand to workspace/manual/.")


def slugs(name):
    n = name.lower().replace('&', 'and')
    base = re.sub(r'[^a-z0-9 ]', '', n).split()
    out = [''.join(base), '-'.join(base), base[0] if base else '', ''.join(base) + 'inc', ''.join(base) + 'hq']
    return [s for i, s in enumerate(out) if s and s not in out[:i]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('url', nargs='?')
    ap.add_argument('--name', help='company name')
    a = ap.parse_args()
    if a.url:
        b, why = from_url(a.url, a.name)
        if not b:
            print(why)
            return
        n = count(b['type'], b)
        if n is None:
            print(f"Parsed {b['type']} but the board did not respond. Check the URL. {json.dumps(b)}")
        elif n == 0:
            print(f"Board resolves but has 0 open jobs (the company may have moved vendors). {json.dumps(b)}")
        else:
            print(f"FOUND {n} open jobs\n{json.dumps(b)}")
        return
    if not a.name:
        sys.exit('Give a job URL, or --name "Company".')
    hits = []
    for s in slugs(a.name):
        for vendor in ('greenhouse', 'lever', 'ashby', 'smartrecruiters'):
            b = {'company': a.name, 'type': vendor, 'board': s}
            n = count(vendor, b)
            if n:
                hits.append((n, b))
    if not hits:
        print(f"No public board found by guessing for {a.name}. Ask for one job-posting URL from "
              f"their careers site (Workday and custom sites can only be found that way).")
        return
    for n, b in sorted(hits, key=lambda x: -x[0]):
        print(f"{n:5d} jobs  {json.dumps(b)}")
    print("\nCHECK before saving: a guessed slug can belong to a different company with the same name "
          "(seen live: 'bcg' and 'linkedin' on Greenhouse were not those companies). Open one posting.")


if __name__ == '__main__':
    main()
