# Pre-registration: end-to-end accuracy and query rewriting (fresh6)

Written before any picker or rewriter runs on `fresh6`. Labels: `benchmarks/data/fresh6.json` (100 queries),
committed in `6706d34` with no results. Branch `explore/pipeline-eval`.

## Question

The plugin's current search finds the right specialist in the top 8 for 71% of new queries, but it's the
choice from that shortlist that the user experiences. Two things are measured end to end:

- **Arm A (current):** the plugin's hybrid search (limit 8) with the original request, then a picker
  chooses one specialist from the list.
- **Arm B (rewriting):** a rewriter writes four search phrases for the request, without seeing candidates or
  labels. The search runs on the original request and each phrase. The five rankings are merged by each
  specialist's best rank (ties go to the original request's rank). The top 8 go to the same picker.

## Proxies, stated plainly

The picker and rewriter are fresh-context subagents, not the main session. They stand in for the skill's
behaviour. The same picker prompt is used in both arms. Results measure these proxies, not every user session.

## Protocol

- Picker input: the request and up to 8 candidates (id, name, description). Output: one id, or NONE.
- Batches of 25 requests per subagent (four batches per arm). The raw outputs are saved in
  `benchmarks/results/pipeline-*.json`.
- Rewriter input: the request only. Output: four phrases. It may not add names of tools or people that are not
  in the request.
- Metrics per arm: end-to-end pick accuracy (picked id is an expected id), recall@8 of the list the picker
  sees, and the number of tokens used by the rewriter and picker subagents (reported as the measured total).

## Strata and sensitivity

Name-overlap (32 queries) and plain (68 queries), as before. Five labels are doubtful and kept, not edited:
#28 "a travel itinerary template for corporate events", #45 "a lesson plan on photosynthesis for year seven",
#51 "a complaint about a noisy neighbour in a rental", #60 "a diet plan for an athlete in training" and #90 "a
schedule for planting in a community garden". A sensitivity run without them is reported alongside.

## Decision rule (fixed before the run)

Arm B is an adoption candidate only if **all three** hold on `fresh6`:

1. The 95% paired-bootstrap interval for end-to-end accuracy (B minus A) has a lower bound above zero.
2. Recall@8 for B is at least that of A.
3. On the plain stratum, end-to-end accuracy (B minus A) has a non-negative point estimate.

Outcomes, as before: **not supported** if rule 1 fails and the interval's upper bound is below 0.06;
**inconclusive** otherwise. Adoption also needs the user's approval, because the skill's instructions would
change.

## Caveats

- 100 queries gives roughly ±10 points on an accuracy near 60%. Only differences above about 0.1 are detectable.
- The picker and rewriter are subagents, so a difference could come from the subagent's behaviour, not from
  the plugin. Both arms use the same picker.
- Rewriting is not the only option. The alias file and the search tuning are not tested here.
