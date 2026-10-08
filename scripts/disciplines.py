"""Load discipline files and sort a posting into discipline, slice, and level.

A discipline file (disciplines/<name>.json) says which TITLES belong to it, how to split it into
slices, and which words its postings use. Everything here runs on titles, because titles are the
one field every board has. A role can land in more than one discipline. That overlap is reported,
not hidden.
"""
import glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DDIR = os.path.join(ROOT, 'disciplines')

# Titles no MBA discipline wants. Applied before any discipline match.
GLOBAL_EXCLUDE = re.compile(
    r'engineer|software|developer|\bsde\b|designer|data scien|architect|recruit|counsel|attorney|'
    r'paralegal|nurse|pharmac|physician|technician|\bdriver\b|cashier|store associate|'
    r'sales associate|warehouse associate|stocker|janitor|security officer|intern\b|internship', re.I)

# Above a typical post-MBA hire. 'stretch' is reachable for people with long pre-MBA careers.
ABOVE = re.compile(r'\b(vp|vice president|svp|evp|chief|head of|senior director|managing director|'
                   r'executive director|partner|principal|staff|group product manager)\b', re.I)
STRETCH = re.compile(r'\b(director|senior manager|sr\.? manager)\b', re.I)
BELOW = re.compile(r'\b(coordinator|assistant|representative|clerk|specialist|apprentice|'
                   r'entry[- ]level|new grad|analyst i\b)', re.I)


def _compile(d):
    d['_inc'] = re.compile(d['title_include'], re.I)
    d['_exc'] = re.compile(d['title_exclude'], re.I) if d.get('title_exclude') else None
    d['_mba'] = re.compile(d['mba_level_titles'], re.I) if d.get('mba_level_titles') else None
    d['_slices'] = [(s['name'], re.compile(s['title_regex'], re.I)) for s in d['slices']]
    d['_axes'] = [(a['name'], re.compile(a['regex'], re.I)) for a in d.get('axes', [])]
    return d


def available():
    return sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(DDIR, '*.json')))


def load_disciplines(names):
    out = []
    for n in names:
        p = os.path.join(DDIR, n + '.json')
        if not os.path.exists(p):
            raise SystemExit(f"unknown discipline '{n}'. Available: {', '.join(available())}")
        out.append(_compile(json.load(open(p))))
    return out


def title_matches(title, discs):
    if not title or GLOBAL_EXCLUDE.search(title):
        return []
    return [d for d in discs if d['_inc'].search(title) and not (d['_exc'] and d['_exc'].search(title))]


def slices_for(title, d):
    hit = [name for name, rx in d['_slices'] if rx.search(title)]
    return hit or [f"{d['label']}: other"]


def level(title, d):
    if d['_mba'] and d['_mba'].search(title):
        return 'mba-level'
    if ABOVE.search(title):
        return 'above'
    if STRETCH.search(title):
        return 'stretch'
    if BELOW.search(title):
        return 'below'
    return 'mba-level'
