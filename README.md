<h1 align="center">🧭 Redrob Candidate Ranker</h1>

<p align="center"><b>Ranks candidates the way a great recruiter would — by understanding careers, not matching keywords.</b></p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%E2%80%933.14-3776AB?logo=python&logoColor=white">
  <img alt="CPU only" src="https://img.shields.io/badge/compute-CPU%20only-success">
  <img alt="No network" src="https://img.shields.io/badge/ranking-no%20network%20%C2%B7%20no%20LLM-blueviolet">
  <img alt="Runtime" src="https://img.shields.io/badge/100K%20pool-~2%20min-orange">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-black">
</p>

---

A **JD-adaptive** ranker that returns the top-100 candidates from a 100,000-
candidate pool for *any* job description. We demonstrate it on the Redrob
*Senior AI Engineer* JD, but paste a Marketing Manager or Civil Engineer JD and
it adapts: the role domain, experience band, location and excluded specialties
are all parsed from the JD text at run time.

> The dataset is a trap for keyword matchers. Most candidates have a randomly
> stuffed skills list (an *Accountant* with "Image Classification", a *Marketing
> Manager* with a full AI stack). A pure embedding/keyword ranker ranks those
> non-fits at the top — exactly what the JD warns against. This ranker reads the
> **title + career history + prose** to find people who actually match the role,
> and gates out stuffers, excluded specialties, unavailable candidates, and
> impossible "honeypot" profiles.

**How it adapts:** [`ranker/jdspec.py`](ranker/jdspec.py) parses the JD into a
target **role-domain vector** (over ~18 occupational domains defined in
[`ranker/domains.py`](ranker/domains.py)), an experience band, target locations,
salient keywords, and any *excluded* specialties from a "do NOT want" section.
**Role fit** is then the cosine between each candidate's own domain vector (built
from their titles + prose, never the stuffable skills list) and the JD's — so an
AI JD surfaces ML engineers and a marketing JD surfaces marketers, with the same
code.

---

## TL;DR — reproduce the submission

```bash
pip install -r requirements.txt
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

- **~2 minutes** on a 16 GB CPU machine for the full 100K pool.
- **No GPU, no network, no hosted-LLM calls** during ranking.
- Output passes the official `validate_submission.py` unchanged.

```bash
python validate_submission.py submission.csv     # -> "Submission is valid."
```

**Results on the released pool (top-100):** every pick is a genuine ML/AI/IR
role, **100 % India-based**, **54 / 100 in the ideal 6–8 yr band**, and
**0 honeypots** (disqualification threshold is 10) — no honeypot special-casing,
they simply fail the internal-consistency gate.

---

## Why this approach

The JD is explicit about what it does and does **not** want, and the dataset
encodes those as traps. Our reading, mapped to code:

| JD signal | How we encode it |
|---|---|
| "NOT the candidate with the most AI keywords" | **Role/domain fit dominates** (weight 0.36) — candidate-vs-JD domain cosine built from titles + prose. A non-matching title (Accountant for an AI JD) scores low no matter how stuffed the skills list is. |
| "A Marketing Manager with a perfect AI skill list is not a fit" | **Keyword-stuffing penalty**: many JD-keyword skills + poor role fit → multiplicative down-weight. |
| "...a candidate who built a recommendation system at a product company is a fit, even without buzzwords" | **Semantic match on prose** (summary + career descriptions, not the skills array) + **JD-keyword evidence** found in that prose. Prose evidence can *lift* a generic "Software Engineer" toward the role. |
| "only ever worked at consulting firms ... not a fit" | **Product-vs-services** score (tech roles only); an all-consulting (TCS/Infosys/…) or all-non-tech career is capped. |
| "computer vision / speech / robotics without NLP/IR" | **Excluded-specialty penalty** — the JD's "do NOT want" section is parsed; candidates whose title is an excluded specialty are down-weighted (softened if they show strong positive evidence). Fully general: any JD's exclusions are honoured. |
| "5–9 years, ideal 6–8" | **Experience-band** score, parsed from the JD, peaking at the band's centre. |
| "Located in or willing to relocate to Noida/Pune" | **Location** score from JD-parsed cities/countries: exact city > same country > relocate > abroad. |
| "Title-chasers ... switching every 1.5 years" | **Job-hopping penalty** on short average tenure across many roles. |
| "hasn't logged in for 6 months / 5% response rate is not actually available" | **Behavioral availability multiplier** (response rate, recency, open-to-work, notice, verification). |
| "we need to SEE how you think, not just trust that you can" | **Verified corroboration** — Redrob assessment scores + GitHub activity gently lift candidates whose verified signals back up their claims. |
| "~80 honeypots with subtly impossible profiles → tier 0; >10% in top 100 disqualifies" | **Internal-consistency / honeypot gate** (role longer than whole career, expert skills with 0 months used, impossible date spans, inverted salary, …). |

### Scoring model

```
base   = 0.36·role_fit + 0.18·semantic + 0.16·evidence
       + 0.10·experience + 0.10·company_type + 0.10·location      # sums to 1.0

final  = base
       × behavioral_multiplier      # availability  (0.55 … 1.12)
       × verified_corroboration     # assessment scores + GitHub (0.95 … 1.08)
       × stuffing_penalty           # JD-keyword stuffing
       × negative_penalty           # candidate is an excluded specialty
       × job_hopping_penalty        # title-chasing
       × consistency_penalty        # mild internal contradictions
       × honeypot_gate              # 0.02 if impossible profile
