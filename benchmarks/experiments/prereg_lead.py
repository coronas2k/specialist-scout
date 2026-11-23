"""Pre-registered test of the Run 18 hybrid setting, with a 2x2 that attributes any gain.

Fixed configurations (no selection on any query set):
  kw default : k1 1.2, b 0.75, body weight 0.5, name bonus 5, fusion weight 1.0 (the plugin's values)
  kw run18   : k1 2.0, b 1.0,  body weight 0.25, name bonus 10, fusion weight 1.5 (the Run 18 values)
  full view  : MiniLM embedding of name, description and vibe (the plugin's view)
  avg_name   : average of the full-view and name-only MiniLM cosine (the Run 18 view)
  A = kw default + full   (the plugin today)
  B = kw run18   + full
  C = kw default + avg_name
  D = kw run18   + avg_name   (the Run 18 setting)
Keyword weights for name (3), description (2) and the fusion norm (max) are the same in all four.
The keyword factor bundles k1, b, body weight, name bonus and fusion weight.

Query sets: fresh1 (40), fresh2 (40), fresh3 (40). None of them selected any setting here.
Stratum, fixed in code before running: a query is "name-overlap" if any lowercase word of three or more
letters, not a stopword, appears in the name of an expected specialist; otherwise it is "plain".

Sanity check: on fresh2, A must give 15 / 21 / MRR 0.464 and D 16 / 24 / 0.508, the Run 18 numbers.
If that fails, the harness is wrong and nothing else is reported.

Usage: .venv/bin/python benchmarks/experiments/prereg_lead.py <models folder> <work dir> [minilm folder]
"""
import sys, json, pathlib, re, math
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tune_hybrid as TH
roster = TH.roster
ROOT = REPO / 'benchmarks' / 'data'
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'

SETS = {'fresh1': json.load(open(ROOT / 'fresh.json')),
        'fresh2': json.load(open(ROOT / 'fresh2.json')),
        'fresh3': json.load(open(ROOT / 'fresh3.json'))}
cases = [dict(q, split=name) for name, qs in SETS.items() for q in qs]
N = len(cases)
agents, pos = TH.agents, TH.pos
A = len(agents)
expect_idx = [np.array([pos[e] for e in c['expect'] if e in pos]) for c in cases]

WORD = re.compile(r'[a-z]{3,}')
def content_words(text):
    return {w for w in WORD.findall(text.lower()) if w not in roster.STOPWORDS}
OVERLAP = np.array([any(content_words(agents[pos[e]]['name']) & content_words(c['query'])
                        for e in c['expect'] if e in pos) for c in cases])
SPLIT = np.array([c['split'] for c in cases])

# ---- keyword side ----
QN = [set(roster.terms(c['query'])) for c in cases]
per_doc = []
for a in agents:
    per_doc.append({'name': roster.terms(a['name']), 'id': roster.terms(a['id'].replace('-', ' ')),
                    'desc': roster.terms(a['description']), 'div': roster.terms(a['division']),
                    'body': roster.terms(a['body'][:roster.BODY_CHARS])})
vocab = {}
for d in per_doc:
    for toks in d.values():
        for t in toks:
            vocab.setdefault(t, len(vocab))
for qs in QN:
    for t in qs:
        vocab.setdefault(t, len(vocab))
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

def bm25(k1, b, body_w, nb):
    F = 3.0 * M['name'] + 2.0 * M['id'] + 2.0 * M['desc'] + 1.0 * M['div'] + body_w * M['body']
    L = F.sum(1); avg = L.mean()
    K = k1 * (1 - b + b * L / avg)
    term = np.where(F > 0, F * (k1 + 1) / (F + K[:, None]), 0.0)
    s = ((term * idf[None, :]) @ QM).T
    return np.where(s > 0, s + nb * NAME_MATCH, s)

# ---- embeddings ----
embed = TH.make_embedder(minilm_dir, 'mean', '', '')
full = embed([roster.embed_text(a) for a in agents], '')
name_v = embed([a['name'] for a in agents], '')
Qv = embed([c['query'] for c in cases], '')
cos_full = Qv @ full.T
cos_name = Qv @ name_v.T
VIEW = {'full': cos_full, 'avg_name': (cos_full + cos_name) / 2}

def fuse(bm, cos, alpha):
    top = bm.max(axis=1, keepdims=True); top[top == 0] = 1.0
    return bm / top + alpha * np.maximum(cos, 0)

KW = {'default': dict(k1=1.2, b=0.75, body_w=0.5, nb=5.0, alpha=1.0),
      'run18':   dict(k1=2.0, b=1.0, body_w=0.25, nb=10.0, alpha=1.5)}
CONFIG = {'A': ('default', 'full'), 'B': ('run18', 'full'), 'C': ('default', 'avg_name'), 'D': ('run18', 'avg_name')}

def scores(cfg):
    kw, view = CONFIG[cfg]
    p = KW[kw]
    return fuse(bm25(p['k1'], p['b'], p['body_w'], p['nb']), VIEW[view], p['alpha'])

def ranks(scr):
    out = np.full(N, np.inf)
    for qi in range(N):
        e = expect_idx[qi]
        if len(e) == 0:
            continue
        bs = scr[qi, e].max()
        if bs <= 0:
            continue
        out[qi] = 1 + int(((scr[qi] > bs) & (scr[qi] > 0)).sum())
    return out

R = {cfg: ranks(scores(cfg)) for cfg in CONFIG}
def rr(r):
    return np.where(r <= 8, 1.0 / r, 0.0)

