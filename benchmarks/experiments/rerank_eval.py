"""Rerank the current hybrid search's top candidates with a cross-encoder (ONNX, CPU).

The cross-encoder reads the query and each candidate together and returns one relevance score.
The folder holds model.onnx and tokenizer.json, for example:
  cross-encoder/ms-marco-MiniLM-L6-v2 (Apache-2.0), onnx/model_qint8_arm64.onnx
  jinaai/jina-reranker-v1-tiny-en (Apache-2.0), onnx/model_int8.onnx

Usage: .venv/bin/python benchmarks/experiments/rerank_eval.py <model folder> [top_k]
"""
import json, sys, time, pathlib
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import roster  # noqa: E402

folder = pathlib.Path(sys.argv[1])
TOP = int(sys.argv[2]) if len(sys.argv) > 2 else 15
tok = Tokenizer.from_file(str(folder / 'tokenizer.json'))
tok.enable_truncation(max_length=256)
tok.no_padding()
sess = ort.InferenceSession(str(folder / 'model.onnx'), providers=['CPUExecutionProvider'])
wants_types = 'token_type_ids' in {i.name for i in sess.get_inputs()}


def rerank_scores(query, docs):
    enc = [tok.encode(query, d) for d in docs]
    L = max(len(e.ids) for e in enc)
    ids = np.zeros((len(enc), L), dtype=np.int64)
    mask = np.zeros_like(ids)
    types = np.zeros_like(ids)
    for i, e in enumerate(enc):
        n = len(e.ids)
        ids[i, :n] = e.ids
        mask[i, :n] = 1
        types[i, :n] = e.type_ids
    feeds = {'input_ids': ids, 'attention_mask': mask}
    if wants_types:
        feeds['token_type_ids'] = types
    return sess.run(['logits'], feeds)[0].reshape(-1)


ROOT = REPO / 'benchmarks' / 'data'
sets = {f: json.load(open(ROOT / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}
wf = json.load(open(ROOT / 'workflows.json'))
cases = [c for f in sets.values() for c in f] + [{'query': s['query'], 'expect': s['expect']} for w in wf for s in w['subtasks']]

searcher = roster.Searcher('hybrid')
by_id = {a['id']: a for a in searcher.pool}
base_h1 = base_h3 = 0
modes = {'rerank only': [0, 0], 'hybrid rank + rerank (RRF)': [0, 0]}
rerank_seconds = 0.0
for c in cases:
    hybrid = [a['id'] for a in searcher.rank(c['query'], limit=TOP)]
    expect = set(c['expect'])
    r = next((k + 1 for k, x in enumerate(hybrid[:8]) if x in expect), None)
    base_h1 += r == 1
    base_h3 += bool(r and r <= 3)
    docs = [roster.embed_text(by_id[i]) for i in hybrid]
    t0 = time.perf_counter()
    scores = rerank_scores(c['query'], docs)
    rerank_seconds += time.perf_counter() - t0
    order_rerank = [hybrid[i] for i in np.argsort(-scores)]
    rrf = {}
    for pos, i in enumerate(hybrid):
        rrf[i] = rrf.get(i, 0.0) + 1 / (60 + pos + 1)
    for pos, i in enumerate(order_rerank):
        rrf[i] = rrf.get(i, 0.0) + 1 / (60 + pos + 1)
    order_rrf = sorted(rrf, key=lambda i: -rrf[i])
    for name, order in [('rerank only', order_rerank), ('hybrid rank + rerank (RRF)', order_rrf)]:
        rr = next((k + 1 for k, x in enumerate(order[:8]) if x in expect), None)
        modes[name][0] += rr == 1
        modes[name][1] += bool(rr and rr <= 3)
n = len(cases)
print(f"model {folder.name}, top {TOP} candidates, {n} queries")
print(f"  current hybrid       hit@1 {base_h1}/{n} ({base_h1/n:.0%})  hit@3 {base_h3}/{n} ({base_h3/n:.0%})")
for name, (a, b) in modes.items():
    print(f"  {name:28} hit@1 {a}/{n} ({a/n:.0%})  hit@3 {b}/{n} ({b/n:.0%})")
print(f"  reranker time: {rerank_seconds / n * 1000:.0f} ms per query ({TOP} pairs)")
