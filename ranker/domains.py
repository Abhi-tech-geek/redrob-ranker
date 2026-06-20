"""
General role-domain taxonomy + profile vectors.

This is what makes the ranker work for *any* job description, not just the AI
Engineer one. Instead of a hard-coded "these titles are good" list, we describe
~18 occupational domains (AI/ML, software, data, marketing, finance, civil
engineering, …). Both the JD and each candidate are turned into a *domain
profile* — a vector over these domains — and role fit is the cosine between the
two. A Marketing JD lights up the marketing dimension; a marketing candidate
lights up the same dimension → high fit. An AI JD vs an accountant → orthogonal
→ low fit. Adjacent domains (ML ~ data engineering) share dimensions and get
partial credit automatically.

Crucially, a candidate's domain profile is built from their *titles and prose*
only — never the stuffable skills[] array — so a keyword-stuffed profile cannot
fake its way into the target domain.
"""
import math
import re

# domain -> (title phrases [weighted high], context terms [weighted low])
DOMAINS = {
    "ai_ml": (
        ["ai engineer", "a.i engineer", "machine learning", "ml engineer",
         "data scientist", "applied scientist", "applied ml", "nlp engineer",
         "deep learning", "research engineer", "recommendation", "recsys",
         "search engineer", "relevance engineer", "ranking engineer",
         "ml scientist", "computer vision", "speech", "ml platform", "mlops"],
        ["machine learning", "deep learning", "neural network", "embedding",
         "embeddings", "model training", "pytorch", "tensorflow", "nlp",
         "natural language", "llm", "large language model", "transformer",
         "recommendation", "ranking", "retrieval", "classification",
         "prediction", "feature engineering", "fine-tuning", "vector search",
         "semantic search", "mlops", "scikit", "xgboost"]),
    "data_eng": (
        ["data engineer", "analytics engineer", "data platform engineer",
         "etl developer", "bi engineer", "big data engineer"],
        ["data pipeline", "etl", "elt", "spark", "airflow", "hadoop",
         "warehouse", "snowflake", "dbt", "bigquery", "kafka", "streaming",
         "ingestion", "data lake", "databricks"]),
    "software": (
        ["software engineer", "backend engineer", "back-end engineer",
         "full stack", "full-stack", "developer", "sde", "software development",
         "programmer", "application engineer", "staff engineer",
         "principal engineer", "java developer", ".net developer"],
        ["api", "rest api", "microservice", "backend", "distributed system",
         "scalable", "database", "service", "deployment", "architecture",
         "spring boot", "node.js", "golang"]),
    "frontend": (
        ["frontend", "front-end", "ui engineer", "ui developer",
         "react developer", "web developer"],
        ["react", "angular", "vue", "css", "html", "javascript", "typescript",
         "responsive", "redux", "tailwind", "next.js"]),
    "mobile": (
        ["mobile developer", "ios developer", "android developer",
         "flutter developer", "react native"],
        ["ios", "android", "swift", "kotlin", "mobile app", "flutter",
         "react native"]),
    "devops": (
        ["devops", "sre", "site reliability", "cloud engineer",
         "platform engineer", "infrastructure engineer"],
        ["kubernetes", "docker", "terraform", "ci/cd", "aws", "azure", "gcp",
         "infrastructure", "monitoring", "ansible", "jenkins", "helm"]),
    "qa": (
        ["qa engineer", "test engineer", "quality assurance", "sdet",
         "automation test"],
        ["testing", "test automation", "selenium", "test cases",
         "quality assurance", "regression testing", "cypress"]),
    "civil": (
        ["civil engineer", "structural engineer", "site engineer"],
        ["construction", "structural", "autocad", "concrete", "survey",
         "building", "site supervision", "staad"]),
    "mechanical": (
        ["mechanical engineer", "design engineer", "manufacturing engineer"],
        ["cad", "solidworks", "manufacturing", "thermal", "hvac", "machining",
         "mechanical design", "tolerance", "ansys"]),
    "electrical": (
        ["electrical engineer", "electronics engineer", "hardware engineer"],
        ["circuit", "pcb", "electronics", "power systems", "embedded",
         "vlsi", "microcontroller"]),
    "marketing": (
        ["marketing manager", "marketing", "seo specialist", "content writer",
         "brand manager", "growth manager", "digital marketing", "social media"],
        ["campaign", "seo", "sem", "brand", "content marketing", "social media",
         "advertising", "engagement", "growth", "email marketing", "copywriting"]),
    "sales": (
        ["sales executive", "sales manager", "business development",
         "account manager", "account executive", "inside sales"],
        ["sales", "revenue", "quota", "sales pipeline", "crm", "leads",
         "prospect", "closing deals", "b2b", "negotiation", "salesforce"]),
    "hr": (
        ["hr manager", "human resources", "recruiter", "talent acquisition",
         "people operations"],
        ["recruitment", "hiring", "payroll", "onboarding", "employee relations",
         "talent", "benefits", "performance review"]),
    "finance": (
        ["accountant", "finance manager", "financial analyst",
         "chartered accountant", "auditor", "bookkeeper"],
        ["accounting", "ledger", "gst", "audit", "taxation", "financial",
         "invoice", "reconciliation", "balance sheet", "budgeting", "tally"]),
    "operations": (
        ["operations manager", "operations", "supply chain", "logistics manager",
         "process engineer"],
        ["operations", "logistics", "supply chain", "process improvement",
         "six sigma", "procurement", "inventory", "vendor management"]),
    "design": (
        ["graphic designer", "ui/ux", "ux designer", "product designer",
         "visual designer"],
        ["photoshop", "figma", "illustrator", "wireframe", "prototype",
         "typography", "branding", "adobe", "user research"]),
    "pm": (
        ["project manager", "product manager", "program manager",
         "scrum master", "delivery manager"],
        ["roadmap", "stakeholder", "agile", "scrum", "delivery", "sprint",
         "requirements", "project plan", "kanban", "jira"]),
    "support": (
        ["customer support", "customer success", "technical support",
         "support engineer"],
        ["support ticket", "customer", "helpdesk", "sla", "troubleshoot",
         "resolution", "zendesk"]),
    "business": (
        ["business analyst", "data analyst", "business intelligence"],
        ["requirements", "stakeholder", "analysis", "dashboard", "reporting",
         "excel", "insights", "kpi", "tableau", "power bi"]),
}

