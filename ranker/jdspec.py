"""
Job-description parser.

Turns *any* free-text JD into a structured JDSpec the ranker can score against:
target role domains, salient keywords, an experience band, and target
locations. Nothing here is specific to the AI-Engineer role — paste a Marketing
Manager or Civil Engineer JD and the spec adapts.
"""
import re
from dataclasses import dataclass, field

from . import domains as D

# --- location gazetteer (extend freely) ------------------------------------ #
INDIA_CITIES = [
    "pune", "noida", "bengaluru", "bangalore", "hyderabad", "mumbai", "delhi",
    "new delhi", "gurgaon", "gurugram", "ncr", "chennai", "kolkata", "ahmedabad",
    "jaipur", "indore", "kochi", "trivandrum", "thiruvananthapuram", "chandigarh",
    "coimbatore", "nagpur", "lucknow", "bhubaneswar", "vadodara", "surat",
]
COUNTRIES = [
    "india", "usa", "united states", "uk", "united kingdom", "canada",
    "australia", "germany", "uae", "singapore", "netherlands", "france",
    "ireland", "japan",
]

_STOP = set("""a an the and or of to for with in on at by we you your our they
this that is are be as it role team will would should role job description
years year experience company looking need want must have has if not""".split())


# markers that introduce an "anti-requirement" in a JD
NEG_MARKERS = [
    "do not want", "don't want", "dont want", "not a fit", "not what we need",
    "do not move forward", "will not move forward", "won't move forward",
    "probably not move forward", "explicitly do not", "explicitly do not want",
    "we will not", "disqualif", "bad fit", "not move forward", "avoid",
    "we do not want", "not looking for",
]

# specialty phrases worth flagging when they appear in an exclusion sentence
SPECIALTY_VOCAB = [
    "computer vision", "vision", "speech", "speech recognition", "robotics",
    "image processing", "langchain", "blockchain", "game development",
    "embedded", "hardware", "frontend", "mobile", "qa", "testing", "manual testing",
    "wordpress", "sales", "marketing", "academic", "research-only", "pure research",
]


@dataclass
class JDSpec:
    raw: str
    title: str
    profile: dict                      # domain -> weight (the JD's domain vector)
    target_domains: list
    keywords: list = field(default_factory=list)
    exp_min: float = 0.0
    exp_max: float = 50.0
    exp_ideal: float = 0.0
    locations: list = field(default_factory=list)   # matched cities
    countries: list = field(default_factory=list)
    has_location_pref: bool = False
    negative_terms: list = field(default_factory=list)  # specialties the JD excludes


def _extract_title(text):
    """Grab a likely role title from the first lines / 'Job Description:' label."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r"(?:job\s*description|role|position|title)\s*[:\-]\s*(.+)",
                      line, re.I)
        if m:
            return m.group(1).strip()[:120]
        return line[:120]                # fall back to the very first non-empty line
    return ""


def _parse_experience(text):
    t = text.lower()
    # "5-9 years", "5 to 9 years", "5 – 9 years"
    m = re.search(r"(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})\s*\+?\s*year", t)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return float(lo), float(hi), (lo + hi) / 2.0
    # "5+ years", "minimum 5 years", "at least 5 years"
    m = re.search(r"(?:minimum|at least|min|over|more than)\s*(\d{1,2})\s*\+?\s*year", t)
    if not m:
        m = re.search(r"(\d{1,2})\s*\+\s*year", t)
    if m:
        lo = int(m.group(1))
        return float(lo), float(lo + 6), float(lo + 1)
    # bare "5 years"
    m = re.search(r"(\d{1,2})\s*year", t)
    if m:
        lo = int(m.group(1))
        return max(0.0, lo - 2.0), float(lo + 3), float(lo)
    return 0.0, 50.0, 0.0               # no constraint found


def _parse_locations(text):
    t = text.lower()
    cities = [c for c in INDIA_CITIES if re.search(r"\b" + re.escape(c) + r"\b", t)]
    countries = [c for c in COUNTRIES if re.search(r"\b" + re.escape(c) + r"\b", t)]
    # de-dup bangalore/bengaluru style
    return sorted(set(cities)), sorted(set(countries))


def _negative_terms(text):
    """
    Specialties the JD explicitly excludes. We scan each sentence that contains
    an exclusion marker and collect known specialty phrases from it. General:
    a Marketing JD that says 'not looking for cold-calling sales' would flag
    'sales' the same way this flags 'computer vision' for the AI JD.
    """
    t = text.lower()
    clauses = re.split(r"[.\n;]", t)
    # a marker often heads a list ("Things we do NOT want:" then bullets), so
    # treat the marker clause AND the next few clauses as negative context.
    neg_idx = set()
    for i, cl in enumerate(clauses):
        if any(m in cl for m in NEG_MARKERS):
            # extend until the next marker or a bounded window (covers a whole
            # "do NOT want" bullet list without spilling into positive sections)
            end = min(len(clauses), i + 16)
            for j in range(i, end):
                neg_idx.add(j)
    neg = []
    for i in sorted(neg_idx):
        for sp in SPECIALTY_VOCAB:
            if re.search(r"\b" + re.escape(sp) + r"\b", clauses[i]) and sp not in neg:
                neg.append(sp)
    return neg


def _keywords(text, jd_profile):
    """Salient terms = domain terms of the JD's top domains present in the text."""
    t = text.lower()
    kws = []
    for dom in D.top_domains(jd_profile, k=3, thresh=0.12):
        titles, terms = D.DOMAINS[dom]
        for term in terms + titles:
            if term in t and term not in kws and len(term) > 2:
                kws.append(term)
    return kws[:40]


def parse_jd(jd_text):
    title = _extract_title(jd_text)
    # JD domain profile: the extracted role title is the "current" identity, the
    # whole JD body is the corroborating prose.
    profile = D.domain_profile(title, [], jd_text)
    target = D.top_domains(profile, k=3, thresh=0.15) or D.top_domains(profile, k=1, thresh=0.0)
    lo, hi, ideal = _parse_experience(jd_text)
    cities, countries = _parse_locations(jd_text)
    kws = _keywords(jd_text, profile)
    neg = _negative_terms(jd_text)
    # a term named in the exclusions section is a negative even if it also lives
    # in the positive domain vocab (the AI JD lists "computer vision" as a
    # negative). Negatives win: drop them from the positive keyword list.
    kws = [k for k in kws if k not in neg]
    return JDSpec(
        raw=jd_text, title=title, profile=profile, target_domains=target,
        keywords=kws, exp_min=lo, exp_max=hi, exp_ideal=ideal,
        locations=cities, countries=countries,
        has_location_pref=bool(cities or countries),
        negative_terms=neg,
    )
