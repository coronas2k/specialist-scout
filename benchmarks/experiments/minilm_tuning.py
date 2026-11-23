"""Explore tuning the current MiniLM hybrid further.

Adds two things the earlier grids did not cover: field weights for the keyword side (name and description),
and three embedding views per agent (full text, name only, description only), combined per query. Settings
are selected on the 106 earlier queries (eval, holdout, holdout2 and the workflows) with five-fold
cross-validation, and one setting is then chosen on all 106 and tested once on a second fresh set
(fresh2.json, written before this script ran). The first fresh set is reported for reference only.

Usage: .venv/bin/python benchmarks/experiments/minilm_tuning.py <models folder> <work dir> [minilm folder]
"""
import sys, json, pathlib, itertools, math
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tune_hybrid as TH
roster = TH.roster

minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
ROOT = REPO / 'benchmarks' / 'data'
S = [dict(c) for c in TH.cases]                       # the 106 earlier queries
fresh = [dict(q, split='fresh') for q in json.load(open(ROOT / 'fresh.json'))]
fresh2 = [dict(q, split='fresh2') for q in json.load(open(ROOT / 'fresh2.json'))]
cases = S + fresh + fresh2
NS, NF, NF2 = len(S), len(fresh), len(fresh2)
N = len(cases)
idx_s = np.arange(NS)
idx_fresh = np.arange(NS, NS + NF)
idx_fresh2 = np.arange(NS + NF, N)
agents, ids, pos = TH.agents, TH.ids, TH.pos
A = len(agents)
expect_idx = [np.array([pos[e] for e in c['expect'] if e in pos]) for c in cases]

# ---- keyword side with separate field weights ----
vocab = {}
def vid(t):
    if t not in vocab:
        vocab[t] = len(vocab)
    return vocab[t]
QN = [set(roster.terms(c['query'])) for c in cases]
fields = {k: np.zeros((A, 0)) for k in ['name', 'id', 'desc', 'div', 'body']}
per_doc = []
for a in agents:
    per_doc.append({'name': roster.terms(a['name']), 'id': roster.terms(a['id'].replace('-', ' ')),
                    'desc': roster.terms(a['description']), 'div': roster.terms(a['division']),
                    'body': roster.terms(a['body'][:roster.BODY_CHARS])})
for d in per_doc:
    for toks in d.values():
        for t in toks:
            vid(t)
for qs in QN:
    for t in qs:
        vid(t)
V = len(vocab)
M = {k: np.zeros((A, V)) for k in ['name', 'id', 'desc', 'div', 'body']}
PRES = np.zeros((A, V), dtype=bool)
for i, d in enumerate(per_doc):
    for k, toks in d.items():
        for t in toks:
            M[k][i, vocab[t]] += 1
            PRES[i, vocab[t]] = True
QM = np.zeros((V, N))
for qi, qs in enumerate(QN):
    for t in qs:
        QM[vocab[t], qi] = 1.0
NAME_MATCH = np.zeros((N, A), dtype=bool)
for qi in range(N):
    for i, d in enumerate(per_doc):
        nt = set(d['name'])
        NAME_MATCH[qi, i] = bool(nt) and nt <= QN[qi]
df = PRES.sum(0)
idf = np.log((A - df + 0.5) / (df + 0.5) + 1)

def bm25_fast(k1, b, nw, dw, bw, nb):
    F = nw * M['name'] + 2 * M['id'] + dw * M['desc'] + 1 * M['div'] + bw * M['body']
    L = F.sum(1); avg = L.mean()
    K = k1 * (1 - b + b * L / avg)
    term = np.where(F > 0, F * (k1 + 1) / (F + K[:, None]), 0.0)
    s = ((term * idf[None, :]) @ QM).T
    return np.where(s > 0, s + nb * NAME_MATCH, s)

# ---- three embedding views of MiniLM ----
def make_embedder(folder):
    return TH.make_embedder(folder, 'mean', '', '')
embed = make_embedder(minilm_dir)
full = embed([roster.embed_text(a) for a in agents], '')
name_v = embed([a['name'] for a in agents], '')
desc_v = embed([a['description'] for a in agents], '')
Qv = embed([c['query'] for c in cases], '')
cos_full = Qv @ full.T; cos_name = Qv @ name_v.T; cos_desc = Qv @ desc_v.T
VIEWS = {'full': cos_full, 'avg_name': (cos_full + cos_name) / 2, 'avg_desc': (cos_full + cos_desc) / 2,
         'max_name': np.maximum(cos_full, cos_name)}
print('embeddings ready', flush=True)

def fuse(bm, cos, alpha, norm):
    if norm == 'max':
        top = bm.max(axis=1, keepdims=True); top[top == 0] = 1.0
        return bm / top + alpha * np.maximum(cos, 0)
    def mm(x):
        lo = x.min(axis=1, keepdims=True); hi = x.max(axis=1, keepdims=True)
        return (x - lo) / np.where(hi - lo == 0, 1, hi - lo)
    return mm(bm) + alpha * mm(cos)

