"""
Redrob Ranker — interactive sandbox demo (Streamlit).

Satisfies the hackathon's mandatory "sandbox / demo link" requirement: a hosted
environment that accepts a small candidate sample (<=100), runs the *exact same*
ranking pipeline used for the submission, and returns a ranked CSV — on CPU, no
network, well within the 5-minute budget.

Extras that make it a real demo, not just a CSV button:
  * live weight tuning (re-ranks instantly)
  * filters (India-only, min experience, hide flagged profiles)
  * KPI cards + insights charts
  * per-candidate explainability: component breakdown, gates, full profile

Run locally:   streamlit run app.py
Deploy free:   push this repo to GitHub -> Streamlit Community Cloud -> app.py
"""
import io
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

from ranker.config import WEIGHTS
from ranker.pipeline import rank_candidates

st.set_page_config(page_title="Redrob Candidate Ranker",
                   page_icon="🧭", layout="wide")

HERE = os.path.dirname(__file__)
JD_PATH = os.path.join(HERE, "job_description.txt")
with open(JD_PATH, "r", encoding="utf-8") as f:
    DEFAULT_JD = f.read()

# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
:root { --indigo:#6366F1; --navy:#0F172A; --muted:#64748B; }
.block-container { padding-top: 1.4rem; max-width: 1400px; }
.hero {
  background: linear-gradient(110deg, #0F172A 0%, #312E81 55%, #4338CA 100%);
  border-radius: 18px; padding: 26px 32px; color: #fff; margin-bottom: 18px;
  box-shadow: 0 10px 30px rgba(49,46,129,.25);
}
.hero h1 { font-size: 2.05rem; margin: 0 0 4px 0; font-weight: 800; letter-spacing:-.5px;}
.hero p  { margin: 0; color: #C7D2FE; font-size: 1.02rem; }
.kpi {
  background:#fff; border:1px solid #E2E8F0; border-radius:14px; padding:16px 18px;
  box-shadow:0 2px 8px rgba(15,23,42,.04);
}
.kpi .v { font-size:1.9rem; font-weight:800; color:#0F172A; line-height:1; }
.kpi .l { font-size:.82rem; color:#64748B; margin-top:6px; text-transform:uppercase; letter-spacing:.5px;}
.badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.78rem; font-weight:700; }
.b-good { background:#ECFDF5; color:#059669; }
.b-warn { background:#FFFBEB; color:#D97706; }
.b-bad  { background:#FEF2F2; color:#DC2626; }
.reason-box {
  background:#F8FAFC; border-left:4px solid #6366F1; border-radius:8px;
  padding:14px 18px; color:#1E293B; font-size:1.02rem;
}
.small { color:#64748B; font-size:.85rem; }
section[data-testid="stSidebar"] { background:#0F172A; }
section[data-testid="stSidebar"] * { color:#E2E8F0; }
section[data-testid="stSidebar"] h2 { color:#fff; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="hero"><h1>🧭 Redrob Candidate Ranker</h1>'
    '<p>Ranks candidates for the <b>Senior AI Engineer — Founding Team</b> role by '
    'reading careers, not keywords. Same pipeline as the submission CSV.</p></div>',
    unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def parse_upload(uploaded):
    raw = uploaded.getvalue().decode("utf-8").strip()
    if not raw:
        return []
    if raw[0] == "[":
        return json.loads(raw)
    return [json.loads(l) for l in raw.splitlines() if l.strip()]


def load_bundled():
    p = os.path.join(HERE, "sample_candidates.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


# --------------------------------------------------------------------------- #
# Sidebar controls
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    src = st.radio("Candidate sample", ["Bundled demo (70)", "Upload file"], index=0)
    uploaded = None
    if src == "Upload file":
        uploaded = st.file_uploader("≤100 candidates (.jsonl / .json)",
                                    type=["jsonl", "json"])

    top_n = st.slider("Show top N", 5, 100, 20, 1)

    st.markdown("### 🔎 Filters")
    india_only = st.checkbox("India-based only", value=False)
    min_yoe = st.slider("Min years of experience", 0, 15, 0, 1)
    hide_flagged = st.checkbox("Hide honeypots / stuffers", value=True)

    st.markdown("### 🎚️ Tune weights (live)")
    st.caption("Re-ranks instantly. Normalised to sum 1.")
    with st.expander("Adjust component weights", expanded=False):
        if "reset" not in st.session_state:
            st.session_state.reset = 0
        w_role = st.slider("Role / career fit", 0.0, 0.6, WEIGHTS["role_fit"], 0.01)
        w_sem = st.slider("Semantic match", 0.0, 0.5, WEIGHTS["semantic"], 0.01)
        w_ev = st.slider("Evidence", 0.0, 0.5, WEIGHTS["evidence"], 0.01)
        w_exp = st.slider("Experience", 0.0, 0.4, WEIGHTS["experience"], 0.01)
        w_comp = st.slider("Company type", 0.0, 0.4, WEIGHTS["company_type"], 0.01)
        w_loc = st.slider("Location", 0.0, 0.4, WEIGHTS["location"], 0.01)
    raw_w = {"role_fit": w_role, "semantic": w_sem, "evidence": w_ev,
             "experience": w_exp, "company_type": w_comp, "location": w_loc}
    tot = sum(raw_w.values()) or 1.0
    weights = {k: v / tot for k, v in raw_w.items()}

    st.markdown("### 📝 Job description")
    jd_text = st.text_area("Edit to re-rank", DEFAULT_JD, height=140,
                           label_visibility="collapsed")


# --------------------------------------------------------------------------- #
# Resolve candidates
# --------------------------------------------------------------------------- #
if src == "Upload file":
    if uploaded is None:
        st.info("⬆️ Upload a .jsonl / .json sample in the sidebar, or switch to the bundled demo.")
        st.stop()
    try:
        cands = parse_upload(uploaded)
    except Exception as e:                     # noqa: BLE001
        st.error(f"Could not parse file: {e}")
        st.stop()
else:
    cands = load_bundled()
    if not cands:
        st.error("Bundled sample not found. Switch to Upload file.")
        st.stop()

cands = cands[:100]
id2cand = {c.get("candidate_id"): c for c in cands}

# Rank everyone, then apply UI filters on the result (so ranks stay meaningful).
rows, audit, jdspec = rank_candidates(cands, jd_text, top=len(cands), weights=weights)
df = pd.DataFrame(audit)


def flag(r):
    if r["honeypot"]:
        return "🚫 honeypot"
    if r["stuffer"] < 0.9:
        return "⚠️ stuffer"
    if r.get("negative", 1.0) < 1.0:
        return "🔻 excluded specialty"
    return "✓ clean"


df["flag"] = df.apply(flag, axis=1)

fdf = df.copy()
if india_only:
    fdf = fdf[fdf["country"] == "India"]
if min_yoe > 0:
    fdf = fdf[fdf["yoe"] >= min_yoe]
if hide_flagged:
    fdf = fdf[(~fdf["honeypot"]) & (fdf["stuffer"] >= 0.9)]
fdf = fdf.head(top_n).reset_index(drop=True)

# --------------------------------------------------------------------------- #
# KPI cards
# --------------------------------------------------------------------------- #
k1, k2, k3, k4 = st.columns(4)
top10 = df.head(10)
cards = [
    (k1, f"{len(cands)}", "candidates ranked"),
    (k2, f"{int((df['country'] == 'India').mean() * 100)}%", "India-based (all)"),
    (k3, f"{int(df['honeypot'].sum())}", "honeypots flagged"),
    (k4, f"{top10['yoe'].mean():.1f}y", "avg exp · top 10"),
]
for col, v, l in cards:
    col.markdown(f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div></div>',
                 unsafe_allow_html=True)
st.write("")

# What the parser understood — proves the ranker adapts to ANY JD pasted above.
from ranker.domains import DOMAIN_LABELS
doms = ", ".join(DOMAIN_LABELS.get(d, d) for d in jdspec.target_domains) or "general"
exp = ("any" if jdspec.exp_min <= 0 and jdspec.exp_max >= 50
       else f"{jdspec.exp_min:.0f}–{jdspec.exp_max:.0f} yrs")
locs = ", ".join((jdspec.locations or jdspec.countries) or ["any"])
kw = ", ".join(jdspec.keywords[:8]) or "—"
st.markdown(
    f'<div class="kpi" style="margin-bottom:6px">'
    f'<span class="l">JD understood as</span><br>'
    f'<b>Role domain:</b> {doms} &nbsp;·&nbsp; <b>Experience:</b> {exp} '
    f'&nbsp;·&nbsp; <b>Location:</b> {locs}<br>'
    f'<span class="small"><b>Key terms:</b> {kw}</span></div>',
    unsafe_allow_html=True)
st.write("")

# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #
tab_rank, tab_explain, tab_insights, tab_about = st.tabs(
    ["🏆 Ranking", "🔬 Explainability", "📊 Insights", "ℹ️ About"])

with tab_rank:
    st.markdown(f"**Top {len(fdf)}** after filters · pipeline identical to `rank.py`")
    show = fdf[["rank", "candidate_id", "title", "domain", "yoe", "location",
                "score", "role_fit", "flag", "reasoning"]]
    st.dataframe(
        show, hide_index=True, width='stretch', height=560,
        column_config={
            "rank": st.column_config.NumberColumn("Rank", width="small"),
            "candidate_id": "ID",
            "title": "Current title",
            "domain": "Detected domain",
            "yoe": st.column_config.NumberColumn("Yrs", format="%.1f", width="small"),
            "location": "Location",
            "score": st.column_config.ProgressColumn(
                "Score", min_value=0.0, max_value=1.0, format="%.3f"),
            "role_fit": st.column_config.ProgressColumn(
                "Role fit", min_value=0.0, max_value=1.0, format="%.2f"),
            "flag": "Flag",
            "reasoning": st.column_config.TextColumn("Reasoning", width="large"),
        })
    csv_df = pd.DataFrame(rows)[["candidate_id", "rank", "score", "reasoning"]].head(top_n)
    buf = io.StringIO()
    csv_df.to_csv(buf, index=False)
    st.download_button("⬇️ Download ranked CSV", buf.getvalue(),
                       file_name="ranking.csv", mime="text/csv")

with tab_explain:
    st.markdown("### Why is a candidate ranked here?")
    opts = {f"#{r['rank']} · {r['title']} · {r['candidate_id']}": r["candidate_id"]
            for _, r in fdf.iterrows()}
    if not opts:
        st.info("No candidates match the current filters.")
    else:
        pick = st.selectbox("Pick a candidate", list(opts.keys()))
        cid = opts[pick]
        r = df[df["candidate_id"] == cid].iloc[0]
        cand = id2cand.get(cid, {})
        prof = cand.get("profile", {})

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rank", f"#{int(r['rank'])}")
        c2.metric("Score", f"{r['score']:.3f}")
        c3.metric("Experience", f"{r['yoe']:.1f} yrs")
        c4.metric("Flag", r["flag"])

        left, right = st.columns([1, 1])
        with left:
            st.markdown("**Weighted component contribution**")
            comp = pd.DataFrame({
                "component": ["Role fit", "Semantic", "Evidence",
                              "Experience", "Company", "Location"],
                "value": [r["role_fit"] * weights["role_fit"],
                          r["semantic"] * weights["semantic"],
                          r["evidence"] * weights["evidence"],
                          r["experience"] * weights["experience"],
                          r["company_type"] * weights["company_type"],
                          r["location_score"] * weights["location"]],
            })
            chart = (alt.Chart(comp).mark_bar(cornerRadiusEnd=4, color="#6366F1")
                     .encode(x=alt.X("value:Q", title="contribution to base score"),
                             y=alt.Y("component:N", sort="-x", title=None),
                             tooltip=["component", alt.Tooltip("value:Q", format=".3f")])
                     .properties(height=230))
            st.altair_chart(chart, width='stretch')

            st.markdown("**Multiplicative gates**")
            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Availability", f"×{r['behavioral']:.2f}")
            g2.metric("Verified", f"×{r['verified']:.2f}")
            g3.metric("Stuffer", f"×{r['stuffer']:.2f}")
            g4.metric("Excl. specialty", f"×{r.get('negative', 1.0):.2f}")

        with right:
            st.markdown(f"**{prof.get('current_title','?')}** · {prof.get('current_company','?')} "
                        f"· {prof.get('current_industry','?')}")
            st.markdown(f"<span class='small'>{prof.get('location','?')}, "
                        f"{prof.get('country','?')} · {prof.get('years_of_experience','?')} yrs</span>",
                        unsafe_allow_html=True)
            st.markdown(f'<div class="reason-box">{r["reasoning"]}</div>',
                        unsafe_allow_html=True)
            with st.expander("Career history"):
                for h in cand.get("career_history", [])[:6]:
                    st.markdown(f"**{h.get('title','?')}** — {h.get('company','?')} "
                                f"({h.get('industry','?')}, {h.get('duration_months','?')}mo)")
                    st.caption((h.get("description", "") or "")[:280])
            sig = cand.get("redrob_signals", {})
            with st.expander("Behavioral & verified signals"):
                st.write({
                    "recruiter_response_rate": sig.get("recruiter_response_rate"),
                    "last_active_date": sig.get("last_active_date"),
                    "open_to_work": sig.get("open_to_work_flag"),
                    "notice_period_days": sig.get("notice_period_days"),
                    "github_activity_score": sig.get("github_activity_score"),
                    "skill_assessment_scores": sig.get("skill_assessment_scores"),
                })

with tab_insights:
    cc1, cc2 = st.columns(2)
    with cc1:
        st.markdown("**Top-N role mix**")
        vc = fdf["title"].value_counts().reset_index()
        vc.columns = ["title", "count"]
        ch = (alt.Chart(vc.head(12)).mark_bar(cornerRadiusEnd=4, color="#4338CA")
              .encode(x=alt.X("count:Q", title="count"),
                      y=alt.Y("title:N", sort="-x", title=None),
                      tooltip=["title", "count"]).properties(height=320))
        st.altair_chart(ch, width='stretch')
    with cc2:
        st.markdown("**Score distribution (all ranked)**")
        ch2 = (alt.Chart(df).mark_bar(color="#6366F1")
               .encode(x=alt.X("score:Q", bin=alt.Bin(maxbins=25), title="score"),
                       y=alt.Y("count()", title="candidates"))
               .properties(height=320))
        st.altair_chart(ch2, width='stretch')
    st.markdown("**Experience vs score** (color = role fit)")
    sc = (alt.Chart(df).mark_circle(size=90, opacity=.7)
          .encode(x=alt.X("yoe:Q", title="years of experience"),
                  y=alt.Y("score:Q", title="final score"),
                  color=alt.Color("role_fit:Q", scale=alt.Scale(scheme="purpleblue"),
                                  title="role fit"),
                  tooltip=["candidate_id", "title", "yoe", "score"])
          .properties(height=300).interactive())
    st.altair_chart(sc, width='stretch')

with tab_about:
    st.markdown("""
### How the ranking works — for *any* job description
The dataset is a trap for keyword matchers — most skill lists are random noise
(an *Accountant* with "NLP, FAISS"). This ranker reads **careers, not keywords**,
and adapts to whatever JD you paste above.

**JD parsing** turns the JD into a target **role-domain vector** (over ~18
occupational domains), an experience band, target locations, salient keywords,
and any *excluded* specialties from a "do NOT want" section.

**Base score (weighted, interpretable):**
`role-domain fit (candidate-vs-JD cosine) · semantic match (prose vs JD) ·
JD-keyword evidence · experience band · product-vs-services · location`

**Then multiplicative gates:**
- **Availability** — response rate, recency, notice period
- **Verified** — Redrob assessment scores + GitHub activity (harder to fake than skills)
- **Keyword-stuffing** — many JD-keyword skills + weak role → penalty
- **Excluded specialty** — title matches something the JD says it does NOT want
- **Honeypot** — internally impossible profiles forced out of the top 100

Role fit is a cosine between the candidate's domain vector (from titles + prose,
never the stuffable skills list) and the JD's. Paste an AI JD → ML engineers
rise; paste a marketing JD → marketers rise. Everything is CPU-only, no network,
~2 minutes for the full 100K pool. The same `rank_candidates()` pipeline powers
this demo and the submission CSV.
""")
