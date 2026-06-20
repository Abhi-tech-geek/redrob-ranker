"""
Structured feature extraction — all JD-driven.

Each function turns one candidate (plus the parsed JDSpec) into a 0..1 sub-score.
Nothing here assumes a particular role: role fit is a domain-vector cosine,
experience/location come from the parsed JD, and keyword evidence is measured
against the JD's own salient terms. The same code ranks an AI-Engineer JD and a
Marketing-Manager JD.
"""
from . import config as C, domains as D

TECH_DOMAINS = {"ai_ml", "data_eng", "software", "frontend", "mobile", "devops", "qa"}


def _contains_any(text, needles):
    return any(n in text for n in needles)


# --------------------------------------------------------------------------- #
# Role fit  — cosine between candidate and JD domain vectors
# --------------------------------------------------------------------------- #
def candidate_domain_profile(cand, prose):
    prof = cand.get("profile", {}) or {}
    cur = prof.get("current_title", "") or ""
    past = [(r.get("title", "") or "") for r in cand.get("career_history", []) or []
            if not r.get("is_current")]
    return D.domain_profile(cur, past, prose)


def role_fit(cand_profile, jdspec):
    """Cosine of candidate domain vector vs the JD domain vector (0..1)."""
    return max(0.0, min(1.0, D.cosine(cand_profile, jdspec.profile)))


# --------------------------------------------------------------------------- #
# Experience  — from the parsed JD band
# --------------------------------------------------------------------------- #
def experience_score(cand, jdspec):
    yoe = float((cand.get("profile", {}) or {}).get("years_of_experience") or 0)
    lo, hi, ideal = jdspec.exp_min, jdspec.exp_max, jdspec.exp_ideal
    if lo <= 0 and hi >= 50:
        return 0.7                                   # JD states no band -> neutral
    center = ideal if ideal > 0 else (lo + hi) / 2.0
    half = max(1.0, (hi - lo) / 2.0)
    if lo <= yoe <= hi:
        return max(0.82, 1.0 - 0.18 * abs(yoe - center) / half)
    dist = (lo - yoe) if yoe < lo else (yoe - hi)
    return max(0.08, 0.80 - 0.13 * dist)


# --------------------------------------------------------------------------- #
# Location  — from the parsed JD
# --------------------------------------------------------------------------- #
def location_score(cand, jdspec):
    if not jdspec.has_location_pref:
        return 0.7                                   # JD is location-agnostic
    prof = cand.get("profile", {}) or {}
    sig = cand.get("redrob_signals", {}) or {}
    loc = (prof.get("location") or "").lower()
    country = (prof.get("country") or "").lower()
    relocate = bool(sig.get("willing_to_relocate"))

    if jdspec.locations and _contains_any(loc, jdspec.locations):
        return 1.0
    jd_countries = jdspec.countries or (["india"] if jdspec.locations else [])
    same_country = any(c in country for c in jd_countries)
    if same_country:
        # right country, different city
        return 0.82 if not jdspec.locations else (0.78 if relocate else 0.68)
    # different country: visa/relocation friction
    return 0.35 if relocate else 0.15


# --------------------------------------------------------------------------- #
# Keyword evidence  — JD's salient terms found in the candidate's PROSE
# --------------------------------------------------------------------------- #
def keyword_evidence(prose, jdspec):
    kws = jdspec.keywords or []
    if not kws:
        return 0.5, []
    found = [k for k in kws if k in prose]
    denom = min(10.0, max(5.0, len(kws) * 0.4))
    score = min(1.0, len(found) / denom)
    return score, found[:6]


# --------------------------------------------------------------------------- #
# Company type  — product vs services (only meaningful for tech roles)
# --------------------------------------------------------------------------- #
def company_type_score(cand, jdspec):
    if not (set(jdspec.target_domains) & TECH_DOMAINS):
        return 0.65                                  # non-tech JD: don't distort
    history = cand.get("career_history", []) or []
    prof = cand.get("profile", {}) or {}
    if not history:
        industry = (prof.get("current_industry") or "").lower()
        return 0.5 if _contains_any(industry, C.PRODUCT_INDUSTRIES) else 0.3

    n = len(history)
    consulting = product = nontech = 0
    for r in history:
        comp = (r.get("company") or "").lower()
        ind = (r.get("industry") or "").lower()
        if _contains_any(comp, C.CONSULTING_COMPANIES) or _contains_any(ind, C.CONSULTING_INDUSTRIES):
            consulting += 1
        elif _contains_any(ind, C.PRODUCT_INDUSTRIES):
            product += 1
        elif _contains_any(ind, C.NONTECH_INDUSTRIES):
            nontech += 1

    score = 0.45 + 0.55 * (product / n) - 0.30 * (consulting / n) - 0.45 * (nontech / n)
    if consulting == n and n >= 2:
        score = min(score, 0.18)
    if nontech / n >= 0.8 and product == 0:
        score = min(score, 0.20)
    return max(0.0, min(1.0, score))


