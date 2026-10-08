#!/usr/bin/env python3
"""Pull job postings from public, no-login job boards into one archive.

    python3 scripts/fetch.py --workspace ~/role-fit-workspace

Reads   workspace/criteria.json     disciplines, companies
        data/boards.json            boards that ship with the skill
        workspace/my_boards.json    boards the user added (optional, same shape)
        workspace/manual/*.md|txt   postings saved by hand (MBA Exchange, LinkedIn, anywhere)
Writes  workspace/raw/              every raw response, cached so re-runs are free
        workspace/postings.jsonl    the archive. Re-running ADDS to it, so roles that close
                                    stay on file with first_seen / last_seen dates.

Only titles that match a chosen discipline get their full description fetched.
Location is NOT filtered here. The archive keeps every place; score.py applies the location
setting, so changing it never needs a re-fetch.
Prints counts only. Never prints raw job text.
"""
import argparse, concurrent.futures, glob, hashlib, html, json, os, re, sys, time
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from disciplines import load_disciplines, title_matches  # noqa: E402

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/126.0 Safari/537.36',
      'Accept': 'application/json'}
TODAY = time.strftime('%Y-%m-%d')


# ---------- http with a disk cache ----------
class Http:
    def __init__(self, rawdir, max_age_h):
        self.rawdir, self.max_age = rawdir, max_age_h * 3600
        os.makedirs(rawdir, exist_ok=True)

    def _path(self, key):
        return os.path.join(self.rawdir, hashlib.sha1(key.encode()).hexdigest()[:16] + '.json')

    def get(self, url, payload=None, as_text=False):
        key = url + (json.dumps(payload, sort_keys=True) if payload else '')
        p = self._path(key)
        if os.path.exists(p) and time.time() - os.path.getmtime(p) < self.max_age:
            raw = open(p, encoding='utf-8').read()
        else:
            hdr = dict(UA)
            data = None
            if payload is not None:
                data = json.dumps(payload).encode()
                hdr['Content-Type'] = 'application/json'
            req = urllib.request.Request(url, data=data, headers=hdr,
                                         method='POST' if data else 'GET')
            # Big boards (Workday especially) throw 429/5xx under load. Back off and retry, don't give up.
            for attempt in range(4):
                try:
                    raw = urllib.request.urlopen(req, timeout=40).read().decode('utf-8', 'ignore')
                    break
                except urllib.error.HTTPError as e:
                    if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                        raise
                    time.sleep(3 * 2 ** attempt)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(raw)
            time.sleep(0.4)
        return raw if as_text else json.loads(raw)


def text(h):
    """HTML (possibly double-escaped) -> plain text."""
    h = html.unescape(html.unescape(h or ''))
    h = re.sub(r'<(br|/p|/li|/h\d|/div)[^>]*>', '\n', h, flags=re.I)
    h = re.sub(r'<[^>]+>', ' ', h)
    return re.sub(r'[ \t]+', ' ', re.sub(r'\n\s*\n+', '\n\n', h)).strip()


def row(company, title, url, body, location='', posted='', dept='', vendor=''):
    return {'company': company, 'title': (title or '').strip(), 'url': url, 'body': body,
            'location': location or '', 'posted': (posted or '')[:10], 'dept': dept or '',
            'vendor': vendor}


# ---------- one function per vendor. Each yields rows for titles that pass `keep`. ----------
def greenhouse(http, b, keep, terms, cap):
    d = http.get(f"https://boards-api.greenhouse.io/v1/boards/{b['board']}/jobs?content=true")
    for j in d.get('jobs', []):
        if keep(j.get('title', '')):
            yield row(b['company'], j['title'], j.get('absolute_url', ''), text(j.get('content')),
                      (j.get('location') or {}).get('name', ''), j.get('updated_at', ''),
                      ', '.join(x.get('name', '') for x in j.get('departments') or []), 'greenhouse')


