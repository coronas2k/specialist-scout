"""Compare fusion weightings for keyword and embedding scores (run with the skill venv, from the skill folder)."""
import json, sys
import pathlib
SKILL = pathlib.Path(__file__).resolve().parent.parent
DATA = pathlib.Path(__file__).resolve().parent / 'data'
sys.path.insert(0, str(SKILL / 'scripts'))
import roster
s = roster.Searcher('hybrid')
sets = {f: json.load(open(DATA / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}

def signals(query):
    qt = roster.terms(query)
    bm = {}
    qset = set(qt)
    for i, (agent, tf, length) in enumerate(s.docs):
        sc = roster.bm25(qt, tf, length, s.df, s.n, s.avg) if qt else 0.0
        if qt and set(roster.terms(agent['name'])) <= qset and roster.terms(agent['name']):
            sc += roster.NAME_MATCH_BONUS
        bm[i] = sc
    qv = roster.embed(s.runtime, [query])[0]
    sims = s.vectors @ qv
    emb = {i: float(sims[s.row[s.pool[i]['id']]]) for i in range(len(s.pool))}
    return bm, emb

def rrf(bm, emb, w_emb):
    order_b = sorted(bm, key=lambda i: -bm[i])
    order_e = sorted(emb, key=lambda i: -emb[i])
    f = {}
    for r, i in enumerate(order_b): f[i] = f.get(i, 0) + 1 / (60 + r + 1) if bm[i] > 0 else f.get(i, 0)
    for r, i in enumerate(order_e): f[i] = f.get(i, 0) + w_emb / (60 + r + 1)
    return f

def linear(bm, emb, alpha):
    mb = max(bm.values()) or 1.0
    return {i: bm[i] / mb + alpha * max(0.0, emb[i]) for i in bm}

variants = {
    'bm25 only': lambda bm, emb: bm,
    'rrf w_emb=1.0': lambda bm, emb: rrf(bm, emb, 1.0),
    'rrf w_emb=0.5': lambda bm, emb: rrf(bm, emb, 0.5),
    'linear a=0.5': lambda bm, emb: linear(bm, emb, 0.5),
    'linear a=1.0': lambda bm, emb: linear(bm, emb, 1.0),
    'linear a=2.0': lambda bm, emb: linear(bm, emb, 2.0),
}
cache = {}
for f, cases in sets.items():
    for c in cases:
        cache[(f, c['query'])] = signals(c['query'])

for name, fn in variants.items():
    row = []
    tot = [0, 0, 0.0, 0]
    for f, cases in sets.items():
        h1 = h3 = 0; mrr = 0.0
        for c in cases:
            bm, emb = cache[(f, c['query'])]
            scores = fn(bm, emb)
            ranked = sorted((i for i in scores if scores[i] > 0), key=lambda i: (-scores[i], s.pool[i]['division'], s.pool[i]['id']))
            ids = [s.pool[i]['id'] for i in ranked[:8]]
            rk = next((k + 1 for k, x in enumerate(ids) if x in c['expect']), None)
            h1 += rk == 1; h3 += bool(rk and rk <= 3); mrr += 1 / rk if rk else 0
        n = len(cases)
        row.append(f"{h3/n:4.0%}")
        tot[0] += h1; tot[1] += h3; tot[2] += mrr; tot[3] += n
    print(f"{name:15} hit@3 by set {' / '.join(row)}   ALL: hit@1 {tot[0]/tot[3]:.0%} hit@3 {tot[1]/tot[3]:.0%} MRR {tot[2]/tot[3]:.2f}")
