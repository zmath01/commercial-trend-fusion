#!/usr/bin/env python3
"""build_lexicon.py — academic phrase mining (word2phrase-style merging).

Algorithm (documented in docs/methodology.md §2):
  1. Tokenize the corpus (scripts/corpus.py::tokenize).
  2. Iteratively merge adjacent tokens/phrases using the association score
     of Mikolov et al. 2013 (word2phrase):
         score(a,b) = (count(ab) - delta) / (count(a) * count(b)) * N
     where N is the number of adjacent pairs, delta discounts rare pairs.
     Merging repeats until max_n tokens per phrase or no pair passes the
     threshold.
  3. Post-filter: keep phrases with final frequency >= min_freq.
  4. Add strong unigrams (freq >= 10 * min_freq) so single-token commercial
     terms (llm, gpu, qubit, bitcoin) enter the network too.

Output: data/lexicon/lexicon.csv  (term, n_tokens, freq, score)

Data structures: dict[(tuple,)] -> int counts; merged phrases are tuples
of tokens, so lookup/merge are O(1) hash operations. This is the same
family of algorithm loomsci-type projects claim, but with a citable,
deterministic formulation and no hidden magic thresholds.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corpus import load_corpus_df, tokenize  # noqa: E402

with open(ROOT / "config.yaml", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)


def merge_pass(sentences, min_freq, delta, min_score):
    """One merging iteration. Returns (new_sentences, merged_phrases).

    merged_phrases: dict phrase_tuple -> association score (for reporting).
    """
    pair_cnt = Counter()
    unigram_cnt = Counter()
    for sent in sentences:
        for i in range(len(sent) - 1):
            a, b = sent[i], sent[i + 1]
            pair_cnt[(a, b)] += 1
            unigram_cnt[a] += 1
        if sent:
            unigram_cnt[sent[-1]] += 1
    n_pairs = sum(pair_cnt.values())

    # phrases eligible to merge: frequency >= min_freq
    to_merge = {}
    for (a, b), c in pair_cnt.items():
        if c < min_freq:
            continue
        ca = unigram_cnt[a]
        cb = unigram_cnt[b]
        if ca == 0 or cb == 0:
            continue
        s = (c - delta) / (ca * cb) * n_pairs
        if s > min_score:
            to_merge[(a, b)] = s

    if not to_merge:
        return sentences, {}

    merged_sentences = []
    for sent in sentences:
        out = []
        i = 0
        while i < len(sent):
            if i + 1 < len(sent) and (sent[i], sent[i + 1]) in to_merge:
                out.append((sent[i], sent[i + 1]))
                i += 2
            else:
                out.append(sent[i])
                i += 1
        merged_sentences.append(out)
    return merged_sentences, to_merge


def flatten(p):
    """Recursively flatten a (possibly nested) phrase tuple to a string."""
    if isinstance(p, tuple):
        return " ".join(flatten(x) for x in p)
    return str(p)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="run on the committed sample corpus")
    args = ap.parse_args()

    lx = CFG["lexicon"]
    min_freq = lx["min_freq"]
    delta = float(min_freq)
    min_score = 1e-4
    max_n = lx["max_n"]

    print("[lexicon] loading corpus ...", flush=True)
    df = load_corpus_df(use_sample=args.sample)
    text = (df["title"].fillna("") + ". " + df["abstract"].fillna(""))
    sentences = [tokenize(t) for t in text]
    print(f"[lexicon] papers={len(df)} sentences={len(sentences)}", flush=True)

    # iterative merging
    all_merged = {}
    for it in range(1, max_n):
        sentences, merged = merge_pass(sentences, min_freq, delta, min_score)
        for k, v in merged.items():
            all_merged[k] = v
        if not merged:
            break
        n_phr = sum(1 for s in sentences for p in s if isinstance(p, tuple))
        print(f"[lexicon] pass {it}: +{len(merged)} phrases (total phrases in corpus {n_phr})",
              flush=True)

    # final phrase frequencies
    phrase_cnt = Counter()
    unigram_cnt = Counter()
    for sent in sentences:
        for p in sent:
            if isinstance(p, tuple):
                phrase_cnt[p] += 1
            else:
                unigram_cnt[p] += 1

    # flat-string frequency map (for merge-artifact detection)
    flat_count = Counter()
    for p, c in phrase_cnt.items():
        flat_count[flatten(p)] += c

    rows = []
    for p, c in phrase_cnt.items():
        if c < min_freq:
            continue
        flat = flatten(p)
        n_tok = len(flat.split())
        # merge-artifact filter: P = Q + t where Q is itself a more common
        # lexicon phrase (e.g. "large language" + "llms") -> drop P
        if n_tok >= 3:
            prefix = flatten(p[:-1])
            if prefix in flat_count and flat_count[prefix] > c:
                continue
        rows.append((flat, n_tok, c, all_merged.get(p, 0.0)))
    # strong unigrams
    for t, c in unigram_cnt.items():
        if c >= 10 * min_freq:
            rows.append((t, 1, c, 0.0))

    rows.sort(key=lambda r: (-r[2]))
    rows = rows[: lx["max_terms"]]

    out = ROOT / CFG["paths"]["lexicon"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["term", "n_tokens", "freq", "score"])
        w.writerows(rows)
    print(f"[lexicon] saved {len(rows)} terms -> {out}")


if __name__ == "__main__":
    main()
