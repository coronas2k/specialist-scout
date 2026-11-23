# Decision: do not add late interaction (ColBERT) to the search

Date: 2026-11-23. Status: accepted. Benchmark: Run 10 in `RESULTS.md`.

## Decision

Keep the current hybrid (keyword plus MiniLM embeddings). Do not add `answerai-colbert-small-v1`.

## Why

1. **No gain on hybrid.** The current hybrid finds the right specialist first on 76 of 106 queries
   and in the top three on 91. Adding late interaction changes that by one query in either direction.
2. **The one gain is not useful.** Late interaction alone finds the right specialist first more often
   than MiniLM embeddings alone (69 against 64), but the plugin does not use embeddings alone.
3. **Cost.** A new 34 MB model, a second index, a new scoring step over token vectors, a new
   third-party notice, and a retest of the whole setup.
4. **Our checks.** The encoding reproduces the model card's ranking. Its scores are about one point
   lower because we use the int8 file, not the full-precision model. That does not affect the result.

## What would change this

- A reranker that reads the query and each candidate together (not yet tested; the smallest MIT
  option is 1.1 GB).
- A labelled set where token-level matching clearly beats a single vector. Multi-part requests
  were the hoped-for case, and these sets do not contain enough of them to show a difference.
