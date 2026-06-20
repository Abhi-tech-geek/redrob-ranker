"""
Shared ranking pipeline used by both rank.py (CLI) and app.py (sandbox demo),
so the hosted demo runs the exact same code path as the submission.
"""
import numpy as np

from . import scoring, reasoning, domains as D
from .jdspec import parse_jd
from .text import SemanticIndex, candidate_text


def percentile_scale(arr, p=99.0):
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size == 0:
        return arr
    hi = np.percentile(arr, p)
    if hi <= 1e-9:
        return np.zeros_like(arr)
    return np.clip(arr / hi, 0.0, 1.0)


def rank_candidates(cands, jd_text, top=100, emb_sims=None, weights=None):
    """
    cands     : list of candidate dicts
    jd_text   : job description string (parsed into a JDSpec internally)
    emb_sims  : optional dict candidate_id -> embedding cosine similarity
    weights   : optional dict overriding config.WEIGHTS (live tuning in sandbox)
    returns   : (rows, audit, jdspec)
    """
    jdspec = parse_jd(jd_text)
    ids = [c.get("candidate_id") for c in cands]
    corpus = [candidate_text(c) for c in cands]

    sims = SemanticIndex(jd_text).fit(corpus).similarities()
    p = 99.0 if len(cands) >= 50 else 100.0
    sims_scaled = percentile_scale(sims, p=p)

    n = len(cands)
    finals = np.empty(n, dtype=np.float64)
    parts_all = [None] * n
    for i in range(n):
        es = emb_sims.get(ids[i]) if emb_sims else None
        finals[i], parts_all[i] = scoring.score_candidate(
            cands[i], float(sims_scaled[i]), jdspec, embed_sim=es, weights=weights)

    maxf = float(finals.max()) or 1.0
    rounded = np.round(finals / maxf, 4)
    order = sorted(range(n), key=lambda i: (-rounded[i], ids[i]))[:top]

    rows, audit = [], []
    for rank, i in enumerate(order, start=1):
        reason = reasoning.build(cands[i], parts_all[i], rank, jdspec)
        rows.append({"candidate_id": ids[i], "rank": rank,
                     "score": f"{rounded[i]:.4f}", "reasoning": reason})
        p_ = parts_all[i]
        prof = cands[i].get("profile") or {}
        cand_doms = D.top_domains(p_["domain_profile"], k=2, thresh=0.2)
        audit.append({
            "rank": rank, "candidate_id": ids[i], "score": float(rounded[i]),
            "title": prof.get("current_title"),
            "yoe": prof.get("years_of_experience"),
            "location": prof.get("location"),
            "country": prof.get("country"),
            "company": prof.get("current_company"),
            "industry": prof.get("current_industry"),
            "domain": ", ".join(D.DOMAIN_LABELS.get(d, d) for d in cand_doms) or "—",
            "role_fit": round(p_["role_fit"], 3),
            "semantic": round(p_["semantic"], 3),
            "evidence": round(p_["evidence"], 3),
            "experience": round(p_["experience"], 3),
            "company_type": round(p_["company_type"], 3),
            "location_score": round(p_["location"], 3),
            "behavioral": round(p_["behavioral"], 3),
            "verified": round(p_["verified"], 3),
            "stuffer": round(p_["stuffer"], 3),
            "negative": round(p_["negative"], 3),
            "honeypot": p_["honeypot_hard"],
            "reasoning": reason,
        })
    return rows, audit, jdspec
