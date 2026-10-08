#!/usr/bin/env python3
"""Build WS/report.html: one self-contained page answering all three questions.

    python3 scripts/report_html.py --workspace ~/role-fit-workspace

Reuses score.py's loader so reach, fit, and slices are computed exactly as the .md reports do.
Fit is shown as a percentile of THIS corpus (each company weighted equally), so "top 10%" means the same thing everywhere on the page.
"""
import argparse, bisect, collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score  # noqa: E402
from disciplines import load_disciplines, slices_for  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(HERE), 'templates', 'report.html')


def tag(t):
    """Bank tags are cut at 40 chars. Keep the name before ' — ', or end on a whole word."""
    t = t.split(' — ')[0] if ' — ' in t else t.rsplit(' ', 1)[0]
    return t.rstrip(' (—-')


def boilerplate(roles, vocab):
    """(company, term) pairs where the term is in 80%+ of that company's postings.
    That's the company describing itself ("payments" at Visa), not a skill the role asks for."""
    by = collections.defaultdict(list)
    for r in roles:
        by[r['company']].append(r['_txt'])
    out = set()
    for c, txts in by.items():
        if len(txts) < 5:
            continue
        for t in vocab:
            rx = score.term_rx(t)
            if sum(1 for x in txts if rx.search(x)) >= .8 * len(txts):
                out.add((c, t))
    return out


def gaps(rs, vocab, weight, boiler):
    reach = [r for r in rs if r['reach']] or rs
    out = []
    for t in vocab:
        if any(t in k or k in t for k in weight):
            continue
        rx = score.term_rx(t)
        share = sum(1 for r in reach if (r['company'], t) not in boiler and rx.search(r['_txt'])) / len(reach)
        if share >= .15:
            out.append([t, round(share, 2)])
    return sorted(out, key=lambda x: -x[1])[:10]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    a = ap.parse_args()
    ws = os.path.expanduser(a.workspace)
    crit = json.load(open(os.path.join(ws, 'criteria.json')))
    discs = load_disciplines(crit['disciplines'])
    roles, m = score.load(ws, crit, discs)

    # Percentile with each company weighted equally, matching score.company_pct, so the 90 line on
    # the page is the same cutoff that decides 'top 10%'.
    nco = collections.Counter(r['company'] for r in roles)
    pts = sorted((r['fit'], 1 / nco[r['company']]) for r in roles)
    cum, run = [], 0
    for _, w in pts:
        run += w
        cum.append(run)
    fits = [f for f, _ in pts]
    pctl = lambda f: min(100, round(100 * cum[bisect.bisect_right(fits, f) - 1] / run))  # noqa: E731
    roles.sort(key=lambda r: -r['fit'])
    for i, r in enumerate(roles):
        r['_id'] = i
    hi = lambda r: r['reach'] and r['fit'] > m['P90']  # noqa: E731

    R = [dict(c=r['company'], t=r['title'], u=r['url'], p=pctl(r['fit']), r=r['reach'], h=hi(r),
              y=r['minyrs'], a=r['axes'], g=r['geo'], d=r['disciplines'],
              k=[tag(m['rec_terms'][x][0]) for x in r['records']][:3]) for r in roles]

    def row(label, d, rs, vocab):
        rc = collections.Counter(tag(m['rec_terms'][x][0]) for r in rs[:50] for x in r['records'])
        return dict(label=label, disc=d['name'] if d else None, ids=[r['_id'] for r in rs],
                    recs=rc.most_common(5), gaps=gaps(rs, vocab, m['weight'], boiler),
                    cos=len({r['company'] for r in rs}))

    views = {}
    allvocab = sorted({t for d in discs for t in d['vocabulary']})
    boiler = boilerplate(roles, allvocab)
    for key in ['all'] + [d['name'] for d in discs]:
        ds = discs if key == 'all' else [d for d in discs if d['name'] == key]
        sl = collections.defaultdict(list)
        for d in ds:
            for r in roles:
                if d['name'] in r['disciplines']:
                    for s in slices_for(r['title'], d):
                        sl[(s, d['name'])].append(r)
        dmap = {d['name']: d for d in ds}
        slices = [row(s, dmap[dn], rs, dmap[dn]['vocabulary']) for (s, dn), rs in sl.items()]
        g = [r for r in roles if any(d['name'] in r['disciplines'] for d in ds)]
        co = collections.defaultdict(list)
        for r in g:
            co[r['company']].append(r)
        vocab = allvocab if key == 'all' else ds[0]['vocabulary']
        companies = [row(c, None, rs, vocab) for c, rs in co.items()]
        views[key] = dict(slices=slices, companies=companies,
                          hi=sum(hi(r) for r in g), n=len(g), reach=sum(r['reach'] for r in g),
                          cos=len({r['company'] for r in g if hi(r)}))

    geo = collections.Counter(r['geo'] for r in roles)
    top = collections.Counter(r['company'] for r in roles).most_common(1)[0]
    meta = dict(n=len(roles), cos=len({r['company'] for r in roles}), loc=m['loc_desc'],
                us=geo['us'], intl=geo['intl'], unk=geo['unknown'],
                dropped_loc=m['dropped']['location filter'], max_years=m['max_years'],
                bank=len(m['bank']), core=crit.get('core'),
                top_co=top[0], top_share=round(top[1] / len(roles), 2),
                discs=[[d['name'], d['label']] for d in discs])
    data = json.dumps(dict(meta=meta, roles=R, views=views), separators=(',', ':'))
    html = open(TEMPLATE).read().replace('/*__DATA__*/null', data)
    out = os.path.join(ws, 'report.html')
    open(out, 'w').write(html)
    print(f"{len(roles)} roles, {len(views)} views, {len(data) // 1024} KB data -> {out}")


if __name__ == '__main__':
    main()
