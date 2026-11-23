"""Compare embedding models in the plugin's own hybrid search, on all 106 queries.

Each model is loaded from <models folder>/<name>/model.onnx and tokenizer.json, with its own pooling
(CLS or mean), query prefix and document prefix. The current MiniLM model is run through the same
harness as the baseline. Index caches go in the work dir. Mean embedding time per query and the time
to embed all 282 agents are reported, to judge CPU cost.

Usage: .venv/bin/python benchmarks/experiments/embed_models.py <models folder> <work dir> [minilm folder]
"""
import json, sys, time, pathlib
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import roster  # noqa: E402

MODELS = {  # name: (pooling, query prefix, document prefix)
    'arctic-xs':   ('cls',  'Represent this sentence for searching relevant passages: ', ''),
    'arctic-s':    ('cls',  'Represent this sentence for searching relevant passages: ', ''),
    'minilm-l12':  ('mean', '', ''),
    'gte-small':   ('mean', '', ''),
    'e5-small':    ('mean', 'query: ', 'passage: '),
    'nomic-quant': ('mean', 'search_query: ', 'search_document: '),
}
base = pathlib.Path(sys.argv[1]); work = pathlib.Path(sys.argv[2])
minilm_dir = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path.home() / '.cache/specialist-scout/model'
ROOT = REPO / 'benchmarks' / 'data'
sets = {f: json.load(open(ROOT / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}
wf = json.load(open(ROOT / 'workflows.json'))
cases = [c for f in sets.values() for c in f] + [{'query': s['query'], 'expect': s['expect']} for w in wf for s in w['subtasks']]
roster.bad_model_files = lambda: []   # checksums are checked per download; this harness runs experimental files


def make_runtime(folder, pooling, qp, dp):
    tok = Tokenizer.from_file(str(folder / 'tokenizer.json'))
    tok.enable_truncation(max_length=256)
    tok.enable_padding(pad_id=tok.token_to_id('[PAD]') or 0, pad_token='[PAD]')
    sess = ort.InferenceSession(str(folder / 'model.onnx'), providers=['CPUExecutionProvider'])
    names = {i.name for i in sess.get_inputs()}
    out = sess.get_outputs()[0].name

    def embed(runtime, texts):
        is_query = len(texts) == 1          # the index is built from many texts; a search embeds one query
        texts = [(qp if is_query else dp) + t for t in texts]
        enc = tok.encode_batch(texts)
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
        return v / np.linalg.norm(v, axis=1, keepdims=True)
    return embed


def score(searcher):
    h1 = h3 = 0
    for c in cases:
        ids = [a['id'] for a in searcher.rank(c['query'], limit=8)]
        r = next((k + 1 for k, x in enumerate(ids) if x in c['expect']), None)
        h1 += r == 1; h3 += bool(r and r <= 3)
    return h1, h3


runs = [('MiniLM-L6 (current)', minilm_dir, 'mean', '', '')]
runs += [(n, base / n, *MODELS[n]) for n in MODELS]
n = len(cases)
print(f"{'model':22} {'size MB':>8} {'embed hit@1':>12} {'embed hit@3':>12} {'hybrid hit@1':>13} {'hybrid hit@3':>13} {'ms/query':>9} {'index s':>8}")
for name, folder, pooling, qp, dp in runs:
    embed = make_runtime(folder, pooling, qp, dp)
    roster.embed = embed
    roster.load_runtime = lambda: {'np': np}
    roster.INDEX_PATH = work / f"index-{name.split()[0].lower()}.npz"
    if roster.INDEX_PATH.exists():
        roster.INDEX_PATH.unlink()                  # time a real index build
    t0 = time.perf_counter()
    emb = roster.Searcher('embed')
    index_s = time.perf_counter() - t0
    e1, e3 = score(emb)
    hyb = roster.Searcher('hybrid')
    h1, h3 = score(hyb)
    t0 = time.perf_counter()
    for c in cases:
        embed({}, [c['query']])
    ms = (time.perf_counter() - t0) / n * 1000
    size = (folder / 'model.onnx').stat().st_size / 1e6
    print(f"{name:22} {size:8.0f} {e1:>6}/{n} ({e1/n:4.0%}) {e3:>6}/{n} ({e3/n:4.0%}) {h1:>7}/{n} ({h1/n:4.0%}) {h3:>7}/{n} ({h3/n:4.0%}) {ms:9.1f} {index_s:8.1f}")