def lever(http, b, keep, terms, cap):
    for j in http.get(f"https://api.lever.co/v0/postings/{b['board']}?mode=json"):
        if not keep(j.get('text', '')):
            continue
        parts = [j.get('descriptionPlain', '')]
        for L in j.get('lists') or []:
            parts += [L.get('text', ''), text(L.get('content', ''))]
        parts.append(j.get('additionalPlain', ''))
        c = j.get('categories') or {}
        posted = time.strftime('%Y-%m-%d', time.gmtime(j['createdAt'] / 1000)) if j.get('createdAt') else ''
        yield row(b['company'], j['text'], j.get('hostedUrl', ''), '\n'.join(parts),
                  c.get('location', ''), posted, c.get('team', '') or c.get('department', ''), 'lever')


def ashby(http, b, keep, terms, cap):
    d = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{b['board']}")
    for j in d.get('jobs', []):
        if keep(j.get('title', '')):
            yield row(b['company'], j['title'], j.get('jobUrl', ''),
                      j.get('descriptionPlain') or text(j.get('descriptionHtml')),
                      j.get('location', ''), j.get('publishedAt', ''),
                      j.get('department', '') or j.get('team', ''), 'ashby')


def smartrecruiters(http, b, keep, terms, cap):
    base = f"https://api.smartrecruiters.com/v1/companies/{b['board']}/postings"
    n = 0
    for off in range(0, 2000, 100):
        d = http.get(f"{base}?limit=100&offset={off}")
        content = d.get('content') or []
        for j in content:
            if not keep(j.get('name', '')) or n >= cap:
                continue
            det = http.get(f"{base}/{j['id']}")
            sec = ((det.get('jobAd') or {}).get('sections') or {})
            body = '\n\n'.join(text((sec.get(k) or {}).get('text', ''))
                               for k in ('jobDescription', 'qualifications', 'additionalInformation'))
            loc = j.get('location') or {}
            n += 1
            yield row(b['company'], j['name'], det.get('postingUrl', ''), body,
                      ', '.join(x for x in (loc.get('city'), loc.get('region'), loc.get('country')) if x),
                      j.get('releasedDate', ''), (j.get('department') or {}).get('label', ''),
                      'smartrecruiters')
        if len(content) < 100:
            break


def rippling(http, b, keep, terms, cap):
    base = f"https://api.rippling.com/platform/api/ats/v1/board/{b['board']}/jobs"
    for j in http.get(base):
        if not keep(j.get('name', '')):
            continue
        det = http.get(f"{base}/{j['uuid']}")
        desc = det.get('description') or {}
        body = text(' '.join(desc.values()) if isinstance(desc, dict) else str(desc))
        wl = j.get('workLocation') or {}
        yield row(b['company'], j['name'], j.get('url', ''), body,
                  wl.get('label', '') if isinstance(wl, dict) else str(wl), '',
                  (j.get('department') or {}).get('label', ''), 'rippling')


def bamboohr(http, b, keep, terms, cap):
    base = f"https://{b['board']}.bamboohr.com/careers"
    for j in http.get(f"{base}/list").get('result', []):
        if not keep(j.get('jobOpeningName', '')):
            continue
        det = (http.get(f"{base}/{j['id']}/detail").get('result') or {}).get('jobOpening') or {}
        loc = j.get('location') or {}
        yield row(b['company'], j['jobOpeningName'], f"{base}/{j['id']}", text(det.get('description')),
                  ', '.join(x for x in (loc.get('city'), loc.get('state')) if x),
                  det.get('datePosted', ''), j.get('departmentLabel', ''), 'bamboohr')


