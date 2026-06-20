#!/usr/bin/env python3
"""
OPTIONAL offline embedding precomputation (the "dense" half of hybrid retrieval).

The submission spec allows pre-computation that exceeds the 5-minute ranking
budget, as long as the *ranking step* (rank.py) stays within it. This script
encodes every candidate's prose with a small CPU sentence-transformer and saves
a plain .npz artifact that rank.py auto-detects and blends with its TF-IDF
score. If you never run this, the ranker still works — TF-IDF is the default.

    pip install -r requirements-embeddings.txt
    python precompute_embeddings.py --candidates ./candidates.jsonl

Produces: artifacts/candidate_embeddings.npz  (ids, vectors, jd)

Model: sentence-transformers/all-MiniLM-L6-v2 (80 MB, CPU-friendly). Swap for
BGE-small / E5-small by changing --model. Encoding runs on CPU only; no network
is needed at *ranking* time because the vectors are baked into the artifact.
"""
import argparse
import json
import os

import numpy as np

from ranker.text import candidate_text


def stream(path, limit=None):
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                break
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--jd", default=os.path.join(os.path.dirname(__file__), "job_description.txt"))
    ap.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "artifacts", "candidate_embeddings.npz"))
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--batch", type=int, default=256)
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer  # heavy import, kept local
    model = SentenceTransformer(args.model, device="cpu")

    ids, texts = [], []
    for c in stream(args.candidates, args.limit):
        cid = c.get("candidate_id")
        if cid:
            ids.append(cid)
            texts.append(candidate_text(c))

    print(f"Encoding {len(texts)} candidates with {args.model} (CPU)...")
    vectors = model.encode(
        texts, batch_size=args.batch, show_progress_bar=True,
        convert_to_numpy=True, normalize_embeddings=True,
    ).astype(np.float32)

    with open(args.jd, "r", encoding="utf-8") as f:
        jd_text = f.read()
    jd_vec = model.encode([jd_text], normalize_embeddings=True,
                          convert_to_numpy=True)[0].astype(np.float32)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # ids saved as a unicode string array so the artifact loads as plain arrays.
    np.savez(args.out,
             ids=np.array(ids, dtype="U16"),
             vectors=vectors,
             jd=jd_vec)
    print(f"Saved {args.out}  (vectors: {vectors.shape})")


if __name__ == "__main__":
    main()
