"""Cross-validated hybrid tuning over a wider grid, with vectorised keyword scoring and rank metrics.

Same protocol as cv_hybrid.py: five folds, settings chosen on four folds and scored on the fifth, so
every query is scored by settings that never saw it. The grid is widened (k1 0.6 to 2.4, b 0 to 1,
body weight 0 to 1, name bonus 0 to 20, fusion weight 0.25 to 4). Keyword scores are computed once per
setting with array operations; the sanity check at start compares them with the loop version.

Usage: .venv/bin/python benchmarks/experiments/cv_hybrid_wide.py <models folder> <work dir> [minilm folder]
"""
import sys, pathlib, itertools
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tune_hybrid as TH
roster = TH.roster

models_dir = pathlib.Path(sys.argv[1])
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
PREFIX = 'Represent this sentence for searching relevant passages: '
cases, agents, ids = TH.cases, TH.agents, TH.ids
N, A = len(cases), len(agents)
pos = TH.pos
expect_idx = [np.array([pos[e] for e in c['expect'] if e in pos]) for c in cases]

# ---- vectorised keyword side ----
vocab = {}
def vid(t):
    if t not in vocab:
        vocab[t] = len(vocab)
    return vocab[t]
doc_parts = []   # per agent: (base Counter, body Counter, name set)
for a in agents:
    base = {}
    for toks, w in [(roster.terms(a['name']), 3), (roster.terms(a['id'].replace('-', ' ')), 2),
                    (roster.terms(a['description']), 2), (roster.terms(a['division']), 1)]:
        for t in toks:
            base[t] = base.get(t, 0) + w
    body = {}
    for t in roster.terms(a['body'][:roster.BODY_CHARS]):
        body[t] = body.get(t, 0) + 1
    doc_parts.append((base, body, set(roster.terms(a['name']))))
for base, body, _ in doc_parts:
    for t in list(base) + list(body):
        vid(t)
for c in cases:
    for t in roster.terms(c['query']):
        vid(t)
V = len(vocab)
BASE = np.zeros((A, V)); BODY = np.zeros((A, V)); PRES = np.zeros((A, V), dtype=bool)
for i, (base, body, _) in enumerate(doc_parts):
    for t, w in base.items():
        BASE[i, vocab[t]] = w; PRES[i, vocab[t]] = True
    for t, c in body.items():
        BODY[i, vocab[t]] = c; PRES[i, vocab[t]] = True      # presence counts body terms, as in the loop version
QM = np.zeros((V, N))
QN = [set(roster.terms(c['query'])) for c in cases]
for qi, c in enumerate(cases):
    for t in QN[qi]:
        QM[vocab[t], qi] = 1.0
NAME_MATCH = np.zeros((N, A), dtype=bool)
for qi in range(N):
    for i, (_, _, nt) in enumerate(doc_parts):
        NAME_MATCH[qi, i] = bool(nt) and nt <= QN[qi]
df = PRES.sum(0)
idf = np.log((A - df + 0.5) / (df + 0.5) + 1)


def bm25_fast(k1, b, bw, nb):
    F = BASE + bw * BODY
    L = F.sum(1)
    avg = L.mean() if L.size else 1.0
    K = k1 * (1 - b + b * L / avg)
    term = np.where(F > 0, F * (k1 + 1) / (F + K[:, None]), 0.0)
    s = (term * idf[None, :]) @ QM                  # (agents, queries)
    s = s.T
    return np.where(s > 0, s + nb * NAME_MATCH, s)


def bm25_loop(k1, b, bw, nb):
    return TH.bm25_matrix(k1, b, bw, nb)


# sanity check: the vectorised keyword scores match the loop version at the default settings
ref = bm25_loop(1.2, 0.75, 0.5, 5.0)
fast = bm25_fast(1.2, 0.75, 0.5, 5.0)
print('keyword check (max abs difference, should be ~0):', float(np.abs(ref - fast).max()), flush=True)


