"""Tune the hybrid search's parameters for each embedding model, with a train/validation split.

Tuning split: eval.json and holdout.json (56 queries). Validation split: holdout2.json and the workflows
(50 queries). Parameters are chosen on the tuning split only; validation is reported for defaults and for
the chosen settings. The keyword side, the fusion and the embedding model are all varied.

Usage: .venv/bin/python benchmarks/experiments/tune_hybrid.py <models folder> <work dir> [minilm folder]
"""
import json, sys, pathlib, itertools, time
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
from collections import Counter

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import roster  # noqa: E402

models_dir = pathlib.Path(sys.argv[1]); work = pathlib.Path(sys.argv[2])
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
SPECS = {
    'minilm-l6': (minilm_dir, 'mean', '', ''),
    'arctic-xs': (models_dir / 'arctic-xs', 'cls', 'Represent this sentence for searching relevant passages: ', ''),
    'gte-small': (models_dir / 'gte-small', 'mean', '', ''),
}
ROOT = REPO / 'benchmarks' / 'data'
cases = []
for f in ['eval.json', 'holdout.json']:
    cases += [dict(c, split='tune') for c in json.load(open(ROOT / f))]
for f in ['holdout2.json']:
    cases += [dict(c, split='validate') for c in json.load(open(ROOT / f))]
for w in json.load(open(ROOT / 'workflows.json')):
    cases += [{'query': s['query'], 'expect': s['expect'], 'split': 'validate'} for s in w['subtasks']]
tune_idx = [i for i, c in enumerate(cases) if c['split'] == 'tune']
val_idx = [i for i, c in enumerate(cases) if c['split'] == 'validate']
agents = list(roster.agents())
ids = [a['id'] for a in agents]
pos = {a: i for i, a in enumerate(ids)}


def make_embedder(folder, pooling, qp, dp):
    tok = Tokenizer.from_file(str(folder / 'tokenizer.json'))
    tok.enable_truncation(max_length=256)
    tok.enable_padding(pad_id=tok.token_to_id('[PAD]') or 0, pad_token='[PAD]')
    sess = ort.InferenceSession(str(folder / 'model.onnx'), providers=['CPUExecutionProvider'])
    names = {i.name for i in sess.get_inputs()}
    out = sess.get_outputs()[0].name

    def embed(texts, prefix):
        texts = [prefix + t for t in texts]
        res = []
        for start in range(0, len(texts), 32):
            enc = tok.encode_batch(texts[start:start + 32])
            feeds = {'input_ids': np.array([e.ids for e in enc], dtype=np.int64),
                     'attention_mask': np.array([e.attention_mask for e in enc], dtype=np.int64)}
            if 'token_type_ids' in names:
                feeds['token_type_ids'] = np.array([e.type_ids for e in enc], dtype=np.int64)
            hid = sess.run([out], feeds)[0]
            if pooling == 'cls':
                v = hid[:, 0, :]
            else:
                m = feeds['attention_mask'][..., None].astype(np.float32)
                v = (hid * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            res.append(v / np.linalg.norm(v, axis=1, keepdims=True))
        return np.concatenate(res)
    return embed


def cos_matrix(name):
    folder, pooling, qp, dp = SPECS[name]
    embed = make_embedder(folder, pooling, qp, dp)
    A = embed([roster.embed_text(a) for a in agents], dp)
    Q = embed([c['query'] for c in cases], qp)
    return Q @ A.T                                          # (queries, agents)


# keyword side, rebuilt with explicit parameters (checked against roster.Searcher('bm25') below)
def bm25_matrix(k1, b, body_w, name_bonus):
    docs = []
    for a in agents:
        parts = [(roster.terms(a['name']), 3), (roster.terms(a['id'].replace('-', ' ')), 2),
                 (roster.terms(a['description']), 2), (roster.terms(a['division']), 1),
                 (roster.terms(a['body'][:roster.BODY_CHARS]), body_w)]
        tf = Counter()
        for toks, w in parts:
            for t in toks:
                tf[t] += w
        docs.append((tf, sum(tf.values()), set(roster.terms(a['name']))))
    n = len(docs); avg = sum(d[1] for d in docs) / n
    df = Counter()
    for tf, _, _ in docs:
        df.update(tf.keys())
    out = np.zeros((len(cases), n))
    for qi, c in enumerate(cases):
        qt = roster.terms(c['query']); qset = set(qt)
        if not qt:
            continue
        for di, (tf, length, nt) in enumerate(docs):
            s = 0.0
            for t in set(qt):
                f = tf.get(t, 0)
                if f:
                    idf = np.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1)
                    s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * length / avg))
            if s and nt and nt <= qset:
                s += name_bonus
            out[qi, di] = s
    return out


