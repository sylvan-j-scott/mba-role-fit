#!/usr/bin/env python3
"""Minimum stated years of experience — corrected extractor.

REPLACES the one-liner inherited from fit.py by every downstream script:
    y = [int(x) for x in re.findall(r"(\\d{1,2})\\s*\\+?\\s*years?", raw) if 0 < int(x) < 25]
    minyrs = min(y) if y else None

Sylvan found the defect on 2026-09-07 in Nielsen "Director of Product Marketing", which reads
"8-10+ years in B2B product marketing, with at least 3-5 years in a leadership role" and was
recorded as reachable at 5. Two independent bugs compounded there:

  MODE 1 - the low end of a range is invisible. In "8-10+ years" the pattern needs digits
  immediately before "years", so it captures 10 and never sees 8. The STATED MINIMUM is exactly
  the number the field is supposed to hold, and it is the one number the regex cannot see.
  78 non-Amazon postings affected.

  MODE 2 - min() across the whole document lands on a SUBORDINATE clause. "8-10 years ... with at
  least 3-5 years in a leadership role" yields min=3 (or 5). The subordinate figure is a
  requirement WITHIN the primary one, never an alternative to it, so it must never be the answer.
  82 non-Amazon postings affected.

  MODE 3 - prose that is not a requirement at all ("founded 80 years ago"). Rare, 2 postings.

The two modes bias in OPPOSITE directions, which is why the errors were invisible in aggregate:
mode 1 overstates the requirement, mode 2 understates it. A sanity check on the mean would have
found nothing. Only reading individual postings surfaces this -- which is what Sylvan did.

Returns (minyrs, basis) where basis is 'primary' | 'fallback' | 'none', so callers can report how
the number was obtained rather than treating all values as equally trustworthy.
"""
import re

# "8-10 years", "8 to 10 years", "8–10+ years", "5 or 7 years" -> normalise to the LOW end
RANGE = re.compile(r"(?P<lo>\d{1,2})\s*(?:-|–|—|\bto\b|\bor\b)\s*(?P<hi>\d{1,2})\s*\+?\s*years?", re.I)
# "5 years", "5+ years", "at least 5 years"
SINGLE = re.compile(r"(?P<v>\d{1,2})\s*\+?\s*years?", re.I)

# Marks the mention as nested INSIDE a broader requirement rather than being one.
LEAD_IN = re.compile(r"(with at least|with a minimum of|including at least|including|of which|"
                     r"and at least|plus at least|plus|plus a|,\s*with)\s*$", re.I)
# "... 3 years in a leadership role" -- a narrower requirement nested inside the headline one.
# ANCHORED DELIBERATELY. An early version allowed up to 60 chars of slack before the qualifier
# and produced two false positives immediately: it read "8-10+ years in B2B product marketing,
# with at least 3-5 years in a leadership role" as subordinate (skipping 56 chars to reach
# "leadership"), and read "5+ years of product MANAGEMENT experience" as subordinate by matching
# the word "management" inside the job function itself. The qualifier must follow directly.
QUALIFIED = re.compile(r"^\s*\+?\s*(?:years?)?\s*(?:of|in)\s+(?:a\s+|an\s+)?(?:direct\s+)?"
                       r"(?:people[- ])?(leadership|management|managerial|supervisory|"
                       r"line[- ]manage|people[- ]manage)\b", re.I)
# Not a requirement at all.
NOISE = re.compile(r"^\s*\+?\s*(?:years?)?\s*(ago|of age|old|in business|history|anniversar|"
                   r"running|since)", re.I)

def _mentions(text):
    """Yield (value_at_low_end, is_subordinate, is_noise) for every year expression."""
    spans = []
    for m in RANGE.finditer(text):
        spans.append((m.start(), m.end(), int(m.group('lo'))))
    covered = {(s, e) for s, e, _ in spans}
    for m in SINGLE.finditer(text):
        if any(s <= m.start() < e for s, e, _ in spans):   # already inside a range match
            continue
        spans.append((m.start(), m.end(), int(m.group('v'))))
    for s, e, v in sorted(spans):
        if not (0 < v < 25):
            continue
        before = text[max(0, s - 45):s]
        after  = text[e:e + 80]
        yield v, bool(LEAD_IN.search(before) or QUALIFIED.match(after)), bool(NOISE.match(after))

def min_years(text):
    """(minyrs, basis). Primary mentions win; a subordinate clause is never the answer on its own
    unless it is all there is, and then the basis says 'fallback' so it can be discounted."""
    primary, subordinate = [], []
    for v, sub, noise in _mentions(text):
        if noise:
            continue
        (subordinate if sub else primary).append(v)
    if primary:
        return min(primary), 'primary'
    if subordinate:
        return min(subordinate), 'fallback'
    return None, 'none'

def reachable(text, cap=5):
    """A posting is reachable if it states no requirement, or states one at or below the cap.
    An unstated requirement is genuinely unknown -- counting it as reachable is a deliberate
    optimistic default, and 11% of non-Amazon postings sit in that bucket."""
    v, _ = min_years(text)
    return v is None or v <= cap

if __name__ == '__main__':
    for t in ["8–10+ years in B2B product marketing, with at least 3-5 years in a leadership role.",
              "8-12+ years of marketing experience, with a heavy emphasis on retention.",
              "5+ years of product management experience.",
              "Minimum 3 years experience. Preferred: 7 years in fintech.",
              "Our company was founded 80 years ago. 4+ years of experience required.",
              "No experience requirement stated here."]:
        print(f"{str(min_years(t)):22s} reachable={reachable(t)}   {t[:64]}")
