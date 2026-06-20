"""
Score combination — JD-driven.

    base   = Σ weight_i · component_i          (interpretable, sums to 1)
    final  = base · behavioral · verified · stuffer · hop · honeypot

All components are computed against the parsed JDSpec, so the same code scores
any job description. The multiplicative gates (availability, verified ability,
keyword-stuffing, title-chasing, internal-impossibility) are JD-agnostic.
"""
from . import config as C, features as F, honeypot, text as T


def score_candidate(cand, semantic_sim, jdspec, embed_sim=None, weights=None):
    """Returns (final_score, parts_dict)."""
    w = weights or C.WEIGHTS
    prose = T.candidate_text(cand)

    sem = 0.5 * semantic_sim + 0.5 * embed_sim if embed_sim is not None else semantic_sim

    cand_profile = F.candidate_domain_profile(cand, prose)
    role = F.role_fit(cand_profile, jdspec)
    ev_score, ev_terms = F.keyword_evidence(prose, jdspec)
    exp = F.experience_score(cand, jdspec)
    comp = F.company_type_score(cand, jdspec)
    locs = F.location_score(cand, jdspec)

    base = (
        w["role_fit"] * role +
        w["semantic"] * sem +
        w["evidence"] * ev_score +
        w["experience"] * exp +
        w["company_type"] * comp +
        w["location"] * locs
    )

    behavioral = F.behavioral_multiplier(cand)
    verified, verified_info = F.verified_corroboration(cand, jdspec)
    stuffer = F.stuffing_penalty(cand, jdspec, role)
    negative = F.negative_penalty(cand, jdspec, ev_score)
    hop = F.job_hopping_penalty(cand)
    hard, soft, reasons = honeypot.check(cand)

    final = base * behavioral * verified * stuffer * negative * hop * soft
    if hard:
        final *= C.HONEYPOT_MULTIPLIER

    parts = {
        "role_fit": role,
        "domain_profile": cand_profile,
        "semantic": sem,
        "tfidf": semantic_sim,
        "evidence": ev_score,
        "evidence_terms": ev_terms,
        "experience": exp,
        "company_type": comp,
        "location": locs,
        "behavioral": behavioral,
        "verified": verified,
        "verified_info": verified_info,
        "stuffer": stuffer,
        "negative": negative,
        "hop": hop,
        "honeypot_hard": hard,
        "honeypot_reasons": reasons,
        "base": base,
    }
    return final, parts
