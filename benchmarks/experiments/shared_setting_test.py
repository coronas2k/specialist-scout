"""One shared hybrid setting for two models, chosen on tuning data only; then a paired per-query test on
held-out data.

Splits: tuning = eval.json + holdout.json (56 queries); fresh = fresh.json (40 queries, written before any
model was run on it); validation = holdout2.json + workflows (50 queries, used earlier for diagnosis).
The shared setting maximises the two models' combined top-three hits on the tuning split (then MRR, then
first place). Each model is then scored with that setting on the held-out splits. The paired test uses an
exact McNemar test on per-query first-place and top-three outcomes, and a paired bootstrap for the mean
difference in reciprocal rank.

Usage: .venv/bin/python benchmarks/experiments/shared_setting_test.py <models folder> <work dir> [minilm folder]
"""
import sys, json, pathlib, itertools, math
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tune_hybrid as TH
roster = TH.roster

models_dir = pathlib.Path(sys.argv[1])
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
PREFIX = 'Represent this sentence for searching relevant passages: '
ROOT = REPO / 'benchmarks' / 'data'
def load(f): return json.load(open(ROOT / f))
tune = [dict(q, split='tune') for f in ['eval.json', 'holdout.json'] for q in load(f)]
val = [dict(q, split='validate') for q in load('holdout2.json')] + \
      [{'query': s['query'], 'expect': s['expect'], 'split': 'validate'} for w in load('workflows.json') for s in w['subtasks']]
fresh = [dict(q, split='fresh') for q in load('fresh.json')]
cases = tune + val + fresh
N = len(cases)
idx = {k: np.array([i for i, c in enumerate(cases) if c['split'] == k]) for k in ['tune', 'validate', 'fresh']}
agents, ids, pos = TH.agents, TH.ids, TH.pos
A = len(agents)
expect_idx = [np.array([pos[e] for e in c['expect'] if e in pos]) for c in cases]

# ---- keyword side (same construction as cv_hybrid_wide.py) ----
vocab = {}
def vid(t):
    if t not in vocab:
        vocab[t] = len(vocab)
    return vocab[t]
parts = []
for a in agents:
    base = {}
    for toks, w in [(roster.terms(a['name']), 3), (roster.terms(a['id'].replace('-', ' ')), 2),
                    (roster.terms(a['description']), 2), (roster.terms(a['division']), 1)]:
        for t in toks:
            base[t] = base.get(t, 0) + w
    body = {}
    for t in roster.terms(a['body'][:roster.BODY_CHARS]):
        body[t] = body.get(t, 0) + 1
    parts.append((base, body, set(roster.terms(a['name']))))
for base, body, _ in parts:
    for t in list(base) + list(body):
        vid(t)
QN = [set(roster.terms(c['query'])) for c in cases]
for qs in QN:
    for t in qs:
        vid(t)
V = len(vocab)
BASE = np.zeros((A, V)); BODY = np.zeros((A, V)); PRES = np.zeros((A, V), dtype=bool)
for i, (base, body, _) in enumerate(parts):
    for t, w in base.items():
        BASE[i, vocab[t]] = w; PRES[i, vocab[t]] = True
    for t, c in body.items():
        BODY[i, vocab[t]] = c; PRES[i, vocab[t]] = True
QM = np.zeros((V, N))
for qi, qs in enumerate(QN):
    for t in qs:
        QM[vocab[t], qi] = 1.0
NAME_MATCH = np.zeros((N, A), dtype=bool)
for qi in range(N):
    for i, (_, _, nt) in enumerate(parts):
        NAME_MATCH[qi, i] = bool(nt) and nt <= QN[qi]
df = PRES.sum(0)
idf = np.log((A - df + 0.5) / (df + 0.5) + 1)

def bm25_fast(k1, b, bw, nb):
    F = BASE + bw * BODY
    L = F.sum(1); avg = L.mean()
    K = k1 * (1 - b + b * L / avg)
    term = np.where(F > 0, F * (k1 + 1) / (F + K[:, None]), 0.0)
    s = ((term * idf[None, :]) @ QM).T
    return np.where(s > 0, s + nb * NAME_MATCH, s)

def ranks_of(scores, sel):
    S = scores[sel]
    E = np.zeros_like(S, dtype=bool)
    for row, qi in enumerate(sel):
        E[row, expect_idx[qi]] = True
    best = np.where(E, S, -np.inf).max(axis=1)
    rank = 1 + ((S > best[:, None]) & (S > 0)).sum(axis=1)
    return np.where(best > 0, rank.astype(float), np.inf)

def metrics(scores, sel):
    r = ranks_of(scores, sel)
    return int((r == 1).sum()), int((r <= 3).sum()), float(np.where(r <= 8, 1.0 / r, 0.0).sum())

