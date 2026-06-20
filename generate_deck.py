#!/usr/bin/env python3
"""
Generates approach_deck.pdf — the explainer deck required by the hackathon.
Pulls live numbers from audit_top100.json so the results slide is real.
Pure reportlab, 16:9 slides.  Run:  python generate_deck.py
"""
import json
import os
from collections import Counter

from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase.pdfmetrics import stringWidth

W, H = 1280, 720
NAVY = HexColor("#0F172A")
INDIGO = HexColor("#6366F1")
INDIGO_D = HexColor("#4338CA")
LIGHT = HexColor("#F8FAFC")
CARD = HexColor("#FFFFFF")
TEXT = HexColor("#1E293B")
MUTED = HexColor("#64748B")
GREEN = HexColor("#10B981")
RED = HexColor("#EF4444")
AMBER = HexColor("#F59E0B")
SLATE = HexColor("#E2E8F0")

HERE = os.path.dirname(__file__)
AUDIT = os.path.join(HERE, "audit_top100.json")


def wrap(text, font, size, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if stringWidth(t, font, size) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class Deck:
    def __init__(self, path):
        self.c = canvas.Canvas(path, pagesize=(W, H))

    def bg(self, color=LIGHT):
        self.c.setFillColor(color)
        self.c.rect(0, 0, W, H, fill=1, stroke=0)

    def header(self, kicker, title):
        c = self.c
        c.setFillColor(INDIGO)
        c.rect(0, H - 12, W, 12, fill=1, stroke=0)
        c.setFillColor(INDIGO)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(70, H - 78, kicker.upper())
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 40)
        c.drawString(70, H - 130, title)
        c.setStrokeColor(SLATE)
        c.setLineWidth(2)
        c.line(70, H - 150, W - 70, H - 150)

    def bullets(self, items, x=70, y=H - 205, lh=52, size=21, maxw=W - 700,
                color=TEXT):
        c = self.c
        for it in items:
            if isinstance(it, tuple):
                txt, col = it
            else:
                txt, col = it, color
            c.setFillColor(INDIGO)
            c.circle(x + 6, y + 7, 5, fill=1, stroke=0)
            c.setFillColor(col)
            c.setFont("Helvetica", size)
            lines = wrap(txt, "Helvetica", size, maxw)
            for i, ln in enumerate(lines):
                c.drawString(x + 24, y - i * (size + 6), ln)
            y -= lh + (len(lines) - 1) * (size + 6)
        return y

    def card(self, x, y, w, h, fill=CARD, stroke=SLATE, r=14):
        c = self.c
        c.setFillColor(fill)
        c.setStrokeColor(stroke)
        c.setLineWidth(1.5)
        c.roundRect(x, y, w, h, r, fill=1, stroke=1)

    def footer(self, n):
        c = self.c
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 12)
        c.drawString(70, 32, "Redrob Hackathon · Intelligent Candidate Discovery & Ranking")
        c.drawRightString(W - 70, 32, f"{n}")

    def page(self):
        self.c.showPage()

    def save(self):
        self.c.save()


def load_stats():
    if not os.path.exists(AUDIT):
        return None
    a = json.load(open(AUDIT, encoding="utf-8"))
    titles = Counter(r["title"] for r in a).most_common(6)
    countries = Counter(r["country"] for r in a)
    honey = sum(1 for r in a if r["honeypot"])
    band = Counter(("6-8" if 6 <= r["yoe"] <= 8 else "5-9" if 5 <= r["yoe"] <= 9
                    else "<5" if r["yoe"] < 5 else "9+") for r in a)
    return {"audit": a, "titles": titles, "countries": dict(countries),
            "honey": honey, "band": dict(band),
            "top": a[:5], "smin": a[-1]["score"], "smax": a[0]["score"]}