def ranks_of(scores, idx):
    S = scores[idx]
    E = np.zeros_like(S, dtype=bool)
    for row, qi in enumerate(idx):
        E[row, expect_idx[qi]] = True
    best = np.where(E, S, -np.inf).max(axis=1)
    rank = 1 + ((S > best[:, None]) & (S > 0)).sum(axis=1)
    return np.where(best > 0, rank.astype(float), np.inf)


def metrics(scores, idx):
    r = ranks_of(scores, idx)
    return int((r == 1).sum()), int((r <= 3).sum()), float(np.where(r <= 8, 1.0 / r, 0.0).sum())


GRID = dict(k1=[0.6, 0.9, 1.2, 1.6, 2.0, 2.4], b=[0.0, 0.25, 0.5, 0.75, 1.0], body_w=[0.0, 0.25, 0.5, 1.0],
            name_bonus=[0.0, 2.5, 5.0, 10.0, 20.0], alpha=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0], norm=['max', 'minmax'])
bm_cache = {}
for k1, b, bw, nb in itertools.product(GRID['k1'], GRID['b'], GRID['body_w'], GRID['name_bonus']):
    bm_cache[(k1, b, bw, nb)] = bm25_fast(k1, b, bw, nb)
settings = [(key, alpha, norm) for key in bm_cache for alpha in GRID['alpha'] for norm in GRID['norm']]
print(f'keyword settings: {len(bm_cache)}, full settings: {len(settings)}', flush=True)

cos = {}
def cos_for(folder, pooling, qp):
    embed = TH.make_embedder(folder, pooling, qp, '')
    Aemb = embed([roster.embed_text(a) for a in agents], '')
    Q = embed([c['query'] for c in cases], qp)
    return Q @ Aemb.T
cos['minilm-l6'] = cos_for(minilm_dir, 'mean', '')
cos['arctic-xs'] = cos_for(models_dir / 'arctic-xs', 'cls', PREFIX)
cos['arctic-xs-noprefix'] = cos_for(models_dir / 'arctic-xs', 'cls', '')
cos['gte-small'] = cos_for(models_dir / 'gte-small', 'mean', '')
cos['ensemble'] = (cos['arctic-xs'] + cos['minilm-l6']) / 2
print('embeddings ready', flush=True)

rng = np.random.default_rng(0)
order = rng.permutation(N)
folds = [order[i::5] for i in range(5)]
results = {}
for name, C in cos.items():
    oof = np.zeros(3)
    chosen = []
    for f in range(5):
        test = folds[f]
        train = np.concatenate([folds[g] for g in range(5) if g != f])
        best = None
        for key, alpha, norm in settings:
            sc = TH.fuse(bm_cache[key], C, alpha, norm)
            h1, h3, mrr = metrics(sc, train)
            cand = (h3, mrr, h1, (key, alpha, norm))
            if best is None or cand[:3] > best[:3]:
                best = cand
        key, alpha, norm = best[3]
        chosen.append(dict(k1=key[0], b=key[1], body_w=key[2], name_bonus=key[3], alpha=alpha, norm=norm))
        h1, h3, mrr = metrics(TH.fuse(bm_cache[key], C, alpha, norm), test)
        oof += [h1, h3, mrr]
    dh1, dh3, dmrr = metrics(TH.fuse(bm_cache[(1.2, 0.75, 0.5, 5.0)], C, 1.0, 'max'), np.arange(N))
    results[name] = dict(oof=oof, default=(dh1, dh3, dmrr / N), chosen=chosen)
    print(f'done {name}', flush=True)
print(f"\n{'model':20} {'default: hit@1 hit@3 MRR':>26} {'widened grid, CV: hit@1 hit@3 MRR':>36}")
for name, r in results.items():
    h1, h3, mrr = r['oof']
    dh1, dh3, dm = r['default']
    print(f"{name:20} {dh1:>10}/{N} {dh3:>3}/{N} {dm:>6.2f}   {int(h1):>20}/{N} {int(h3):>3}/{N} {mrr / N:6.2f}")
print('\nchosen settings per fold:')
for name, r in results.items():
    print(f"  {name}:")
    for f, s in enumerate(r['chosen'], 1):
        print(f"    fold {f}: {s}")
