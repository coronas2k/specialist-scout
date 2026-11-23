"""Cross-validated comparison of hybrid search settings on all 106 queries.

Five folds (deterministic shuffle). For each fold, the best settings are chosen on the other four folds
(by top-three hits, then MRR, then first-place hits) and scored on the held-out fold. Every query is
therefore scored by settings that never saw it. Also reports fixed default settings, for reference.

Compared:
  minilm-l6            current model, query without prefix
  arctic-xs            arctic-embed-xs with its query prefix
  arctic-xs-noprefix   arctic-embed-xs without the query prefix
  ensemble             arctic-embed-xs plus MiniLM-L6, averaged cosine (two models; not a plugin candidate)

Usage: .venv/bin/python benchmarks/experiments/cv_hybrid.py <models folder> <work dir> [minilm folder]
"""
import sys, pathlib, itertools
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tune_hybrid as TH

models_dir = pathlib.Path(sys.argv[1])
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
PREFIX = 'Represent this sentence for searching relevant passages: '
cases = TH.cases
N = len(cases)
rng = np.random.default_rng(0)
order = rng.permutation(N)
folds = [order[i::5] for i in range(5)]


def cos_for(folder, pooling, qp):
    embed = TH.make_embedder(folder, pooling, qp, '')
    A = embed([TH.roster.embed_text(a) for a in TH.agents], '')
    Q = embed([c['query'] for c in cases], qp)
    return Q @ A.T


cos = {
    'minilm-l6': cos_for(minilm_dir, 'mean', ''),
    'arctic-xs': cos_for(models_dir / 'arctic-xs', 'cls', PREFIX),
    'arctic-xs-noprefix': cos_for(models_dir / 'arctic-xs', 'cls', ''),
}
cos['ensemble'] = (cos['arctic-xs'] + cos['minilm-l6']) / 2
print('embeddings ready', flush=True)

GRID = TH.GRID
bm_cache = {}
for k1, b, bw, nb in itertools.product(GRID['k1'], GRID['b'], GRID['body_w'], GRID['name_bonus']):
    bm_cache[(k1, b, bw, nb)] = TH.bm25_matrix(k1, b, bw, nb)
print('keyword matrices ready', flush=True)
settings = [(key, alpha, norm) for key in bm_cache for alpha in GRID['alpha'] for norm in GRID['norm']]


def fold_metrics(scores, idx):
    h1 = h3 = 0; mrr = 0.0
    for qi in idx:
        o = [j for j in np.argsort(-scores[qi], kind='stable') if scores[qi, j] > 0][:8]
        expect = set(cases[qi]['expect'])
        r = next((k + 1 for k, j in enumerate(o) if TH.ids[j] in expect), None)
        h1 += r == 1; h3 += bool(r and r <= 3); mrr += (1 / r) if r else 0.0
    return h1, h3, mrr


results = {}
for name, C in cos.items():
    oof = np.zeros(3)                                  # hit@1, hit@3, sum of reciprocal ranks
    chosen = []
    for f in range(5):
        test = folds[f]
        train = np.concatenate([folds[g] for g in range(5) if g != f])
        best = None
        for key, alpha, norm in settings:
            sc = TH.fuse(bm_cache[key], C, alpha, norm)
            h1, h3, mrr = fold_metrics(sc, train)
            cand = (h3, mrr, h1, (key, alpha, norm))
            if best is None or cand[:3] > best[:3]:
                best = cand
        key, alpha, norm = best[3]
        chosen.append(dict(k1=key[0], b=key[1], body_w=key[2], name_bonus=key[3], alpha=alpha, norm=norm))
        sc = TH.fuse(bm_cache[key], C, alpha, norm)
        h1, h3, mrr = fold_metrics(sc, test)
        oof += [h1, h3, mrr]
    default = TH.fuse(bm_cache[(1.2, 0.75, 0.5, 5.0)], C, 1.0, 'max')
    dh1, dh3, dmrr = fold_metrics(default, range(N))
    results[name] = dict(oof=oof, default=(dh1, dh3, dmrr / N), chosen=chosen)
print(f"\n{'model':20} {'default: hit@1 hit@3 MRR':>26} {'tuned by CV: hit@1 hit@3 MRR':>31}")
for name, r in results.items():
    h1, h3, mrr = r['oof']
    dh1, dh3, dm = r['default']
    print(f"{name:20} {dh1:>10}/{N} {dh3:>3}/{N} {dm:>6.2f}   {int(h1):>13}/{N} {int(h3):>3}/{N} {mrr / N:6.2f}")
print('\nchosen settings per fold:')
for name, r in results.items():
    print(f"  {name}:")
    for f, s in enumerate(r['chosen'], 1):
        print(f"    fold {f}: {s}")
