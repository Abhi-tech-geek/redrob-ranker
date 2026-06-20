"""
Central configuration — only the JD-agnostic knobs live here.

Role taxonomy moved to domains.py (general, ~18 occupational domains) and JD
parsing to jdspec.py, so this ranker adapts to any job description. What remains
here are universal pieces: how we type companies (product vs services), the
scoring weights, and the bounds of the multiplicative gates.
"""

# --------------------------------------------------------------------------- #
# Company / industry typing  (product vs services) — used for tech roles
# --------------------------------------------------------------------------- #
CONSULTING_COMPANIES = [
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "mindtree", "tech mahindra", "hcl", "lti", "larsen", "l&t infotech",
    "ltimindtree", "mphasis", "dxc", "hexaware", "ibm services", "deloitte",
    "kpmg", "pwc", "ey ", "ernst", "syntel", "birlasoft", "coforge", "zensar",
    "persistent systems", "nttdata", "ntt data", "atos",
]
CONSULTING_INDUSTRIES = ["it services", "consulting", "outsourcing", "bpo"]

PRODUCT_INDUSTRIES = [
    "software", "fintech", "food delivery", "e-commerce", "ecommerce",
    "saas", "internet", "gaming", "healthtech", "edtech", "social media",
    "ride sharing", "logistics", "marketplace", "ad tech", "adtech",
    "streaming", "cloud", "cybersecurity", "data", "ai", "technology",
]

NONTECH_INDUSTRIES = [
    "manufacturing", "paper products", "conglomerate", "construction",
    "automotive", "oil", "mining", "agriculture", "textiles", "real estate",
    "hospitality", "retail", "fmcg", "pharmaceutical", "chemicals",
    "transportation", "utilities",
]

# --------------------------------------------------------------------------- #
# Scoring weights  (base fit, before multiplicative gates) — sum to 1.0
# --------------------------------------------------------------------------- #
WEIGHTS = {
    "role_fit":      0.36,   # candidate-vs-JD domain cosine (the decisive signal)
    "semantic":      0.18,   # TF-IDF (+optional embedding) of prose vs JD
    "evidence":      0.16,   # JD's salient keywords found in the candidate's prose
    "experience":    0.10,   # parsed JD experience band
    "company_type":  0.10,   # product vs services (tech roles only)
    "location":      0.10,   # parsed JD location preference
}

# Behavioral availability multiplier bounds.
BEHAVIORAL_MIN = 0.55
BEHAVIORAL_MAX = 1.12

# Hard-penalty multipliers.
HONEYPOT_MULTIPLIER = 0.02     # forces detected honeypots out of the top 100
STUFFER_PENALTY_MAX = 0.45     # max multiplicative penalty for keyword stuffing
