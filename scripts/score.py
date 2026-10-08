#!/usr/bin/env python3
"""Answer one of three questions from the postings archive and the user's bank.

    python3 scripts/score.py --workspace WS --question where
        Q1 "Where do I fit?"  Every slice in every swept discipline, one ranking.
    python3 scripts/score.py --workspace WS --question companies --discipline supply-chain
        Q2 "In this discipline, which companies fit me best?"
    python3 scripts/score.py --workspace WS --question roles --discipline marketing
        Q3 "In this discipline, what kinds of roles exist, and which am I strongest for?"
           Also lists the words those postings use that the bank never does (interview round 2).

Reads   WS/criteria.json, WS/bank.json, WS/postings.jsonl
Writes  WS/report_<question>[_<discipline>].md, WS/scored.jsonl (one line per role, no body)

Three measures, kept SEPARATE on purpose. One blended number ranks word overlap and calls it fit.
  reach   could you be hired into it: title level + stated minimum years vs your years
  fit     how much of your bank's vocabulary the posting uses, weighted by record strength,
          per 1,000 words so long postings don't win by length
  axes    yes/no flags for the shape of the work (owns a number, 0-to-1, discipline-specific)

Slices come from title patterns in disciplines/*.json. They are a starting grouping, not a verdict:
the same title can mean different jobs at different companies.

Sample-size bands bind: n>=100 medians trustworthy, 40-99 directional, <40 list roles only.
"""
import argparse, collections, json, os, re, statistics, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from disciplines import load_disciplines, title_matches, slices_for, level  # noqa: E402
from geo import make_filter, where  # noqa: E402
from minyrs import min_years  # noqa: E402

GLOBAL_AXES = [
    ('owns a number', re.compile(r"own(?:s|ing|ed)?\s+(?:the\s+)?(?:p&l|business|revenue|budget)|\bp&l\b|"
                                 r"profit and loss|revenue target|revenue goal|\bquota\b|gross margin|"
                                 r"unit economics|own the number|business owner|general manager", re.I)),
    ('0-to-1', re.compile(r"0 to 1|0-to-1|zero to one|greenfield|from scratch|incubat|new product line|"
                          r"launch new|stand up a new|early.stage|new business|new vertical|white space", re.I)),
]
# Bank keywords too generic to tell roles apart.
DROP = {'product', 'ai', 'leadership', 'communication', 'operations', 'strategy', 'analytics',
        'automation', 'management', 'marketing', 'finance', 'business', 'team', 'data'}


def composite(r):
    """Same weights as the bank template: defensibility is the gate, so it carries real weight."""
    s = r.get('scores') or {}
    if all(k in s for k in ('impact', 'defensibility', 'differentiation', 'recency')):
        return .35 * s['impact'] + .30 * s['defensibility'] + .25 * s['differentiation'] + .10 * s['recency']
    return 3.0


def clean(t):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9&/+\-% ]', ' ', (t or '').lower()))


def term_rx(t):
    # Word boundaries on every term. Plain substring matching lets "arr" score inside "carry".
    return re.compile(r'(?<![a-z0-9])' + re.escape(t) + r'(?![a-z0-9])')


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))] if v else 0


def band(n):
    return 'trustworthy' if n >= 100 else ('directional' if n >= 40 else 'UNDER-SAMPLED')


def role_line(r):
    yrs = f"{r['minyrs']}y" if r['minyrs'] is not None else "yrs?"
    geo = '' if r['geo'] == 'us' else f" · loc {r['geo']}"
    return (f"- {r['fit']:.1f} · {r['company']} · {r['title']} · {yrs}{geo} · "
            f"{', '.join(r['axes']) or 'no axis flags'} · [link]({r['url']})")


# ---------- load and score every role once ----------
def load(ws, crit, discs):
    bank = json.load(open(os.path.join(ws, 'bank.json')))['records']
    weight, rec_terms = {}, {}
    for r in bank:
        ks = {k.strip().lower() for k in r.get('keywords', []) if k.strip()}
        ks = {k for k in ks if k not in DROP and len(k) > 2}
        rec_terms[r['id']] = (r.get('tag', ''), ks)
        for k in ks:
            weight[k] = max(weight.get(k, 0), composite(r))
    rxs = {k: term_rx(k) for k in weight}
    keep_loc, loc_desc = make_filter(crit.get('location'))
    max_years = crit.get('max_years', 5)

    roles, dropped = [], collections.Counter()
    for line in open(os.path.join(ws, 'postings.jsonl'), encoding='utf-8'):
        p = json.loads(line)
        ds = title_matches(p['title'], discs)
        if not ds:
            continue
        if len(p.get('body', '')) < 300:
            dropped['no description'] += 1
            continue
        if not keep_loc(p):
            dropped['location filter'] += 1
            continue
        txt = clean(p['body'])
        n = max(len(txt.split()) / 1000, 1.0)
        hits = {k for k, rx in rxs.items() if rx.search(txt)}
        yrs, basis = min_years(p['body'])
        p.update(
            disciplines=[d['name'] for d in ds],
            level=level(p['title'], ds[0]),
            minyrs=yrs, yrs_basis=basis, geo=where(p.get('location')),
            fit=round(sum(weight[k] for k in hits) / n, 1),
            hits=sorted(hits),
            records=sorted(rid for rid, (_, ks) in rec_terms.items() if len(ks & hits) >= 3),
            axes=sorted({nm for nm, rx in GLOBAL_AXES if rx.search(txt)} |
                        {nm for d in ds for nm, rx in d['_axes'] if rx.search(txt)}),
            _txt=txt)
        p['reach'] = p['level'] != 'above' and (yrs is None or yrs <= max_years)
        roles.append(p)
    if not roles:
        raise SystemExit(f"No roles left (dropped: {dict(dropped)}). Run fetch.py, widen disciplines, "
                         f"or loosen the location setting.")
    meta = dict(bank=bank, weight=weight, rec_terms=rec_terms, loc_desc=loc_desc, dropped=dropped,
                max_years=max_years, P90=pct([r['fit'] for r in roles], .9))
    return roles, meta


