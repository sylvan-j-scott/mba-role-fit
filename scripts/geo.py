"""Where is a posting? 'us', 'intl', or 'unknown', plus an explicit filter the user configures.

criteria.json -> "location":
  {"mode": "us"}                      US + postings we can't place (default; unknown is flagged, not hidden)
  {"mode": "us-strict"}               only postings we can confirm are in the US
  {"mode": "international"}           only postings outside the US
  {"mode": "anywhere"}                no filter
  {"mode": "custom", "include": ["Utah", "Salt Lake", "Lehi", "Provo"], "include_remote": true}
                                      only postings naming one of these places, in the location field OR
                                      the first part of the description (Workday lists site names like
                                      "CINCINNATI GENERAL OFFICES", so the field alone misses roles)
Optional in any mode: "exclude": ["New York"] to drop places.
"""
import re

STATES = ('Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|'
          'Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|'
          'Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|'
          'North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|'
          'South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|'
          'District of Columbia')
ABBR = ('AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|'
        'OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC')
US = re.compile(rf'United States|\bUSA?\b|\bU\.S\.|{STATES}|,\s*({ABBR})\b|\b({ABBR}),?\s*(USA|US)\b|'
                r'San Francisco|Seattle|Chicago|Boston|Austin|Atlanta|Denver|Cincinnati|Minneapolis|Bentonville|'
                r'Salt Lake|Los Angeles|Dallas|Houston|Miami|Phoenix|Philadelphia|Pittsburgh|Detroit|Nashville|'
                r'Charlotte|Raleigh|Portland|San Diego|San Jose|Palo Alto|Mountain View|Sunnyvale|Menlo Park|'
                r'Redmond|Bellevue|Arlington|McLean|Plano|Irvine|Lehi|Provo|Boise|Columbus|Cleveland|St\.? Louis')
INTL = re.compile(r'India|Mumbai|Bangalore|Bengaluru|Hyderabad|Pune|Chennai|Gurgaon|Gurugram|Noida|Canada|Toronto|'
                  r'Vancouver|Montreal|Mexico|Brazil|S[aã]o Paulo|Argentina|Buenos Aires|Colombia|Bogot|Chile|Peru|'
                  r'United Kingdom|\bUK\b|England|London|Manchester|Ireland|Dublin|Germany|Berlin|Munich|Frankfurt|'
                  r'France|Paris|Spain|Madrid|Barcelona|Italy|Milan|Netherlands|Amsterdam|Belgium|Brussels|Poland|'
                  r'Warsaw|Krak|Romania|Bucharest|Ukraine|Kyiv|Czech|Prague|Switzerland|Geneva|Zurich|Sweden|'
                  r'Stockholm|Denmark|Copenhagen|Norway|Finland|Israel|Tel Aviv|Dubai|\bUAE\b|Saudi|Riyadh|Egypt|'
                  r'Cairo|Nigeria|Lagos|Kenya|Nairobi|South Africa|Singapore|Japan|Tokyo|China|Shanghai|Beijing|'
                  r'Shenzhen|Hong Kong|Korea|Seoul|Taiwan|Taipei|Philippines|Manila|Vietnam|Thailand|Bangkok|'
                  r'Malaysia|Kuala Lumpur|Indonesia|Jakarta|Australia|Sydney|Melbourne|New Zealand|Costa Rica|'
                  r'Panama|Turkey|Istanbul|Portugal|Lisbon|Austria|Vienna|Hungary|Budapest|Greece|Luxembourg|EMEA|APAC|LATAM')
REMOTE = re.compile(r'\bremote\b', re.I)


def where(loc):
    """Classify the location field only. Description text is too noisy for us/intl
    (global companies list every office in the boilerplate)."""
    loc = loc or ''
    us, intl = bool(US.search(loc)), bool(INTL.search(loc))
    if us and not intl:
        return 'us'
    if intl and not us:
        return 'intl'
    return 'unknown'   # blank, a site name, or both ("New York; London")


def make_filter(cfg):
    cfg = cfg or {'mode': 'us'}
    mode = cfg.get('mode', 'us')
    exc = re.compile('|'.join(cfg['exclude']), re.I) if cfg.get('exclude') else None
    inc = re.compile('|'.join(cfg['include']), re.I) if cfg.get('include') else None

    def keep(p):
        loc = p.get('location') or ''
        if exc and exc.search(loc):
            return False
        g = where(loc)
        if mode == 'anywhere':
            return True
        if mode == 'us':
            return g != 'intl'
        if mode == 'us-strict':
            return g == 'us'
        if mode == 'international':
            return g == 'intl'
        if mode == 'custom':
            if not inc:
                raise SystemExit('location mode "custom" needs an "include" list, e.g. ["Utah", "Salt Lake", "Lehi"]')
            if inc.search(loc) or inc.search((p.get('body') or '')[:1500]):
                return True
            return bool(cfg.get('include_remote')) and bool(REMOTE.search(loc)) and g != 'intl'
        raise SystemExit(f'unknown location mode "{mode}". Use us, us-strict, international, anywhere, or custom.')

    def describe():
        if mode == 'custom':
            return f"custom: {', '.join(cfg['include'])}" + (' + remote (US)' if cfg.get('include_remote') else '')
        return {'us': 'US + unplaceable (flagged)', 'us-strict': 'confirmed US only',
                'international': 'outside the US only', 'anywhere': 'no location filter'}[mode]

    return keep, describe()