# ---- embeddings ----
def cos_for(folder, pooling, qp):
    embed = TH.make_embedder(folder, pooling, qp, '')
    Aemb = embed([roster.embed_text(a) for a in agents], '')
    Q = embed([c['query'] for c in cases], qp)
    return Q @ Aemb.T
MODELS = {'MiniLM-L6': cos_for(minilm_dir, 'mean', ''),
          'arctic-xs (prefix)': cos_for(models_dir / 'arctic-xs', 'cls', PREFIX)}
print('embeddings ready', flush=True)

GRID = dict(k1=[0.6, 0.9, 1.2, 1.6, 2.0, 2.4], b=[0.0, 0.25, 0.5, 0.75, 1.0], body_w=[0.0, 0.25, 0.5, 1.0],
            name_bonus=[0.0, 2.5, 5.0, 10.0, 20.0], alpha=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0], norm=['max', 'minmax'])
def fuse(bm, cos, alpha, norm):
    if norm == 'max':
        top = bm.max(axis=1, keepdims=True); top[top == 0] = 1.0
        return bm / top + alpha * np.maximum(cos, 0)
    def mm(x):
        lo = x.min(axis=1, keepdims=True); hi = x.max(axis=1, keepdims=True)
        return (x - lo) / np.where(hi - lo == 0, 1, hi - lo)
    return mm(bm) + alpha * mm(cos)

bm_cache = {}
for k1, b, bw, nb in itertools.product(GRID['k1'], GRID['b'], GRID['body_w'], GRID['name_bonus']):
    bm_cache[(k1, b, bw, nb)] = bm25_fast(k1, b, bw, nb)
settings = [(key, alpha, norm) for key in bm_cache for alpha in GRID['alpha'] for norm in GRID['norm']]

# ---- choose one shared setting on the tuning split only ----
best = None
for key, alpha, norm in settings:
    tot = np.zeros(3)
    for name, C in MODELS.items():
        tot += metrics(fuse(bm_cache[key], C, alpha, norm), idx['tune'])
    cand = (tot[1], tot[2], tot[0], (key, alpha, norm))
    if best is None or cand[:3] > best[:3]:
        best = cand
key, alpha, norm = best[3]
shared = dict(k1=key[0], b=key[1], body_w=key[2], name_bonus=key[3], alpha=alpha, norm=norm)
print('shared setting (chosen on tuning split only):', shared, flush=True)
BM = bm_cache[key]

def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, p)

def paired_report(split_name, sel):
    rng = np.random.default_rng(0)
    rA = ranks_of(fuse(BM, MODELS['arctic-xs (prefix)'], alpha, norm), sel)
    rM = ranks_of(fuse(BM, MODELS['MiniLM-L6'], alpha, norm), sel)
    first_a, first_m = rA == 1, rM == 1
    top_a, top_m = rA <= 3, rM <= 3
    b1 = int((first_m & ~first_a).sum()); c1 = int((first_a & ~first_m).sum())
    b3 = int((top_m & ~top_a).sum()); c3 = int((top_a & ~top_m).sum())
    rr = lambda r: np.where(r <= 8, 1.0 / r, 0.0)
    d = rr(rA) - rr(rM)
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    n = len(sel)
    print(f"\n[{split_name}] n={n}")
    print(f"  first place : arctic {first_a.sum()}/{n}  MiniLM {first_m.sum()}/{n}  "
          f"arctic-only {c1}, MiniLM-only {b1}, McNemar p = {mcnemar_exact(b1, c1):.3f}")
    print(f"  top three   : arctic {top_a.sum()}/{n}  MiniLM {top_m.sum()}/{n}  "
          f"arctic-only {c3}, MiniLM-only {b3}, McNemar p = {mcnemar_exact(b3, c3):.3f}")
    print(f"  mean reciprocal rank difference (arctic minus MiniLM): {d.mean():+.3f} "
          f"(95% paired bootstrap CI {lo:+.3f} to {hi:+.3f})")

print('\n=== tuning split (used to choose the shared setting) ===')
for name, C in MODELS.items():
    h1, h3, mrr = metrics(fuse(BM, C, alpha, norm), idx['tune'])
    print(f"  {name:20} first {h1}/{len(idx['tune'])}  top three {h3}/{len(idx['tune'])}  MRR {mrr / len(idx['tune']):.3f}")
paired_report('fresh (held out, written before any run)', idx['fresh'])
paired_report('validation (held out)', idx['validate'])
pooled = np.concatenate([idx['fresh'], idx['validate']])
paired_report('fresh + validation pooled (held out)', pooled)

print('\n=== reference: each model at its own default settings, fresh set ===')
for name, C in MODELS.items():
    h1, h3, mrr = metrics(fuse(bm25_fast(1.2, 0.75, 0.5, 5.0), C, 1.0, 'max'), idx['fresh'])
    print(f"  {name:20} first {h1}/40  top three {h3}/40  MRR {mrr / 40:.3f}")