def header(title, roles, m):
    geo = collections.Counter(r['geo'] for r in roles)
    out = [f"# {title}\n",
           f"{len(roles)} roles · {len({r['company'] for r in roles})} companies · bank: {len(m['bank'])} records, "
           f"{len(m['weight'])} keywords · reach = not above MBA level and stated minimum ≤ {m['max_years']} yrs · "
           f"corpus p90 fit = {m['P90']:.1f}\n",
           f"**Location:** {m['loc_desc']} · kept {geo['us']} US, {geo['intl']} international, {geo['unknown']} "
           f"unplaceable · dropped {m['dropped']['location filter']} by location, "
           f"{m['dropped']['no description']} with no description\n"]
    top = collections.Counter(r['company'] for r in roles).most_common(1)[0]
    if top[1] / len(roles) > .4:
        out.append(f"⚠️ **{top[0]} is {top[1] / len(roles):.0%} of this corpus.** Rankings mostly describe "
                   f"{top[0]}. Add companies before trusting cross-company patterns.\n")
    out.append("Fit is relative to THIS corpus and THIS bank. Compare rows, not numbers across people.\n")
    return out


def slice_rows(roles, d, P90):
    by = collections.defaultdict(list)
    for r in roles:
        if d['name'] in r['disciplines']:
            for s in slices_for(r['title'], d):
                by[s].append(r)
    rows = []
    for s, rs in by.items():
        rch = [r for r in rs if r['reach']]
        rows.append(dict(slice=s, d=d, rs=rs, rch=rch, hi=[r for r in rch if r['fit'] > P90],
                         med=pct([r['fit'] for r in rch] or [0], .5)))
    return sorted(rows, key=lambda x: (-len(x['hi']), -x['med']))