DOMAIN_NAMES = list(DOMAINS.keys())

# human-readable labels for reasoning / UI
DOMAIN_LABELS = {
    "ai_ml": "AI/ML", "data_eng": "data engineering", "software": "software engineering",
    "frontend": "frontend", "mobile": "mobile", "devops": "DevOps/cloud", "qa": "QA",
    "civil": "civil engineering", "mechanical": "mechanical engineering",
    "electrical": "electrical engineering", "marketing": "marketing", "sales": "sales",
    "hr": "HR/recruiting", "finance": "finance/accounting", "operations": "operations",
    "design": "design", "pm": "project/product management", "support": "customer support",
    "business": "business analysis",
}

# --- precomputed indexes for fast matching (built once at import) ----------- #
_TITLE_INDEX = [(t, dom) for dom, (titles, _) in DOMAINS.items() for t in titles]
_TERM_DOMAINS = {}
for _dom, (_t, _terms) in DOMAINS.items():
    for _term in _terms:
        _TERM_DOMAINS.setdefault(_term, set()).add(_dom)
_ALL_TERMS = sorted(_TERM_DOMAINS, key=len, reverse=True)
_TERM_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(t) for t in _ALL_TERMS) + r")(?![a-z0-9])")


def domain_profile(current_title, past_titles, prose_text):
    """
    Return a normalised dict domain -> score in [0,1].

    The *current* title is the dominant identity signal (it is who the person is
    now and the hardest thing to fake), past roles add weaker recency-agnostic
    credit, and prose only corroborates (capped) so a keyword-stuffed
    description cannot flip a candidate's domain. This is what stops, say, a
    Mechanical Engineer who once held a marketing role from reading as a
    marketer.
    """
    cur = (current_title or "").lower()
    past = [(t or "").lower() for t in (past_titles or [])]
    prose = (prose_text or "").lower()

    raw = {d: 0.0 for d in DOMAINS}
    # current role identity (4.0, once per domain) ...
    cur_doms = {dom for phrase, dom in _TITLE_INDEX if phrase in cur}
    for dom in cur_doms:
        raw[dom] += 4.0
    # ... past roles (1.0 per past role that maps to a domain)
    for pt in past:
        for dom in {dom for phrase, dom in _TITLE_INDEX if phrase in pt}:
            raw[dom] += 1.0
    # prose corroboration: one regex pass, count distinct terms per domain
    term_hits = {d: 0 for d in DOMAINS}
    for term in set(_TERM_RE.findall(prose)):
        for dom in _TERM_DOMAINS[term]:
            term_hits[dom] += 1
    for dom in DOMAINS:
        raw[dom] += min(2.5, 0.4 * term_hits[dom])

    norm = math.sqrt(sum(v * v for v in raw.values()))
    if norm <= 1e-9:
        return {d: 0.0 for d in raw}
    return {d: v / norm for d, v in raw.items()}


def cosine(a, b):
    return sum(a[d] * b[d] for d in a)


def top_domains(profile, k=2, thresh=0.15):
    items = sorted(profile.items(), key=lambda kv: kv[1], reverse=True)
    return [d for d, v in items[:k] if v >= thresh]