def workday(http, b, keep, terms, cap):
    # searchText is fuzzy OR-matching, so its hit counts mean nothing. Filter on titles here.
    # Most tenants live on {tenant}.{wd}.myworkdayjobs.com; some on {wd}.myworkdaysite.com ('host').
    host = b.get('host') or f"{b['tenant']}.{b['wd']}.myworkdayjobs.com"
    base = f"https://{host}/wday/cxs/{b['tenant']}/{b['site']}"
    found = {}
    # Under ~2,500 jobs, one pass over the whole board is cheaper than 19 fuzzy searches that each
    # page through most of it anyway. Bigger boards fall back to per-term search.
    total = http.get(base + '/jobs', {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}).get('total', 0)
    plan = [('', total)] if total <= 2500 else [(q, 400) for q in terms]
    for q, stop in plan:
        for off in range(0, stop, 20):
            d = http.get(base + '/jobs', {"appliedFacets": {}, "limit": 20, "offset": off, "searchText": q})
            posts = d.get('jobPostings') or []
            for j in posts:
                if j.get('externalPath') and keep(j.get('title', '')):
                    found.setdefault(j['externalPath'], j)
            if len(posts) < 20:
                break
    for path, j in list(found.items())[:cap]:
        info = http.get(base + path).get('jobPostingInfo') or {}
        yield row(b['company'], j['title'], info.get('externalUrl', ''), text(info.get('jobDescription')),
                  j.get('locationsText', ''), info.get('startDate', ''), '', 'workday')


def amazon(http, b, keep, terms, cap):
    seen = set()
    for q in terms:
        for off in range(0, 300, 100):
            qs = urllib.parse.urlencode({'base_query': q, 'offset': off, 'result_limit': 100,
                                         'country': 'USA', 'sort': 'recent'})
            jobs = http.get(f"https://www.amazon.jobs/en/search.json?{qs}").get('jobs') or []
            for j in jobs:
                if j.get('id_icims') in seen or not keep(j.get('title', '')):
                    continue
                seen.add(j.get('id_icims'))
                body = '\n\n'.join(text(j.get(k, '')) for k in
                                   ('description', 'basic_qualifications', 'preferred_qualifications'))
                # business_category says which part of Amazon the role sits in. It is the field that
                # finds a consumer-content pocket inside a logistics company.
                yield row(b['company'], j['title'], 'https://www.amazon.jobs' + (j.get('job_path') or ''),
                          body, j.get('normalized_location', '') or j.get('location', ''),
                          j.get('posted_date', ''), j.get('business_category', '') or j.get('job_category', ''),
                          'amazon')
            if len(jobs) < 100:
                break


def phenom(http, b, keep, terms, cap):
    """Phenom career sites (careers.{co}.com/widgets). One list pass over the US board, then a detail
    call per kept title. Many Phenom sites front a Workday or Oracle board; prefer those when known."""
    base = dict(lang='en_us', deviceType='desktop', country='us', siteType='external')
    url = f"https://{b['host']}/widgets"
    found = {}
    for off in range(0, 5000, 50):
        d = http.get(url, dict(base, pageName='search-results', ddoKey='refineSearch', size=50, jobs=True,
                               keywords=b.get('keywords', ''), selected_fields={}, sortBy='', subsearch='',
                               clearAll=False, jdsource='facets', isSliderEnable=False, locationData={},
                               counts=False, **{'from': off}))
        jobs = ((d.get('refineSearch') or {}).get('data') or {}).get('jobs') or []
        for j in jobs:
            if keep(j.get('title', '')):
                found.setdefault(j['jobSeqNo'], j)
        if len(jobs) < 50:
            break
    for seq, j in list(found.items())[:cap]:
        dd = http.get(url, dict(base, pageName='job', ddoKey='jobDetail', jobId=j.get('jobId'), jobSeqNo=seq))
        job = ((dd.get('jobDetail') or {}).get('data') or {}).get('job') or {}
        yield row(b['company'], j['title'], f"https://{b['host']}/us/en/job/{j.get('jobId')}",
                  text(job.get('description', '')), j.get('location', ''), j.get('postedDate', ''),
                  j.get('category', ''), 'phenom')