def ranks_of(scores, sel):
    Sx = scores[sel]
    E = np.zeros_like(Sx, dtype=bool)
    for row, qi in enumerate(sel):
        E[row, expect_idx[qi]] = True
    best = np.where(E, Sx, -np.inf).max(axis=1)
    rank = 1 + ((Sx > best[:, None]) & (Sx > 0)).sum(axis=1)
    return np.where(best > 0, rank.astype(float), np.inf)

def metrics(scores, sel):
    r = ranks_of(scores, sel)
    return int((r == 1).sum()), int((r <= 3).sum()), float(np.where(r <= 8, 1.0 / r, 0.0).sum())

GRID = dict(k1=[0.9, 1.2, 1.6, 2.0], b=[0.25, 0.5, 0.75, 1.0], body_w=[0.0, 0.25, 0.5], name_bonus=[0.0, 5.0, 10.0, 20.0],
            name_w=[3.0, 5.0], desc_w=[2.0, 3.0], alpha=[0.5, 1.0, 1.5, 2.0, 3.0], norm=['max', 'minmax'],
            view=list(VIEWS))
bm_keys = list(itertools.product(GRID['k1'], GRID['b'], GRID['name_w'], GRID['desc_w'], GRID['body_w'], GRID['name_bonus']))
BM = {k: bm25_fast(*k) for k in bm_keys}
settings = [(k, al, no, vw) for k in bm_keys for al in GRID['alpha'] for no in GRID['norm'] for vw in GRID['view']]
print(f'keyword settings {len(BM)}, full settings {len(settings)}', flush=True)

def score_setting(s, cosm=None):
    k, al, no, vw = s
    return fuse(BM[k], VIEWS[vw], al, no)

DEFAULT = ((1.2, 0.75, 3.0, 2.0, 0.5, 5.0), 1.0, 'max', 'full')

if __name__ == '__main__':
    rng = np.random.default_rng(0)
    order = rng.permutation(NS)
    folds = [order[i::5] for i in range(5)]
    oof = np.zeros(3); chosen = []
    for f in range(5):
        test = folds[f]; train = np.concatenate([folds[g] for g in range(5) if g != f])
        best = None
        for s in settings:
            h1, h3, mrr = metrics(score_setting(s), train)
            cand = (h3, mrr, h1, s)
            if best is None or cand[:3] > best[:3]:
                best = cand
        chosen.append(best[3])
        oof += metrics(score_setting(best[3]), test)
        print(f'fold {f + 1} chose {best[3]}', flush=True)
    d = metrics(score_setting(DEFAULT), idx_s)
    print(f"\nMiniLM default, 106 earlier queries: first {d[0]}  top three {d[1]}  MRR {d[2] / NS:.3f}")
    print(f"MiniLM expanded grid, cross-validated, 106 earlier queries: first {int(oof[0])}  top three {int(oof[1])}  MRR {oof[2] / NS:.3f}")
    best_all = None
    for s in settings:
        h1, h3, mrr = metrics(score_setting(s), idx_s)
        cand = (h3, mrr, h1, s)
        if best_all is None or cand[:3] > best_all[:3]:
            best_all = cand
    chosen_all = best_all[3]
    print(f"chosen on all 106: {chosen_all}")
    rng2 = np.random.default_rng(1)
    rd = ranks_of(score_setting(DEFAULT), idx_fresh2)
    rc = ranks_of(score_setting(chosen_all), idx_fresh2)
    f1d, f1c = rd == 1, rc == 1
    f3d, f3c = rd <= 3, rc <= 3
    def mcn(b, c):
        n = b + c
        return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)
    b1 = int((f1d & ~f1c).sum()); c1 = int((f1c & ~f1d).sum())
    b3 = int((f3d & ~f3c).sum()); c3 = int((f3c & ~f3d).sum())
    rr = lambda r: np.where(r <= 8, 1.0 / r, 0.0)
    dd = rr(rc) - rr(rd)
    boots = np.array([dd[rng2.integers(0, len(dd), len(dd))].mean() for _ in range(10000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    print(f"\nfresh2 (40, held out, new): default first {f1d.sum()}, top three {f3d.sum()}, MRR {rr(rd).mean():.3f}")
    print(f"fresh2 (40, held out, new): chosen  first {f1c.sum()}, top three {f3c.sum()}, MRR {rr(rc).mean():.3f}")
    print(f"  first place: chosen-only {c1}, default-only {b1}, McNemar p = {mcn(b1, c1):.3f}")
    print(f"  top three:   chosen-only {c3}, default-only {b3}, McNemar p = {mcn(b3, c3):.3f}")
    print(f"  MRR difference (chosen minus default) {dd.mean():+.3f}, 95% paired bootstrap CI {lo:+.3f} to {hi:+.3f}")
    rd1 = ranks_of(score_setting(DEFAULT), idx_fresh)
    rc1 = ranks_of(score_setting(chosen_all), idx_fresh)
    print(f"\nfresh (40, seen in Run 17, reference only): default first {(rd1 == 1).sum()} top three {(rd1 <= 3).sum()}; "
          f"chosen first {(rc1 == 1).sum()} top three {(rc1 <= 3).sum()}")