# ---------- Q1 ----------
def q_where(roles, m, discs, crit):
    core = crit.get('core')
    out = header("Q1. Where do I fit?", roles, m)
    out.append(f"Every slice in every swept discipline, ranked by reachable roles above the corpus p90 fit."
               + (f" ★ = home discipline ({core})." if core else "") +
               " Your bank is written in your home discipline's words, so a non-home slice ranking high is a "
               "strong signal.\n")
    out.append("| # | slice | postings | companies | reachable | high-fit & reachable | median fit (reachable) | best match | band |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    rows = sorted([x for d in discs for x in slice_rows(roles, d, m['P90'])], key=lambda x: (-len(x['hi']), -x['med']))
    for i, x in enumerate(rows[:25], 1):
        best = max(x['rch'] or x['rs'], key=lambda r: r['fit'])
        star = ' ★' if x['d']['name'] == core else ''
        out.append(f"| {i} | {x['slice']}{star} | {len(x['rs'])} | {len({r['company'] for r in x['rs']})} | "
                   f"{len(x['rch'])} | {len(x['hi'])} | {x['med']:.1f} | {best['company']}: {best['title'][:45]} | "
                   f"{band(len(x['rs']))} |")
    out.append("\n**Top reachable roles overall**\n")
    out += [role_line(r) for r in sorted([r for r in roles if r['reach']], key=lambda r: -r['fit'])[:15]]
    out.append("\nNext: pick a discipline from the top rows and ask Q2 (companies) or Q3 (roles) for it.")
    return out


# ---------- Q2 ----------
def q_companies(roles, m, d):
    g = [r for r in roles if d['name'] in r['disciplines']]
    out = header(f"Q2. {d['label']}: which companies fit me best?", g, m)
    byco = collections.defaultdict(list)
    for r in g:
        byco[r['company']].append(r)

    def key(item):
        rch = [r for r in item[1] if r['reach']]
        return (-sum(r['fit'] > m['P90'] for r in rch), -pct([r['fit'] for r in rch] or [0], .5))

    out.append("Ranked by reachable roles above the corpus p90 fit, then median fit. A company with 1-2 roles "
               "is a data point, not a pattern.\n")
    out.append("| company | roles | reachable | median fit | high-fit & reachable | slices they hire for | best reachable role |")
    out.append("|---|---|---|---|---|---|---|")
    for c, rs in sorted(byco.items(), key=key):
        rch = [r for r in rs if r['reach']]
        sl = collections.Counter(s.split(': ', 1)[-1] for r in rs for s in slices_for(r['title'], d)).most_common(3)
        best = max(rch, key=lambda r: r['fit'])['title'][:50] if rch else '-'
        out.append(f"| {c} | {len(rs)} | {len(rch)} | {statistics.median(r['fit'] for r in rs):.1f} | "
                   f"{sum(r['fit'] > m['P90'] for r in rch)} | {', '.join(f'{s} {n}' for s, n in sl)} | {best} |")
    out.append("\n**Best 3 reachable roles at each of the top 8 companies**\n")
    for c, rs in sorted(byco.items(), key=key)[:8]:
        top = sorted([r for r in rs if r['reach']], key=lambda r: -r['fit'])[:3]
        if top:
            out.append(f"\n*{c}*")
            out += [role_line(r) for r in top]
    return out


# ---------- Q3 ----------
def q_roles(roles, m, d, top_n):
    g = [r for r in roles if d['name'] in r['disciplines']]
    out = header(f"Q3. {d['label']}: what kinds of roles exist, and which am I strongest for?", g, m)
    axis_names = [nm for nm, _ in GLOBAL_AXES] + [nm for nm, _ in d['_axes']]
    out.append("| slice | n | companies | reachable | median fit | p90 fit | high-fit & reachable | "
               + " | ".join(f"% {x}" for x in axis_names) + " | band |")
    out.append("|" + "---|" * (8 + len(axis_names)))
    for x in slice_rows(g, d, m['P90']):
        rs, f = x['rs'], [r['fit'] for r in x['rs']]
        med = f"{statistics.median(f):.1f}" if len(rs) >= 40 else "-"
        ax = " | ".join(f"{100 * sum(a in r['axes'] for r in rs) / len(rs):.0f}" for a in axis_names)
        out.append(f"| {x['slice']} | {len(rs)} | {len({r['company'] for r in rs})} | {len(x['rch'])} | {med} | "
                   f"{pct(f, .9):.1f} | {len(x['hi'])} | {ax} | {band(len(rs))} |")

    out.append(f"\n**Top {top_n} reachable roles by fit**\n")
    out += [role_line(r) for r in sorted([r for r in g if r['reach']], key=lambda r: -r['fit'])[:top_n]]

    rc = collections.Counter(x for r in sorted(g, key=lambda r: -r['fit'])[:50] for x in r['records'])
    if rc:
        out.append("\n**Bank records doing the work** (top-50 roles that use 3+ of a record's keywords)\n")
        out += [f"- {rid} ({m['rec_terms'][rid][0]}): {c}/50" for rid, c in rc.most_common(8)]

    reach = [r for r in g if r['reach']] or g
    gaps = []
    for t in d['vocabulary']:
        if any(t in k or k in t for k in m['weight']):
            continue
        share = sum(1 for r in reach if term_rx(t).search(r['_txt'])) / len(reach)
        if share >= .15:
            gaps.append((share, t))
    out.append("\n**Words these postings use that your bank never does** "
               "(round 2 of \"what else can you claim\", see reference/intake.md)\n")
    out.append(", ".join(f"{t} ({s:.0%})" for s, t in sorted(gaps, reverse=True)[:15]) or "None above 15%.")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--question', required=True, choices=['where', 'companies', 'roles'])
    ap.add_argument('--discipline', help='required for companies and roles')
    ap.add_argument('--top', type=int, default=15)
    a = ap.parse_args()
    ws = os.path.expanduser(a.workspace)
    crit = json.load(open(os.path.join(ws, 'criteria.json')))
    names = crit['disciplines']
    if a.question != 'where':
        if not a.discipline:
            raise SystemExit(f'--discipline is required for "{a.question}". Choose from: {", ".join(names)}')
        if a.discipline not in names:
            names = names + [a.discipline]
            print(f'note: {a.discipline} was not in criteria.disciplines; scoring it anyway. '
                  f'If it looks thin, add it to criteria and re-run fetch.py.')
    discs = load_disciplines(names)
    roles, m = load(ws, crit, discs)

    if a.question == 'where':
        out, name = q_where(roles, m, discs, crit), 'report_where.md'
    else:
        d = next(x for x in discs if x['name'] == a.discipline)
        out = q_companies(roles, m, d) if a.question == 'companies' else q_roles(roles, m, d, a.top)
        name = f'report_{a.question}_{a.discipline}.md'

    open(os.path.join(ws, name), 'w').write('\n'.join(out) + '\n')
    with open(os.path.join(ws, 'scored.jsonl'), 'w') as f:
        for r in roles:
            f.write(json.dumps({k: v for k, v in r.items() if k not in ('body', '_txt')}) + '\n')
    geo = collections.Counter(r['geo'] for r in roles)
    print(f"{len(roles)} roles after filters ({m['loc_desc']}; US {geo['us']}, intl {geo['intl']}, "
          f"unplaceable {geo['unknown']}; dropped {dict(m['dropped'])}) -> {name}")


if __name__ == '__main__':
    main()
