"""
Honeypot / internal-consistency detection.

The dataset hides ~80 honeypots with "subtly impossible" profiles and forces
them to relevance tier 0. A submission with >10% honeypots in the top 100 is
disqualified at Stage 3. We do NOT try to special-case the exact 80 — we detect
*genuine impossibilities* (a role longer than the person's whole career, mastery
of skills never used, tenure that exceeds the role's own dates) and let those
profiles fall out.

IMPORTANT — what we deliberately do NOT flag: things that look odd but are just
synthetic-data noise present in ~19% of *all* candidates (e.g. expected-salary
min > max, or a career start year a bit before the listed education start).
Flagging those would bury thousands of legitimate candidates, so the gate is
kept tight: only physically impossible tenure / mastery facts trip it.

Returns (is_honeypot, consistency_penalty, reasons).
"""


def _parse_year(d):
    if not d:
        return None
    try:
        return int(str(d)[:4])
    except (ValueError, TypeError):
        return None


def check(cand):
    reasons = []
    hard = False

    profile = cand.get("profile", {}) or {}
    yoe = float(profile.get("years_of_experience") or 0)
    history = cand.get("career_history", []) or []
    skills = cand.get("skills", []) or []

    yoe_months = yoe * 12.0

    # 1. A single role lasting longer than the person's entire career. -------
    for role in history:
        dur = role.get("duration_months") or 0
        if yoe_months > 0 and dur > yoe_months + 12:   # 12-month slack
            hard = True
            reasons.append(
                f"role '{role.get('title','?')}' lasts {dur}mo but total "
                f"experience is only {yoe:.1f}y"
            )
            break

    # 2. Career durations summing to far more than total experience. ---------
    total_role_months = sum((r.get("duration_months") or 0) for r in history)
    if yoe_months > 0 and total_role_months > yoe_months * 2.0 and len(history) >= 2:
        hard = True
        reasons.append(
            f"career roles sum to {total_role_months}mo vs {yoe_months:.0f}mo "
            f"of stated experience (impossible overlap)"
        )

    # 3. "Expert"/"advanced" mastery in skills never actually used. ----------
    #    The spec's own honeypot example: 'expert proficiency in 10 skills with
    #    0 years used'. Genuine signal, hard to occur by chance.
    mastery_zero = 0
    for s in skills:
        prof = (s.get("proficiency") or "").lower()
        dur = s.get("duration_months")
        if prof in ("expert", "advanced") and dur is not None and dur == 0:
            mastery_zero += 1
    if mastery_zero >= 5:
        hard = True
        reasons.append(f"{mastery_zero} skills marked expert/advanced with 0 months used")
    elif mastery_zero >= 3:
        reasons.append(f"{mastery_zero} expert/advanced skills with 0 months used")

    # 4. duration_months inconsistent with a role's own start/end dates. ------
    for role in history:
        sy = _parse_year(role.get("start_date"))
        ey = _parse_year(role.get("end_date"))
        dur = role.get("duration_months") or 0
        if sy and ey:
            span = (ey - sy) * 12
            if dur > span + 30:           # claims much longer than the dates allow
                hard = True
                reasons.append(
                    f"role '{role.get('title','?')}' claims {dur}mo over a "
                    f"{span}mo date span"
                )
                break

    # soft penalty scales with the (now rare) mild contradictions
    soft = max(0.6, 1.0 - 0.2 * len(reasons))
    return hard, soft, reasons