def oracle(http, b, keep, terms, cap):
    """Oracle Recruiting Cloud (…/hcmRestApi). Public list + detail endpoints, no login."""
    api = f"https://{b['host']}/hcmRestApi/resources/latest"
    found = {}
    for off in range(0, 5000, 100):
        d = http.get(f"{api}/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;"
                     f"siteNumber={b['site']},limit=100,offset={off},sortBy=POSTING_DATES_DESC")
        items = (d.get('items') or [{}])[0]
        reqs = items.get('requisitionList') or []
        for j in reqs:
            if keep(j.get('Title', '')):
                found.setdefault(j['Id'], j)
        if len(reqs) < 100 or off + 100 >= (items.get('TotalJobsCount') or 0):
            break
    for jid, j in list(found.items())[:cap]:
        x = (http.get(f'{api}/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;'
                      f'Id=%22{jid}%22,siteNumber={b["site"]}').get('items') or [{}])[0]
        body = '\n\n'.join(text(x.get(k)) for k in
                            ('ExternalDescriptionStr', 'ExternalResponsibilitiesStr', 'ExternalQualificationsStr'))
        yield row(b['company'], j['Title'],
                  f"https://{b['host']}/hcmUI/CandidateExperience/en/sites/{b['site']}/job/{jid}",
                  body, j.get('PrimaryLocation', ''), j.get('PostedDate', ''), j.get('JobFamily', ''), 'oracle')


def eightfold(http, b, keep, terms, cap):
    """Eightfold career sites (Microsoft, Starbucks, Netflix). Boards are huge and mostly hourly at
    some companies, so search per discipline term like Amazon. Newer sites answer /api/pcsx/*, older
    ones /api/apply/v2/*; try pcsx and fall back."""
    host, dom = b['host'], b['domain']
    api = b.get('api', 'pcsx')
    found = {}
    for q in terms:
        start = 0
        while start < 300:
            qs = urllib.parse.urlencode({'domain': dom, 'query': q, 'start': start, 'num': 50, 'location': b.get('location', 'United States')})
            try:
                d = http.get(f"https://{host}/api/{'pcsx/search' if api == 'pcsx' else 'apply/v2/jobs'}?{qs}")
            except urllib.error.HTTPError as e:
                if e.code == 403 and api == 'pcsx':
                    api = 'v2'
                    continue
                raise
            d = d.get('data', d)
            pos = d.get('positions') or []
            for j in pos:
                if keep(j.get('name', '')):
                    found.setdefault(j['id'], j)
            start += len(pos)
            if not pos or start >= (d.get('count') or 0):
                break
    for jid, j in list(found.items())[:cap]:
        path = (f"pcsx/position_details?position_id={jid}&domain={dom}&hl=en" if api == 'pcsx'
                else f"apply/v2/jobs/{jid}?domain={dom}")
        x = http.get(f"https://{host}/api/{path}")
        x = x.get('data', x)
        loc = j.get('location') or ', '.join((j.get('locations') or [])[:2])
        ts = j.get('postedTs') or x.get('t_create') or x.get('t_update')  # v2 sites have no postedTs
        posted = time.strftime('%Y-%m-%d', time.gmtime(ts)) if ts else ''
        yield row(b['company'], j['name'], j.get('canonicalPositionUrl') or f"https://{host}/careers/job/{jid}",
                  text(x.get('job_description') or x.get('jobDescription') or ''), loc, posted,
                  j.get('department') or '', 'eightfold')


VENDORS = {'greenhouse': greenhouse, 'lever': lever, 'ashby': ashby, 'smartrecruiters': smartrecruiters,
           'rippling': rippling, 'bamboohr': bamboohr, 'workday': workday, 'amazon': amazon,
           'phenom': phenom, 'oracle': oracle, 'eightfold': eightfold}


