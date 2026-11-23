"""Score late-interaction (ColBERT) ranking alone and combined with keyword search on all 106 queries.

Usage: .venv/bin/python benchmarks/experiments/colbert_eval.py <folder> [model file, default model_int8.onnx]
The folder holds tokenizer.json and the model file.
(answerai-colbert-small-v1, Apache-2.0, pinned at commit 934fa8bb.)
"""
import json, sys, pathlib
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts')); sys.path.insert(0, str(pathlib.Path(__file__).parent))
import roster
from colbert_core import ColBERT
ROOT = REPO / 'benchmarks' / 'data'
sets = {f: json.load(open(ROOT / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}
wf = json.load(open(ROOT / 'workflows.json'))
cases = [c for f in sets.values() for c in f] + [{'query': s['query'], 'expect': s['expect']} for w in wf for s in w['subtasks']]
print('queries:', len(cases))

agents = list(roster.agents())
model_file = sys.argv[2] if len(sys.argv) > 2 else 'model_int8.onnx'
print('model file:', model_file)
m = ColBERT(str(pathlib.Path(sys.argv[1])), model_file=model_file)
docs = [m.encode_doc(roster.embed_text(a)) for a in agents]
print('doc token counts: mean %.1f max %d' % (np.mean([d.shape[0] for d in docs]), max(d.shape[0] for d in docs)))

bm = roster.Searcher('bm25')
def bm_scores(query):
    qt = roster.terms(query); qset = set(qt)
    out = np.zeros(len(agents))
    for i, (agent, tf, length) in enumerate(bm.docs):
        if not qt: continue
        s = roster.bm25(qt, tf, length, bm.df, bm.n, bm.avg)
        nt = set(roster.terms(agent['name']))
        if nt and nt <= qset: s += roster.NAME_MATCH_BONUS
        out[i] = s
    return out

def colbert_scores(query):
    q = m.encode_query(query)
    return np.array([float((q @ d.T).max(axis=1).sum()) for d in docs])

def rank_hits(scores, expect):
    order = np.argsort(-scores)
    ids = [agents[i]['id'] for i in order[:8]]
    return next((k + 1 for k, x in enumerate(ids) if x in expect), None)

def mm(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-9)

pre = [(bm_scores(c['query']), colbert_scores(c['query'])) for c in cases]
def evaluate(name, fn):
    h1 = h3 = 0
    for c, (b, cb) in zip(cases, pre):
        r = rank_hits(fn(b, cb), set(c['expect']))
        h1 += r == 1; h3 += bool(r and r <= 3)
    print(f"{name:34} hit@1 {h1}/{len(cases)} ({h1/len(cases):.0%})  hit@3 {h3}/{len(cases)} ({h3/len(cases):.0%})")

evaluate('keyword (BM25 + name bonus)', lambda b, cb: b)
evaluate('late interaction alone', lambda b, cb: cb)
for a in [0.5, 1.0, 2.0]:
    evaluate(f'keyword + late interaction a={a}', lambda b, cb, a=a: (b / (b.max() or 1.0)) + a * mm(cb))