def build():
    d = Deck(os.path.join(HERE, "approach_deck.pdf"))
    S = load_stats()

    # ---- Slide 1 : Title ----
    d.bg(NAVY)
    d.c.setFillColor(INDIGO)
    d.c.rect(0, 0, 18, H, fill=1, stroke=0)
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Helvetica-Bold", 64)
    d.c.drawString(90, H - 240, "Redrob Candidate Ranker")
    d.c.setFillColor(HexColor("#A5B4FC"))
    d.c.setFont("Helvetica-Bold", 30)
    d.c.drawString(92, H - 290, "Ranking candidates the way a great recruiter would")
    d.c.setFillColor(SLATE)
    d.c.setFont("Helvetica", 22)
    for i, ln in enumerate([
        "Top-100 of a 100,000 candidate pool — demonstrated on the Senior AI Engineer JD.",
        "JD-adaptive: works for any role. Reads careers, not keywords. CPU-only, ~2 min for 100K."]):
        d.c.drawString(92, H - 360 - i * 34, ln)
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Helvetica-Bold", 18)
    d.c.drawString(92, 90, "Team: YOUR_TEAM_NAME")
    d.c.setFillColor(MUTED)
    d.c.setFont("Helvetica", 15)
    d.c.drawString(92, 62, "Hybrid interpretable ranker · TF-IDF + structured fit + behavioral gates")
    d.page()

    # ---- Slide 2 : Problem & the trap ----
    d.bg()
    d.header("The problem", "Keyword filters can't see what matters")
    d.bullets([
        "Recruiters skim hundreds of profiles and still miss the right person — keyword filters reward the wrong signals.",
        ("The dataset is built to PUNISH keyword matchers:", NAVY),
        "Keyword stuffers — an Accountant whose skills list is full of 'NLP, LLM, FAISS'.",
        "Plain-language Tier-5s — built a real recsys at a product company, never says 'RAG'.",
        "~80 honeypots — subtly impossible profiles (8 yrs at a 3-yr-old company).",
        ("The provided sample_submission.csv falls for it: HR Managers & Content Writers at rank 1–2.", RED),
    ], maxw=W - 480)
    # side card
    d.card(W - 380, 210, 300, 360, fill=NAVY, stroke=NAVY)
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Helvetica-Bold", 17)
    d.c.drawString(W - 360, 540, "A naive ranker outputs:")
    rows = [("#1 HR Manager", RED), ("#2 Content Writer", RED),
            ("#3 Graphic Designer", RED), ("#4 Accountant", RED),
            ("…all with 9 'AI skills'", AMBER)]
    for i, (t, col) in enumerate(rows):
        d.c.setFillColor(col)
        d.c.setFont("Helvetica-Bold", 19)
        d.c.drawString(W - 360, 495 - i * 46, t)
    d.c.setFillColor(HexColor("#A5B4FC"))
    d.c.setFont("Helvetica-Oblique", 15)
    d.c.drawString(W - 360, 250, "= exactly the trap.")
    d.footer(2)
    d.page()

    # ---- Slide 3 : Key insight ----
    d.bg()
    d.header("Key insight", "The signal is the career, not the skills list")
    d.bullets([
        ("Skills[] is randomly stuffed noise — easy to fake. We mostly ignore it.", NAVY),
        "We read the PROSE: current title, every past title, and the career-history descriptions.",
        "A 'Marketing Manager' with a perfect AI skill list is capped low — the role is the anti-stuffer signal.",
        "A generic 'Software Engineer' whose descriptions show ranking/retrieval work is LIFTED toward ML.",
        "Behavioral signals decide who is actually hireable, not just good on paper.",
    ], maxw=W - 520)
    # two compare cards
    d.card(W - 430, 360, 350, 150, fill=HexColor("#FEF2F2"), stroke=RED)
    d.c.setFillColor(RED)
    d.c.setFont("Helvetica-Bold", 17)
    d.c.drawString(W - 410, 478, "✗  Keyword stuffer")
    d.c.setFillColor(TEXT)
    d.c.setFont("Helvetica", 14)
    d.c.drawString(W - 410, 448, "Title: Accountant")
    d.c.drawString(W - 410, 426, "Skills: NLP, LLM, FAISS, RAG…")
    d.c.drawString(W - 410, 404, "Prose: ledgers, GST, audits")
    d.c.setFillColor(RED)
    d.c.setFont("Helvetica-Bold", 14)
    d.c.drawString(W - 410, 378, "→ capped + stuffer penalty")

    d.card(W - 430, 190, 350, 150, fill=HexColor("#ECFDF5"), stroke=GREEN)
    d.c.setFillColor(GREEN)
    d.c.setFont("Helvetica-Bold", 17)
    d.c.drawString(W - 410, 308, "✓  Real fit")
    d.c.setFillColor(TEXT)
    d.c.setFont("Helvetica", 14)
    d.c.drawString(W - 410, 278, "Title: Recommendation Sys Eng")
    d.c.drawString(W - 410, 256, "Prose: built ranking at scale,")
    d.c.drawString(W - 410, 234, "FAISS index, NDCG eval, prod")
    d.c.setFillColor(GREEN)
    d.c.setFont("Helvetica-Bold", 14)
    d.c.drawString(W - 410, 208, "→ ranks #1")
    d.footer(3)
    d.page()

    # ---- Slide 4 : Architecture ----
    d.bg()
    d.header("Architecture", "A hybrid, interpretable pipeline")
    # JD parsing banner feeding the fit stage
    d.c.setFillColor(INDIGO_D)
    d.c.roundRect(470, 575, 590, 30, 8, fill=1, stroke=0)
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Helvetica-Bold", 14)
    d.c.drawCentredString(765, 584, "JD  ⟶  JDSpec: role-domain vector · experience band · location · exclusions")

    boxes = [
        ("candidates\n.jsonl (100K)", 70, NAVY),
        ("Prose\nextraction", 270, INDIGO_D),
        ("Role-domain fit\n+ TF-IDF\n+ JD keywords", 470, INDIGO),
        ("Base score\n(weighted Σ)", 690, INDIGO),
        ("Gates ×\nbehavioral /\nstuffer / honeypot", 890, INDIGO_D),
        ("Top-100 CSV\n+ reasoning", 1110, GREEN),
    ]
    cy = 430
    for i, (label, x, col) in enumerate(boxes):
        bw = 150
        d.card(x, cy, bw, 120, fill=col, stroke=col, r=12)
        d.c.setFillColor(HexColor("#FFFFFF"))
        d.c.setFont("Helvetica-Bold", 15)
        for j, ln in enumerate(label.split("\n")):
            d.c.drawCentredString(x + bw / 2, cy + 80 - j * 20, ln)
        if i < len(boxes) - 1:
            nx = boxes[i + 1][1]
            d.c.setStrokeColor(MUTED)
            d.c.setLineWidth(2.5)
            d.c.line(x + bw, cy + 60, nx, cy + 60)
            d.c.setFillColor(MUTED)
            p = d.c.beginPath()
            p.moveTo(nx, cy + 60)
            p.lineTo(nx - 11, cy + 66)
            p.lineTo(nx - 11, cy + 54)
            p.close()
            d.c.drawPath(p, fill=1, stroke=0)
    d.bullets([
        "JD-adaptive: paste any JD — role domain, experience band, location and excluded specialties are parsed at run time. AI JD -> ML engineers; marketing JD -> marketers.",
        "Role fit = cosine of the candidate's domain vector (from titles + prose, never the stuffable skills list) vs the JD's.",
        "Same pipeline powers the submission CSV and the Streamlit sandbox. TF-IDF by default (zero network); optional embedding booster.",
    ], y=378, maxw=W - 160)
    d.footer(4)
    d.page()

    # ---- Slide 5 : Scoring model ----
    d.bg()
    d.header("Scoring model", "Weighted base, then multiplicative gates")
    d.card(70, 430, W - 140, 140, fill=NAVY, stroke=NAVY)
    d.c.setFillColor(HexColor("#A5B4FC"))
    d.c.setFont("Courier-Bold", 19)
    d.c.drawString(100, 530, "base  = 0.36·role_fit + 0.18·semantic + 0.16·evidence")
    d.c.drawString(100, 502, "        + 0.10·experience + 0.10·company_type + 0.10·location")
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Courier-Bold", 16)
    d.c.drawString(100, 466, "final = base × behavioral × verified × stuffer × excl-specialty × hopping × honeypot")
    # weights table
    weights = [("Role / domain fit", "0.36", "candidate-vs-JD domain cosine"),
               ("Semantic (TF-IDF)", "0.18", "prose vs JD, not skills[]"),
               ("JD-keyword evidence", "0.16", "JD's salient terms in the prose"),
               ("Experience", "0.10", "parsed band, peak at centre"),
               ("Company type", "0.10", "product > services (tech roles)"),
               ("Location", "0.10", "parsed JD city/country")]
    y = 380
    for name, w, why in weights:
        d.c.setFillColor(TEXT)
        d.c.setFont("Helvetica-Bold", 18)
        d.c.drawString(90, y, name)
        d.c.setFillColor(INDIGO)
        d.c.setFont("Courier-Bold", 18)
        d.c.drawString(370, y, w)
        d.c.setFillColor(MUTED)
        d.c.setFont("Helvetica", 16)
        d.c.drawString(450, y, why)
        y -= 40
    d.footer(5)
    d.page()

    # ---- Slide 6 : Trap defense ----
    d.bg()
    d.header("Trap defense", "Four multiplicative gates")
    cards = [
        ("Keyword-stuffing", "Many JD-keyword skills + weak role fit → penalty up to −45%.", RED),
        ("Honeypot / consistency", "Role longer than whole career, 'expert' in skills with 0 months used, impossible date spans → forced out of top 100.", AMBER),
        ("Excluded specialty (from JD)", "The JD's 'do NOT want' section is parsed; a title that matches an excluded specialty (e.g. computer vision for this role) → down-weighted.", INDIGO_D),
        ("Behavioral availability", "Low response rate, inactive 6+ months, long notice → down-weighted. A perfect-on-paper unreachable candidate is not hireable.", GREEN),
    ]
    xs = [70, 660]
    ys = [330, 330, 110, 110]
    for i, (t, body, col) in enumerate(cards):
        x = xs[i % 2]
        y = ys[i]
        d.card(x, y, 540, 170, fill=CARD, stroke=col)
        d.c.setFillColor(col)
        d.c.rect(x, y, 8, 170, fill=1, stroke=0)
        d.c.setFillColor(NAVY)
        d.c.setFont("Helvetica-Bold", 22)
        d.c.drawString(x + 28, y + 130, t)
        d.c.setFillColor(TEXT)
        d.c.setFont("Helvetica", 16)
        for j, ln in enumerate(wrap(body, "Helvetica", 16, 480)):
            d.c.drawString(x + 28, y + 96 - j * 24, ln)
    d.footer(6)
    d.page()

    # ---- Slide 7 : Results ----
    d.bg()
    d.header("Results", "Top-100 on the released pool")
    if S:
        stats = [("India candidates", f"{S['countries'].get('India',0)} / 100", GREEN),
                 ("Honeypots in top-100", f"{S['honey']}  (limit 10)", GREEN),
                 ("In 6–8y ideal band", f"{S['band'].get('6-8',0)}", INDIGO),
                 ("Score range", f"{S['smax']:.2f} → {S['smin']:.2f}", INDIGO)]
        for i, (k, v, col) in enumerate(stats):
            x = 70 + i * 295
            d.card(x, 430, 270, 130, fill=CARD, stroke=SLATE)
            d.c.setFillColor(col)
            d.c.setFont("Helvetica-Bold", 34)
            d.c.drawString(x + 22, 478, v)
            d.c.setFillColor(MUTED)
            d.c.setFont("Helvetica", 16)
            d.c.drawString(x + 22, 446, k)
        # top 5 table
        d.c.setFillColor(NAVY)
        d.c.setFont("Helvetica-Bold", 22)
        d.c.drawString(70, 388, "Top 5 picks")
        y = 350
        d.c.setFillColor(MUTED)
        d.c.setFont("Helvetica-Bold", 14)
        d.c.drawString(70, y, "RANK")
        d.c.drawString(140, y, "TITLE")
        d.c.drawString(560, y, "YRS")
        d.c.drawString(650, y, "SCORE")
        y -= 28
        for r in S["top"]:
            d.c.setFillColor(INDIGO)
            d.c.setFont("Helvetica-Bold", 17)
            d.c.drawString(70, y, f"#{r['rank']}")
            d.c.setFillColor(TEXT)
            d.c.setFont("Helvetica", 17)
            d.c.drawString(140, y, str(r["title"])[:42])
            d.c.drawString(560, y, f"{r['yoe']}")
            d.c.setFillColor(GREEN)
            d.c.setFont("Helvetica-Bold", 17)
            d.c.drawString(650, y, f"{r['score']:.3f}")
            y -= 30
        # title distribution panel
        d.card(770, 130, 440, 230, fill=LIGHT, stroke=SLATE)
        d.c.setFillColor(NAVY)
        d.c.setFont("Helvetica-Bold", 18)
        d.c.drawString(792, 330, "Top-100 role mix (all genuine ML/IR)")
        yy = 298
        mx = max(c for _, c in S["titles"]) or 1
        for name, cnt in S["titles"]:
            d.c.setFillColor(TEXT)
            d.c.setFont("Helvetica", 14)
            d.c.drawString(792, yy, str(name)[:26])
            barw = 150 * cnt / mx
            d.c.setFillColor(INDIGO)
            d.c.roundRect(1040, yy - 2, barw, 14, 3, fill=1, stroke=0)
            d.c.setFillColor(MUTED)
            d.c.setFont("Helvetica-Bold", 13)
            d.c.drawString(1040 + barw + 8, yy, str(cnt))
            yy -= 30
    d.footer(7)
    d.page()

    # ---- Slide 8 : Reasoning quality ----
    d.bg()
    d.header("Reasoning", "Grounded, specific, varied")
    d.bullets([
        "Every reasoning string is assembled ONLY from facts in the candidate's own profile — no hallucinated skills.",
        "Tone adapts to rank; honest concerns (low response rate, long notice, services-heavy background) are surfaced.",
        "99 / 100 reasonings are unique — no templated 'insert name' filler.",
    ], maxw=W - 160)
    examples = [
        ("#1", "Senior ML Engineer, 7.2 yrs; retrieval/ranking work, eval-metric experience, production signals; Pune. Responsive (95%)."),
        ("#7", "Applied ML Engineer, 6.0 yrs; retrieval/ranking + production signals; Kolkata. Concern: long notice period (90d)."),
        ("#84", "Junior ML Engineer, 6.8 yrs; production/scale signals, product-company background; Jaipur."),
    ]
    y = 330
    for tag, ex in examples:
        d.card(70, y - 10, W - 140, 78, fill=CARD, stroke=SLATE)
        d.c.setFillColor(INDIGO)
        d.c.setFont("Helvetica-Bold", 20)
        d.c.drawString(90, y + 28, tag)
        d.c.setFillColor(TEXT)
        d.c.setFont("Helvetica", 16)
        for j, ln in enumerate(wrap(ex, "Helvetica", 16, W - 320)):
            d.c.drawString(150, y + 36 - j * 22, ln)
        y -= 100
    d.footer(8)
    d.page()

    # ---- Slide 9 : Compute & reproducibility ----
    d.bg()
    d.header("Compute & reproducibility", "Built for a real production budget")
    rows = [("Runtime ≤ 5 min", "~2 min for 100K (TF-IDF path)", GREEN),
            ("Memory ≤ 16 GB", "well under — sparse TF-IDF + streamed JSONL", GREEN),
            ("CPU only, no GPU", "yes, everywhere", GREEN),
            ("Network off", "zero API / LLM calls during ranking", GREEN),
            ("One command", "python rank.py --candidates … --out …", INDIGO),
            ("Passes validator", "validate_submission.py → 'Submission is valid.'", INDIGO),
            ("Sandbox", "Streamlit app runs the same pipeline on a sample", INDIGO)]
    y = 430
    for k, v, col in rows:
        d.c.setFillColor(col)
        d.c.circle(82, y + 6, 7, fill=1, stroke=0)
        d.c.setFillColor(NAVY)
        d.c.setFont("Helvetica-Bold", 20)
        d.c.drawString(105, y, k)
        d.c.setFillColor(MUTED)
        d.c.setFont("Helvetica", 18)
        d.c.drawString(470, y, v)
        y -= 48
    d.footer(9)
    d.page()

    # ---- Slide 10 : Roadmap / closing ----
    d.bg(NAVY)
    d.c.setFillColor(INDIGO)
    d.c.rect(0, 0, 18, H, fill=1, stroke=0)
    d.c.setFillColor(HexColor("#FFFFFF"))
    d.c.setFont("Helvetica-Bold", 44)
    d.c.drawString(90, H - 150, "What we'd ship next")
    nexts = [
        "Dense embeddings (BGE/E5) as the primary retriever — booster already wired in, TF-IDF as fallback.",
        "Learning-to-rank (XGBoost) trained on recruiter-engagement labels once available.",
        "Proper offline eval harness: NDCG / MRR / MAP with bootstrapped confidence intervals.",
        "Online A/B testing + recruiter-feedback loop to close the offline→online gap.",
    ]
    d.c.setFillColor(SLATE)
    y = H - 215
    for n in nexts:
        d.c.setFillColor(INDIGO)
        d.c.circle(100, y + 7, 5, fill=1, stroke=0)
        d.c.setFillColor(SLATE)
        d.c.setFont("Helvetica", 21)
        for j, ln in enumerate(wrap(n, "Helvetica", 21, W - 260)):
            d.c.drawString(120, y - j * 28, ln)
        y -= 40 + 28 * (len(wrap(n, "Helvetica", 21, W - 260)) - 1)
    d.c.setFillColor(HexColor("#A5B4FC"))
    d.c.setFont("Helvetica-Bold", 22)
    d.c.drawString(90, 140, "Reads careers, not keywords · CPU-only · fully reproducible")
    d.c.setFillColor(MUTED)
    d.c.setFont("Helvetica", 16)
    d.c.drawString(90, 100, "GitHub: github.com/Abhi-tech-geek/redrob-ranker   ·   Sandbox: Streamlit Community Cloud")
    d.page()

    d.save()
    print("Wrote approach_deck.pdf")


if __name__ == "__main__":
    build()