# ---------- postings saved by hand ----------
def manual(ws):
    """workspace/manual/*.md or *.txt. Optional header lines at the top:
    company: X / title: Y / url: Z / posted: YYYY-MM-DD / source: mba-exchange"""
    for f in sorted(glob.glob(os.path.join(ws, 'manual', '*.md')) + glob.glob(os.path.join(ws, 'manual', '*.txt'))):
        raw = open(f, encoding='utf-8', errors='ignore').read()
        raw = re.sub(r'^---\n(.*?)\n---\n', r'\1\n\n', raw, flags=re.S)
        meta = dict((k.lower(), v.strip()) for k, v in re.findall(r'^(company|title|url|posted|source|location):\s*(.+)$', raw, re.M | re.I))
        body = re.sub(r'^(company|title|url|posted|source|location):.*$', '', raw, flags=re.M | re.I).strip()
        name = os.path.splitext(os.path.basename(f))[0]
        r = row(meta.get('company', name.split('__')[0]), meta.get('title', name), meta.get('url', 'file://' + f),
                body, meta.get('location', ''), meta.get('posted', ''), '', meta.get('source', 'manual'))
        yield r


# ---------- archive ----------
def key(r):
    return r['url'] or hashlib.sha1((r['company'] + r['title'] + r['body'][:300]).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--max-age', type=float, default=20, help='hours before a cached response is refetched')
    ap.add_argument('--cap', type=int, default=150, help='max detail fetches per company (Workday, SmartRecruiters)')
    ap.add_argument('--workers', type=int, default=6, help='boards fetched at once')
    ap.add_argument('--only', help='comma list of company names to fetch this run')
    a = ap.parse_args()
    ws = os.path.expanduser(a.workspace)
    crit = json.load(open(os.path.join(ws, 'criteria.json')))
    discs = load_disciplines(crit['disciplines'])
    terms = [t for d in discs for t in d['search_terms']]

    def keep(title):
        return bool(title_matches(title, discs))

    boards = json.load(open(os.path.join(ROOT, 'data', 'boards.json')))['boards']
    mine = os.path.join(ws, 'my_boards.json')
    if os.path.exists(mine):
        boards += json.load(open(mine))
    want = crit.get('companies') or 'all'
    if a.only:
        want = [x.strip() for x in a.only.split(',')]
    if want != 'all':
        wl = {w.lower() for w in want}
        boards = [b for b in boards if b['company'].lower() in wl]

    http = Http(os.path.join(ws, 'raw'), a.max_age)
    arch_p = os.path.join(ws, 'postings.jsonl')
    arch = {}
    if os.path.exists(arch_p):
        for line in open(arch_p, encoding='utf-8'):
            r = json.loads(line)
            arch[key(r)] = r

    def add(r):
        k = key(r)
        old = arch.get(k)
        r['first_seen'] = old['first_seen'] if old else TODAY
        r['last_seen'] = TODAY
        arch[k] = r
        return 1

    def save():
        tmp = arch_p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            for r in arch.values():
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        os.replace(tmp, arch_p)

    def pull(b):
        rows, err = [], None
        try:
            for r in VENDORS[b['type']](http, b, keep, terms, a.cap):
                rows.append(r)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError, TimeoutError, OSError) as e:
            err = f"{type(e).__name__}: {str(e)[:80]}"
        return b, rows, err

    print(f"disciplines: {', '.join(d['name'] for d in discs)}   boards: {len(boards)}")
    todo = []
    for b in boards:
        if b['type'] not in VENDORS or b.get('fetch') == 'manual':
            print(f"  {b['company']:24s} skipped ({b['type']}: search by hand, save to manual/)")
        else:
            todo.append(b)
    # Boards run in parallel (each board stays sequential, so no single site is hit hard).
    # The archive is saved after every board, so stopping mid-run loses nothing already pulled.
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as ex:
        for b, rows, err in (f.result() for f in concurrent.futures.as_completed([ex.submit(pull, b) for b in todo])):
            n = sum(add(r) for r in rows)
            note = f"ERROR {err}  ({n} kept before error)" if err else f"{n:4d} matching roles  ({b['type']})"
            print(f"  {b['company']:24s} {note}", flush=True)
            save()
    m = sum(add(r) for r in manual(ws))
    print(f"  {'manual/ folder':24s} {m:4d} postings")
    save()
    live = sum(1 for r in arch.values() if r['last_seen'] == TODAY)
    print(f"\narchive: {len(arch)} postings ({live} seen today, {len(arch) - live} seen on earlier runs only)")


if __name__ == '__main__':
    main()