def fuse(bm, cos, alpha, norm):
    if norm == 'max':
        top = bm.max(axis=1, keepdims=True)
        top[top == 0] = 1.0
        return bm / top + alpha * np.maximum(cos, 0)
    def mm(x):
        lo = x.min(axis=1, keepdims=True); hi = x.max(axis=1, keepdims=True)
        return (x - lo) / np.where(hi - lo == 0, 1, hi - lo)
    return mm(bm) + alpha * mm(cos)


def metrics(scores, idx):
    h1 = h3 = 0; mrr = 0.0
    for qi in idx:
        order = np.argsort(-scores[qi], kind='stable')
        order = [j for j in order if scores[qi, j] > 0][:8]
        expect = set(cases[qi]['expect'])
        r = next((k + 1 for k, j in enumerate(order) if ids[j] in expect), None)
        h1 += r == 1; h3 += bool(r and r <= 3); mrr += (1 / r) if r else 0.0
    n = len(idx)
    return h1, h3, mrr / n, n


DEFAULT = dict(k1=1.2, b=0.75, body_w=0.5, name_bonus=5.0, alpha=1.0, norm='max')
GRID = dict(k1=[0.9, 1.2, 1.6], b=[0.5, 0.75, 1.0], body_w=[0.0, 0.5, 1.0], name_bonus=[0.0, 5.0, 10.0],
            alpha=[0.5, 1.0, 1.5, 2.0], norm=['max', 'minmax'])

if __name__ == '__main__':
    print('cases:', len(cases), 'tune:', len(tune_idx), 'validate:', len(val_idx))
    # sanity: the keyword side reproduces the plugin's BM25 search
    bm_default = bm25_matrix(DEFAULT['k1'], DEFAULT['b'], DEFAULT['body_w'], DEFAULT['name_bonus'])
    s = roster.Searcher('bm25')
    rank_plugin = [a['id'] for a in s.rank(cases[0]['query'], limit=8)]
    rank_mine = [ids[j] for j in np.argsort(-bm_default[0], kind='stable')[:8] if bm_default[0, j] > 0]
    print('keyword check, first query identical:', rank_plugin == rank_mine)
    results = {}
    for name in SPECS:
        t0 = time.perf_counter()
        cos = cos_matrix(name)
        print(f'{name}: embedded in {time.perf_counter() - t0:.1f}s')
        results[name] = {'cos': cos}
    bm_cache = {}
    for name in SPECS:
        cos = results[name]['cos']
        best = None
        for k1, b, bw, nb in itertools.product(GRID['k1'], GRID['b'], GRID['body_w'], GRID['name_bonus']):
            key = (k1, b, bw, nb)
            if key not in bm_cache:
                bm_cache[key] = bm25_matrix(k1, b, bw, nb)
            bm = bm_cache[key]
            for alpha, norm in itertools.product(GRID['alpha'], GRID['norm']):
                sc = fuse(bm, cos, alpha, norm)
                h1, h3, mrr, n = metrics(sc, tune_idx)
                cand = (h3, mrr, h1, dict(k1=k1, b=b, body_w=bw, name_bonus=nb, alpha=alpha, norm=norm))
                if best is None or cand[:3] > best[:3]:
                    best = cand
        results[name]['best'] = best[3]
    print(f"\n{'model':12} {'settings':12} {'tune hit@1/3':>14} {'validate hit@1/3':>18} {'validate MRR':>13}")
    bm_def = bm25_matrix(DEFAULT['k1'], DEFAULT['b'], DEFAULT['body_w'], DEFAULT['name_bonus'])
    for name in SPECS:
        cos = results[name]['cos']
        for label, params in [('default', DEFAULT), ('tuned', results[name]['best'])]:
            bm = bm25_matrix(params['k1'], params['b'], params['body_w'], params['name_bonus'])
            sc = fuse(bm, cos, params['alpha'], params['norm'])
            t1, t3, _, tn = metrics(sc, tune_idx)
            v1, v3, vmrr, vn = metrics(sc, val_idx)
            print(f"{name:12} {label:12} {t1:>6}/{tn} {t3:>3}/{tn}   {v1:>7}/{vn} {v3:>3}/{vn}      {vmrr:6.2f}")
    print('\nchosen settings:')
    for name in SPECS:
        print(f"  {name}: {results[name]['best']}")
