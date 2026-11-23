# Decision: do not add a cross-encoder reranker

Date: 2026-11-23. Status: accepted. Benchmark: Run 12 in `RESULTS.md`.

## Decision

Keep the current hybrid (keyword plus MiniLM embeddings), with no reranking step.

## Why

1. **No gain.** Reranking the top 15 with either reranker is no better than the hybrid on 106
   queries. Rerank-only is worse on the top three (ms-marco 87 against 91; jina 89 against 91).
   Combining the hybrid order with the reranker order moves the top three by one query.
2. **The cost is real.** Each reranker adds a second model (23 or 33 MB), about 100 ms per query on
   this Mac, and a new scoring step, with a new third-party notice and a retest of the setup.
3. **The two-in-one goal is not met.** No single model under 200 MB with a permissive licence does
   both vectors and cross-encoder reranking and beats the hybrid. The one that does both
   (answerai-colbert-small-v1) did not improve it either (`DECISION-no-late-interaction.md`).

## What would change this

- A reranker trained on job, role or tool descriptions rather than web passages. The two tested here
  were trained on web passages, which may explain why they do not transfer.
- A labelled set where reranking clearly beats the hybrid. The current sets do not show that.
