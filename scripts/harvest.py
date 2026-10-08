#!/usr/bin/env python3
"""Harvest every bullet from every resume version, and group the ones that describe the same thing.

    python3 scripts/harvest.py --workspace ~/role-fit-workspace

Reads   workspace/resumes/*.txt|md|docx|pdf   (PDF needs `pdftotext`; otherwise save it as .txt)
Writes  workspace/harvest.json

Most people have 3-15 versions of their resume, each tailored a little differently. The same
achievement shows up with different verbs, different emphasis, and sometimes DIFFERENT NUMBERS.
This script finds those groups (clusters) so the bank gets one record per real achievement,
the strongest wording is easy to see, and every number disagreement is surfaced for the user to settle.

Prints counts only.
"""
import argparse, difflib, glob, json, os, re, shutil, subprocess, zipfile

NUM = re.compile(r'\$?\d[\d,.]*\s?(%|x\b|k\b|m\b|mm\b|b\b|million|billion|\+)?', re.I)
BULLET = re.compile(r'^\s*([•●▪◦‣\-\*–]|\d+[.)])\s+')
STOP = set('a an the and or of to in for with by on at from as into over our their its using via was were '
           'is are be been led drove built created managed developed helped worked'.split())


def read_doc(p):
    ext = os.path.splitext(p)[1].lower()
    if ext in ('.txt', '.md'):
        return open(p, encoding='utf-8', errors='ignore').read()
    if ext == '.docx':
        x = zipfile.ZipFile(p).read('word/document.xml').decode('utf-8', 'ignore')
        x = re.sub(r'</w:p>', '\n', x)
        return re.sub(r'<[^>]+>', '', x)
    if ext == '.pdf':
        if not shutil.which('pdftotext'):
            raise RuntimeError('pdftotext not installed; save this PDF as .txt')
        return subprocess.run(['pdftotext', '-layout', p, '-'], capture_output=True, text=True).stdout
    raise RuntimeError(f'unsupported file type {ext}')


def bullets(doc):
    """Lines that look like accomplishments: bullet-marked, or long sentence-like lines with a verb start."""
    out, cur = [], None
    for line in doc.splitlines():
        s = line.strip()
        if not s:
            cur = None
            continue
        if BULLET.match(s):
            cur = BULLET.sub('', s)
            out.append(cur)
        elif cur is not None and s[:1].islower():      # wrapped continuation of the previous bullet
            out[-1] = out[-1] + ' ' + s
        elif len(s.split()) >= 7 and s[:1].isupper() and not s.isupper() and s[-1:] not in ':':
            out.append(s)
            cur = s
    # Drop role headers ("Director of Product, Acme   Sept 2024 – Jun 2025"): a date range and no verb sentence.
    hdr = re.compile(r"(19|20)\d\d\s*[–—-]\s*([a-z.]+\s*)?((19|20)\d\d|present|current)", re.I)
    return [re.sub(r'\s+', ' ', b).strip() for b in out
            if len(b.split()) >= 5 and not (hdr.search(b) and len(b.split()) < 14)]


def tokens(s):
    return [w for w in re.findall(r'[a-z0-9$%]+', s.lower()) if w not in STOP]


def sim(a, b):
    ta, tb = set(tokens(a)), set(tokens(b))
    jac = len(ta & tb) / max(1, len(ta | tb))
    return max(jac, difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--threshold', type=float, default=0.5)
    a = ap.parse_args()
    ws = os.path.expanduser(a.workspace)
    files = sorted(f for f in glob.glob(os.path.join(ws, 'resumes', '*'))
                   if os.path.splitext(f)[1].lower() in ('.txt', '.md', '.docx', '.pdf'))
    if not files:
        raise SystemExit('No resumes in workspace/resumes/. Add every version you have, old ones too.')

    allb = []
    for f in files:
        name = os.path.splitext(os.path.basename(f))[0]
        try:
            bs = bullets(read_doc(f))
        except Exception as e:
            print(f"  {name}: SKIPPED ({e})")
            continue
        print(f"  {name}: {len(bs)} bullets")
        allb += [(name, b) for b in bs]

    clusters = []
    for ver, b in allb:
        best, score = None, 0
        for c in clusters:
            s = max(sim(b, v['text']) for v in c['variants'][:6])
            if s > score:
                best, score = c, s
        if best and score >= a.threshold:
            if not any(v['text'] == b for v in best['variants']):
                best['variants'].append({'text': b, 'version': ver})
            best['versions'].add(ver)
        else:
            clusters.append({'variants': [{'text': b, 'version': ver}], 'versions': {ver}})

    out = []
    for i, c in enumerate(sorted(clusters, key=lambda c: -len(c['versions'])), 1):
        nums = sorted({m.group(0).strip() for v in c['variants'] for m in NUM.finditer(v['text'])
                       if re.search(r'\d', m.group(0)) and not re.fullmatch(r'(19|20)\d\d', m.group(0).strip())})
        norm = lambda x: re.sub(r'[,+\s]', '', x.lower())
        with_nums = [s for s in ({norm(m.group(0)) for m in NUM.finditer(v['text']) if re.search(r'\d', m.group(0))}
                                 for v in c['variants']) if s]
        # A conflict is two versions whose numbers can't both be true: neither set contains the other.
        # A version that just drops a number, or writes 7,800 as 7,800+, is not a conflict.
        conflict = any(not (x <= y or y <= x) for i, x in enumerate(with_nums) for y in with_nums[i + 1:])
        out.append({'cid': f'C{i:03d}', 'n_versions': len(c['versions']), 'versions': sorted(c['versions']),
                    'longest': max(c['variants'], key=lambda v: len(v['text']))['text'],
                    'numbers': nums, 'number_conflict': conflict, 'variants': c['variants']})

    json.dump({'files': [os.path.basename(f) for f in files], 'threshold': a.threshold,
               'bullets': len(allb), 'clusters': out}, open(os.path.join(ws, 'harvest.json'), 'w'), indent=1)
    print(f"\n{len(allb)} bullets from {len(files)} files -> {len(out)} clusters "
          f"({sum(c['n_versions'] > 1 for c in out)} appear in 2+ versions, "
          f"{sum(c['number_conflict'] for c in out)} have numbers that disagree)")


if __name__ == '__main__':
    main()