# --------------------------------------------------------------------------- #
# Keyword-stuffing  — JD terms crammed in skills[] but role doesn't match
# --------------------------------------------------------------------------- #
def stuffing_penalty(cand, jdspec, role_fit_score):
    skills = cand.get("skills", []) or []
    if not skills:
        return 1.0
    jd_kw = set(jdspec.keywords)
    hits = sum(1 for s in skills
               if (s.get("name") or "").strip().lower() in jd_kw)
    if hits >= 4 and role_fit_score < 0.45:
        severity = min(1.0, hits / 8.0) * (0.45 - role_fit_score) / 0.45
        return 1.0 - C.STUFFER_PENALTY_MAX * severity
    return 1.0


# --------------------------------------------------------------------------- #
# Negative-specialty penalty  (JD's own exclusions)
# --------------------------------------------------------------------------- #
def negative_penalty(cand, jdspec, evidence_score):
    """
    If the JD explicitly excludes a specialty and the candidate's current title
    is that specialty, down-weight them — softened when they also show strong
    positive evidence (the JD's 'X without significant Y exposure' caveat).
    """
    negs = jdspec.negative_terms
    if not negs:
        return 1.0
    title = ((cand.get("profile", {}) or {}).get("current_title") or "").lower()
    if not any(n in title for n in negs):
        return 1.0
    return 0.80 if evidence_score >= 0.9 else 0.60


# --------------------------------------------------------------------------- #
# Title-chasing  (JD-agnostic)
# --------------------------------------------------------------------------- #
def job_hopping_penalty(cand):
    completed = [r for r in (cand.get("career_history", []) or []) if not r.get("is_current")]
    if len(completed) < 3:
        return 1.0
    durations = [r.get("duration_months") or 0 for r in completed]
    avg = sum(durations) / len(durations)
    if avg < 16 and len(completed) >= 3:
        return 0.85
    if avg < 20 and len(completed) >= 4:
        return 0.92
    return 1.0


# --------------------------------------------------------------------------- #
# Behavioral availability  (JD-agnostic)
# --------------------------------------------------------------------------- #
def _recency_score(last_active, ref="2026-06-20"):
    try:
        ly, lm = int(last_active[:4]), int(last_active[5:7])
        ry, rm = int(ref[:4]), int(ref[5:7])
        months = (ry - ly) * 12 + (rm - lm)
    except (TypeError, ValueError):
        return 0.5
    if months <= 1:
        return 1.0
    if months <= 3:
        return 0.85
    if months <= 6:
        return 0.6
    if months <= 12:
        return 0.3
    return 0.12


def behavioral_multiplier(cand):
    sig = cand.get("redrob_signals", {}) or {}
    parts = []
    rr = sig.get("recruiter_response_rate")
    if rr is not None:
        parts.append((0.30, min(1.0, rr / 0.6)))
    parts.append((0.25, _recency_score(sig.get("last_active_date"))))
    parts.append((0.12, 1.0 if sig.get("open_to_work_flag") else 0.55))
    icr = sig.get("interview_completion_rate")
    if icr is not None:
        parts.append((0.10, min(1.0, icr)))
    npd = sig.get("notice_period_days")
    if npd is not None:
        nps = 1.0 if npd <= 30 else 0.8 if npd <= 60 else 0.6 if npd <= 90 else 0.4
        parts.append((0.10, nps))
    pcs = sig.get("profile_completeness_score")
    if pcs is not None:
        parts.append((0.07, min(1.0, pcs / 90.0)))
    verified = (1.0 if sig.get("verified_email") else 0.0) + \
               (1.0 if sig.get("verified_phone") else 0.0)
    parts.append((0.06, verified / 2.0))

    wsum = sum(w for w, _ in parts)
    raw = sum(w * v for w, v in parts) / max(1e-9, wsum)
    return C.BEHAVIORAL_MIN + (C.BEHAVIORAL_MAX - C.BEHAVIORAL_MIN) * raw


# --------------------------------------------------------------------------- #
# Verified corroboration  (JD-aware: assessment scores on JD-relevant skills)
# --------------------------------------------------------------------------- #
def verified_corroboration(cand, jdspec):
    sig = cand.get("redrob_signals", {}) or {}
    assess = sig.get("skill_assessment_scores", {}) or {}
    jd_kw = set(jdspec.keywords)
    rel = [v for k, v in assess.items()
           if (k or "").strip().lower() in jd_kw and isinstance(v, (int, float))]
    if not rel:                                       # fall back to any assessment
        rel = [v for v in assess.values() if isinstance(v, (int, float))]
    if rel:
        avg_assess = sum(rel) / len(rel)
        assess_term = max(-0.5, min(1.0, (avg_assess - 55.0) / 35.0))
    else:
        avg_assess, assess_term = None, 0.0

    gh = sig.get("github_activity_score")
    if gh is None or gh < 0:
        gh_term, gh_val = 0.0, None
    else:
        gh_val = gh
        gh_term = max(-0.3, min(1.0, (gh - 35.0) / 45.0))
    # GitHub only matters for tech roles
    if not (set(jdspec.target_domains) & TECH_DOMAINS):
        gh_term = 0.0

    mult = 1.0 + 0.05 * assess_term + 0.03 * gh_term
    mult = max(0.95, min(1.08, mult))
    return mult, {"avg_assessment": avg_assess, "github": gh_val,
                  "n_relevant_assessments": len(rel)}
