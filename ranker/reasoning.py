"""
Reasoning generation — JD-aware and grounded.

Stage-4 review penalises empty / identical / templated reasoning, hallucinated
skills, and reasoning that contradicts the rank. Every sentence here is built
ONLY from facts in the candidate's own profile plus the scores we computed, and
adapts to the actual JD (its target domain and matched keywords) and to where
the candidate landed.
"""
from . import domains as D


def _role_phrase(cand):
    p = cand.get("profile", {}) or {}
    title = p.get("current_title") or "professional"
    yoe = p.get("years_of_experience")
    yoe_s = f"{yoe:.1f} yrs" if isinstance(yoe, (int, float)) else "unknown tenure"
    return f"{title} with {yoe_s}"


def _location_phrase(cand):
    p = cand.get("profile", {}) or {}
    sig = cand.get("redrob_signals", {}) or {}
    loc = p.get("location") or p.get("country") or "location unknown"
    country = (p.get("country") or "").lower()
    if "india" in country:
        return loc
    tail = ", open to relocate)" if sig.get("willing_to_relocate") else ")"
    return f"{loc} (outside India" + tail


def build(cand, parts, rank, jdspec):
    sig = cand.get("redrob_signals", {}) or {}
    role = _role_phrase(cand)
    loc = _location_phrase(cand)
    jd_dom = (jdspec.target_domains or ["the"])[0]
    jd_label = D.DOMAIN_LABELS.get(jd_dom, "the target")

    sentences = []
    rf = parts["role_fit"]
    terms = parts.get("evidence_terms") or []
    term_str = ", ".join(terms[:3])

    # ---- lead: who they are + how well the role matches ----
    if rf >= 0.6:
        match = f"strong match to the {jd_label} role"
    elif rf >= 0.35:
        match = f"partial/adjacent match to the {jd_label} role"
    else:
        match = f"limited match to the {jd_label} role"

    extras = []
    if term_str:
        extras.append(f"profile mentions {term_str}")
    vinfo = parts.get("verified_info") or {}
    aa = vinfo.get("avg_assessment")
    if aa is not None and aa >= 75:
        extras.append(f"verified assessment avg {aa:.0f}/100")
    if parts["company_type"] >= 0.7 and (set(jdspec.target_domains) &
                                         {"ai_ml", "software", "data_eng", "devops", "frontend", "mobile", "qa"}):
        extras.append("product-company background")

    if rf < 0.35 and parts["stuffer"] < 0.85:
        lead = (f"{role}; {match} — skills list carries relevant keywords but the "
                f"actual role and history do not back them up; based in {loc}.")
    else:
        tail = ("; " + "; ".join(extras[:2])) if extras else ""
        lead = f"{role}; {match}{tail}; based in {loc}."
    sentences.append(lead)

    # ---- concerns / availability (honest) ----
    concerns = []
    rr = sig.get("recruiter_response_rate")
    if rr is not None and rr < 0.25:
        concerns.append(f"low recruiter response rate ({rr:.0%})")
    npd = sig.get("notice_period_days")
    if npd is not None and npd >= 90:
        concerns.append(f"long notice period ({npd}d)")
    if parts["behavioral"] < 0.8:
        concerns.append("weak recent platform activity")
    if parts["company_type"] <= 0.25 and rf >= 0.5:
        concerns.append("services-heavy background")
    if parts["honeypot_reasons"]:
        concerns.append("profile has internal inconsistencies")

    if rank <= 25 and not concerns:
        if rr is not None and rr >= 0.5:
            sentences.append(f"Responsive on the platform (response rate {rr:.0%}).")
        else:
            sentences.append("Solid overall fit on role, experience and location.")
    elif concerns:
        sentences.append("Concerns: " + "; ".join(concerns[:3]) + ".")

    return " ".join(" ".join(sentences).split()).replace('"', "'")
