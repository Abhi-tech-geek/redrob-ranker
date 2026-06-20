#!/usr/bin/env python3
"""
Redrob Hackathon — Senior AI Engineer candidate ranker.

Single-command entry point that reads the candidate pool and writes the top-100
ranking CSV required by the submission spec.

    python rank.py --candidates ./candidates.jsonl --out ./submission.csv

Design (see README.md for the full write-up):
  * Reads each candidate's *prose* (summary + career descriptions), not just the
    keyword-stuffable skills list.
  * Hybrid score = interpretable structured components (role fit, experience,
    product-vs-services, location) + TF-IDF semantic match + explicit
    retrieval/ranking/eval/production evidence.
  * Multiplicative gates for availability (behavioral signals), keyword
    stuffing, job-hopping, off-domain (CV/speech) and internal-impossibility
    (honeypots).
  * CPU-only, no network, no GPU. Runs the full 100K pool in well under the
    5-minute / 16 GB budget.

Optional: if `artifacts/candidate_embeddings.npz` exists (produced offline by
precompute_embeddings.py), a sentence-transformers similarity is blended in.
The default path needs none of that.
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np

from ranker.pipeline import rank_candidates


def load_jd(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def stream_candidates(path, limit=None):
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def load_embedding_sims(art_path):
    """Optional .npz artifact -> dict candidate_id -> cosine similarity to JD."""
    if not art_path or not os.path.exists(art_path):
        return None
    data = np.load(art_path)               # plain arrays, no allow_pickle needed
    ids = [str(x) for x in data["ids"]]
    vecs = data["vectors"].astype(np.float32)
    jd = data["jd"].astype(np.float32)
    vecs /= (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)
    jd /= (np.linalg.norm(jd) + 1e-9)
    sims = vecs @ jd
    return {cid: float(s) for cid, s in zip(ids, sims)}


def main():
    ap = argparse.ArgumentParser(description="Rank candidates for the Redrob JD.")
    ap.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    ap.add_argument("--out", default="submission.csv", help="Output CSV path")
    ap.add_argument("--jd", default=os.path.join(os.path.dirname(__file__), "job_description.txt"))
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--limit", type=int, default=None, help="Only read first N (debug)")
    ap.add_argument("--embeddings", default=os.path.join(
        os.path.dirname(__file__), "artifacts", "candidate_embeddings.npz"))
    ap.add_argument("--audit", default=None, help="Optional top-N audit JSON path")
    args = ap.parse_args()

    t0 = time.time()
    jd_text = load_jd(args.jd)
    print(f"[1/4] Loaded JD ({len(jd_text)} chars)", file=sys.stderr)

    cands = [c for c in stream_candidates(args.candidates, args.limit)
             if c.get("candidate_id")]
    print(f"[2/4] Read {len(cands)} candidates ({time.time()-t0:.1f}s)", file=sys.stderr)
    if len(cands) < args.top:
        print(f"ERROR: only {len(cands)} candidates, need >= {args.top}", file=sys.stderr)
        sys.exit(1)

    emb_sims = load_embedding_sims(args.embeddings)
    if emb_sims is not None:
        print(f"      embedding artifact found ({len(emb_sims)} vecs) -> blending",
              file=sys.stderr)

    rows, audit, jdspec = rank_candidates(cands, jd_text, top=args.top, emb_sims=emb_sims)
    print(f"      JD parsed -> domains={jdspec.target_domains} "
          f"exp={jdspec.exp_min:.0f}-{jdspec.exp_max:.0f}y "
          f"locations={jdspec.locations or jdspec.countries or 'any'}", file=sys.stderr)
    print(f"[3/4] Scored + ranked ({time.time()-t0:.1f}s)", file=sys.stderr)

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in rows:
            w.writerow([r["candidate_id"], r["rank"], r["score"], r["reasoning"]])

    if args.audit:
        with open(args.audit, "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2, ensure_ascii=False)

    print(f"[4/4] Wrote {args.out} (top {args.top}) in {time.time()-t0:.1f}s total",
          file=sys.stderr)


if __name__ == "__main__":
    main()