def mcn(b, c):
    n = b + c
    return 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)

def pair(x, y, idx, seed=1):
    rx, ry = R[x][idx], R[y][idx]
    f1x, f1y = rx == 1, ry == 1
    f3x, f3y = rx <= 3, ry <= 3
    b1 = int((f1x & ~f1y).sum()); c1 = int((f1y & ~f1x).sum())
    b3 = int((f3x & ~f3y).sum()); c3 = int((f3y & ~f3x).sum())
    d = rr(rx) - rr(ry)
    rng = np.random.default_rng(seed)
    boots = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)])
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return dict(n=len(idx), first_x=int(f1x.sum()), first_y=int(f1y.sum()), first_xonly=b1, first_yonly=c1,
                first_p=mcn(b1, c1), top_x=int(f3x.sum()), top_y=int(f3y.sum()), top_xonly=b3, top_yonly=c3,
                top_p=mcn(b3, c3), mrr_x=float(rr(rx).mean()), mrr_y=float(rr(ry).mean()),
                mrr_diff=float(d.mean()), lo=float(lo), hi=float(hi))

def show(label, res):
    print(f"  {label:34} n={res['n']:3}  first {res['first_x']:3} vs {res['first_y']:3} (x-only {res['first_xonly']}, y-only {res['first_yonly']}, p={res['first_p']:.3f})  "
          f"top3 {res['top_x']:3} vs {res['top_y']:3} (x-only {res['top_xonly']}, y-only {res['top_yonly']}, p={res['top_p']:.3f})  "
          f"MRR {res['mrr_x']:.3f} vs {res['mrr_y']:.3f}, diff {res['mrr_diff']:+.3f} [{res['lo']:+.3f}, {res['hi']:+.3f}]")

def table(label, idx):
    print(f"\n{label}")
    for cfg in 'ABCD':
        r = R[cfg][idx]
        print(f"  {cfg} ({CONFIG[cfg][0]:7}, {CONFIG[cfg][1]:8}): first {(r == 1).sum():3}  top3 {(r <= 3).sum():3}  MRR {rr(r).mean():.3f}")

if __name__ == '__main__':
    fresh2_idx = np.where(SPLIT == 'fresh2')[0]
    a2 = R['A'][fresh2_idx]; d2 = R['D'][fresh2_idx]
    got = ((a2 == 1).sum(), (a2 <= 3).sum(), round(rr(a2).mean(), 3), (d2 == 1).sum(), (d2 <= 3).sum(), round(rr(d2).mean(), 3))
    ok = got == (15, 21, 0.464, 16, 24, 0.508)
    print(f"harness check on fresh2 (expects A 15/21/0.464, D 16/24/0.508): got A {got[0]}/{got[1]}/{got[2]}, D {got[3]}/{got[4]}/{got[5]} -> {'PASS' if ok else 'FAIL'}")
    if not ok:
        raise SystemExit('harness check failed; nothing reported')

    f3 = np.where(SPLIT == 'fresh3')[0]
    pooled = np.where(SPLIT != 'fresh1')[0]
    all3 = np.arange(N)
    plain = pooled[~OVERLAP[pooled]]
    overl = pooled[OVERLAP[pooled]]
    print(f"\nstrata: pooled fresh2+fresh3 = {len(pooled)} queries; plain {len(plain)}, name-overlap {len(overl)}")
    print(f"fresh3 strata: plain {int((~OVERLAP[f3]).sum())}, name-overlap {int(OVERLAP[f3].sum())}")

    table('fresh3 (40 queries, held out, labels committed before any run)', f3)
    table('pooled fresh2 + fresh3 (80 queries)', pooled)

    print('\nPrimary comparison (pre-registered): D (Run 18 setting) vs A (plugin today)')
    show('fresh3', pair('D', 'A', f3))
    show('pooled fresh2 + fresh3', pair('D', 'A', pooled))
    print('\nAttribution, pooled fresh2 + fresh3 (x - y differences):')
    show('keyword effect, avg_name view: D vs C', pair('D', 'C', pooled))
    show('keyword effect, full view: B vs A', pair('B', 'A', pooled))
    show('name-view effect, default kw: C vs A', pair('C', 'A', pooled))
    show('name-view effect, run18 kw: D vs B', pair('D', 'B', pooled))

    print('\nStratified, pooled fresh2 + fresh3:')
    show('plain: D vs A', pair('D', 'A', plain))
    show('plain: C vs A (name view only)', pair('C', 'A', plain))
    show('plain: B vs A (keyword only)', pair('B', 'A', plain))
    show('name-overlap: D vs A', pair('D', 'A', overl))

    print('\nSensitivity, adding fresh1 (120 queries): D vs A')
    show('all three sets', pair('D', 'A', all3))

    rule1 = pair('D', 'A', pooled)['lo'] > 0
    rule2 = pair('D', 'A', plain)['mrr_diff'] > 0
    rule3 = pair('C', 'A', plain)['mrr_diff'] > 0
    print('\nPre-registered decision rule:')
    print(f"  1. pooled MRR CI for D-A excludes zero (lower bound > 0): {rule1}")
    print(f"  2. plain stratum D-A point estimate > 0:                  {rule2}")
    print(f"  3. plain stratum name-view effect C-A point estimate > 0: {rule3}")
    if rule1 and rule2 and rule3:
        print('  DECISION: adoption candidate (second vector set needs user approval)')
    else:
        failed = [n for n, ok in [('1', rule1), ('2', rule2), ('3', rule3)] if not ok]
        print(f"  DECISION: not supported (failed rule {', '.join(failed)})")