```

where `role_fit = cosine(candidate_domain_vector, jd_domain_vector)` and the JD
vector / band / locations / excluded specialties all come from parsing the JD.

**Verified corroboration** is the key differentiator *within* the strong
cohort: self-reported skills are stuffable, but Redrob **skill-assessment
scores** and **GitHub activity** are platform-verified and far harder to fake —
directly answering the JD's "we need to *see* how you think, not just trust
that you can".

The scoring weights and company lists live in
[`ranker/config.py`](ranker/config.py); the role taxonomy in
[`ranker/domains.py`](ranker/domains.py); JD parsing in
[`ranker/jdspec.py`](ranker/jdspec.py). Nothing is hard-coded to one role, so
every ranking decision is auditable and the system generalises to any JD.

### Works for any JD (not just the AI role)

```bash
python rank.py --candidates ./candidates.jsonl --jd ./my_other_jd.txt --out out.csv
```

| JD pasted | Parsed domain | Top-100 result |
|---|---|---|
| Senior AI Engineer | `ai_ml` | ML / AI / NLP / Recommendation engineers, 5–9y, India |
| Senior Marketing Manager | `marketing` | Marketing Managers + Content Writers, 6–10y, Mumbai |

Same code path, no per-JD tuning — the sandbox lets you try this interactively.

### Semantic engine: TF-IDF by default, embeddings optional

The ranking step must run on CPU, offline, in ≤5 min for 100K candidates — so a
hosted LLM or per-candidate model call is out. The default semantic signal is
**TF-IDF cosine** (uni/bi-gram, sublinear) over each candidate's prose vs the
JD — fast, deterministic, fully self-contained.

An **optional dense booster** ([`precompute_embeddings.py`](precompute_embeddings.py))
encodes candidates with a small `sentence-transformers` model *offline* and
saves a plain `.npz` artifact. If `artifacts/candidate_embeddings.npz` is
present, `rank.py` auto-detects it and blends dense + sparse similarity 50/50.
No artifact → TF-IDF only. Either way the ranking step makes **zero** network
calls.

```bash
# optional, offline pre-computation (may exceed 5 min — that's allowed):
pip install -r requirements-embeddings.txt
python precompute_embeddings.py --candidates ./candidates.jsonl
python rank.py --candidates ./candidates.jsonl --out ./submission.csv   # now hybrid
```

---

## Repository layout

```
redrob-ranker/
├── rank.py                  # single-command entry point -> submission.csv
├── job_description.txt      # the JD we rank against
├── ranker/
│   ├── domains.py           # ~18 occupational domains + domain-vector profiles
│   ├── jdspec.py            # JD parser: domain, experience, location, exclusions
│   ├── config.py            # weights, company lists, gate bounds (auditable)
│   ├── text.py              # prose extraction + TF-IDF semantic similarity
│   ├── features.py          # JD-driven role fit, experience, location, behavioral
│   ├── honeypot.py          # internal-consistency / impossible-profile detector
│   ├── scoring.py           # combines base components + multiplicative gates
│   ├── reasoning.py         # grounded, varied, JD-aware 1–2 sentence reasoning
│   └── pipeline.py          # shared pipeline used by rank.py and app.py
├── precompute_embeddings.py # OPTIONAL dense embedding booster (offline)
├── app.py                   # Streamlit sandbox demo (hosted-link requirement)
├── requirements.txt         # core deps (numpy, scikit-learn, scipy, streamlit)
├── requirements-embeddings.txt  # optional sentence-transformers + torch
├── submission_metadata.yaml # portal metadata mirror
└── validate_submission.py   # official format validator (copy from bundle)
```

---

## Sandbox / demo

`app.py` is an interactive Streamlit app that runs the **exact same pipeline**
on a small uploaded sample (≤100 candidates) and returns a ranked CSV. It ships
with a bundled 70-candidate demo so it works out-of-the-box, plus:

- **Live weight tuning** — drag the six component sliders and watch the ranking re-order instantly.
- **Filters** — India-only, minimum experience, hide flagged (honeypot/stuffer) profiles.
- **KPI cards + insights charts** — role mix, score distribution, experience-vs-score scatter.
- **Per-candidate explainability** — component contribution breakdown, the multiplicative gates, full career history and verified signals, and the generated reasoning.

```bash
streamlit run app.py
```

**Free hosting (Streamlit Community Cloud):** push this repo to GitHub →
share.streamlit.io → "New app" → pick this repo and `app.py`. Put the resulting
URL in `submission_metadata.yaml` → `sandbox_link`.

---

## Compute & reproducibility

| Constraint | This system |
|---|---|
| Runtime ≤ 5 min | ~2 min for 100K (TF-IDF path) |
| Memory ≤ 16 GB | well under (sparse TF-IDF + streamed JSONL) |
| CPU only | yes — no GPU anywhere |
| Network off | yes — no API/LLM calls in `rank.py` |
| Disk ≤ 5 GB | optional embedding artifact ≈ 150 MB |

Tested on Python 3.11–3.14. `candidates.jsonl` is **not** committed (see
`.gitignore`); place it next to `rank.py` or pass `--candidates <path>`.

## Honeypot self-check

The ranker does not special-case the ~80 honeypots; it scores internal
consistency and lets impossible profiles fall out. On the released pool the
top-100 honeypot rate is **0%** (limit for disqualification is 10%). Inspect any
run with:

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv --audit audit.json
```

`audit.json` shows the per-component breakdown for every ranked candidate.
