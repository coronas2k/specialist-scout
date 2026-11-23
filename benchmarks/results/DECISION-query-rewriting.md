# Decision: write four search phrases and merge them with the request

Date: 2026-11-23. Status: adopted, on the user's approval. Evidence: Run 20 and `PREREG-pipeline.md`.

## What changed

- The skill writes four short phrases (2 to 5 words each) in the words a specialist's job description would
  use. It passes each with `--also`, and `roster.py` merges the request and the phrases by each specialist's
  best rank, with ties going to the request. The top eight are shown, and the model picks from them.
- The merge is `rank_merged` in `scripts/roster.py`. It reproduces the tested candidate lists for all 100
  fresh6 queries exactly (`100/100`).
- The plugin version is 0.3.0.

## Evidence

On 100 new queries (fresh6), the picker chose the right specialist 41% of the time with the plugin's search
alone, and 59% of the time with the merged phrases (paired-bootstrap interval +8 to +28 points). Recall at
eight rose from 62% to 82%. All three pre-registered conditions held, and the result held without the five
doubtful labels.

## Limits

- The picker and the rewriter were subagents in the test. The shipped skill has the main model write the
  phrases, which has not been measured directly.
- The sample is 100 queries, and I wrote the labels. The gain is an estimate.
- The phrases are the model's own wording, so a phrase can add a wrong specialist. The picker must still
  choose, and a NONE answer is possible.

## How to check it again

Run the fresh6 pipeline (`benchmarks/experiments/pipeline_eval.py`) after any change to the phrases or the
merge. Re-run the card-check and the held-out search numbers if the roster or the embedding model changes.
