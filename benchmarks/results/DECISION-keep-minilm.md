# Decision: keep the current embedding model and text

Date: 2026-11-23. Status: accepted. Benchmark: Run 9 in `RESULTS.md`.

## Decision

Keep `all-MiniLM-L6-v2` (the upstream ONNX file, Apache-2.0) and the current embedding text
(name, description and vibe). Do not switch to `bge-small-en-v1.5`, and do not embed body text.

## Context

Hybrid search finds the right specialist in the top three on 20 of 30 workflow subtasks. The
subagent picker finds it on 22 of 23 valid subtasks. We wanted to close that gap without a model
call per lookup, so we tested the two cheapest levers: what text is embedded, and which model
embeds it.

## What was tested

| Option | Result on 106 queries | Verdict |
|---|---|---|
| Embed name and description only | hybrid 76/106 at hit@1, 90/106 at hit@3 | no gain |
| Add 600 characters of body text | hybrid 75/106, 89/106 | worse |
| Add 1,200 characters of body text | hybrid 75/106, 90/106 | no gain |
| bge-small-en-v1.5, CLS pooling | embeddings alone 67/106, 84/106; hybrid 74/106, 91/106 | no gain on hybrid; first place slightly worse |
| bge-small with query prefix | embeddings alone 69/106, 82/106; hybrid 75/106, 91/106 | no gain |
| Current MiniLM (baseline) | embeddings alone 64/106, 82/106; hybrid 76/106, 91/106 | kept |

## Why not switch

1. **No hybrid gain.** bge-small is about 2 points better on embeddings alone, but hybrid search
   is the same at the top three (91 of 106) and one query worse at first place (74 against 76).
2. **Cost.** The model file is 133 MB against 90 MB. Switching means a new download and checksum
   pin, a new pooling step, a rebuilt index for every user, a new third-party notice, and a
   retest of the whole setup.
3. **Noise.** With 106 queries, one query is about one point. The differences between these
   options are one or two queries, so they do not justify the change.
4. **Longer text did not help.** Body text adds index size and embedding time without better
   matches.

## What would change this decision

- A **cross-encoder reranker**, which reads the query and each candidate together. The smallest
  MIT-licensed option we found, `BAAI/bge-reranker-base`, has a 1.1 GB ONNX file. It is untested and
  is the only lever left that works like the picker.
- A **new labelled set** where embeddings are clearly better than keywords. The current sets do not
  separate the options.

## Reproduce

```
benchmarks/experiments/text_variants.py <work dir>
benchmarks/experiments/bge_compare.py <work dir>   # needs a bge/ folder with model.onnx and tokenizer.json
```

## Update (Run 13): six more embedding models

Also tested: arctic-embed-xs and arctic-embed-s (Apache-2.0), all-MiniLM-L12-v2 (Apache-2.0),
gte-small (MIT), e5-small-v2 (MIT) and nomic-embed-text-v1.5 (Apache-2.0, int8). None improves the
hybrid, and arctic-embed-xs ties it at the same size. The decision stands: keep all-MiniLM-L6-v2.
See Run 13 in `RESULTS.md`.
