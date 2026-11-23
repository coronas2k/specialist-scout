"""Compare the current MiniLM embeddings with bge-small-en-v1.5 (CLS pooling), with and without the query prefix, on all query sets.

Usage (from the plugin folder, with the venv that has the embedding packages):
  .venv-or-plugin-data/bin/python benchmarks/experiments/bge_compare.py <work dir>
The work dir holds the index caches and, for bge_compare, a bge/ folder with model.onnx and tokenizer.json
from BAAI/bge-small-en-v1.5 (MIT), pinned at commit 5c38ec7c.
"""
import json, sys, pathlib
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer
REPO = pathlib.Path(__file__).resolve().parents[2]
EXP = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(REPO / 'scripts'))
import roster
ROOT = REPO / 'benchmarks' / 'data'
sets = {f: json.load(open(ROOT / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}
wf = json.load(open(ROOT / 'workflows.json'))
sets['workflows.json'] = [{'query': s['query'], 'expect': s['expect']} for w in wf for s in w['subtasks']]

BGE = EXP / 'bge'
tok = Tokenizer.from_file(str(BGE / 'tokenizer.json'))
tok.enable_truncation(max_length=512)
tok.enable_padding(pad_id=tok.token_to_id('[PAD]'), pad_token='[PAD]')
sess = ort.InferenceSession(str(BGE / 'model.onnx'), providers=['CPUExecutionProvider'])
PREFIX = 'Represent this sentence for searching relevant passages: '
state = {'prefix': False}
orig_embed, orig_load = roster.embed, roster.load_runtime

def bge_runtime():
    return {'np': np, 'tok': tok, 'sess': sess}

def bge_embed(runtime, texts):
    if state['prefix'] and len(texts) == 1:       # a single text here is a search query
        texts = [PREFIX + t for t in texts]
    chunks = []
    for start in range(0, len(texts), 32):
        enc = tok.encode_batch(texts[start:start + 32])
        feeds = {'input_ids': np.array([e.ids for e in enc], dtype=np.int64),
                 'attention_mask': np.array([e.attention_mask for e in enc], dtype=np.int64),
                 'token_type_ids': np.array([e.type_ids for e in enc], dtype=np.int64)}
        hidden = sess.run(['last_hidden_state'], feeds)[0]
        chunks.append(hidden[:, 0, :])               # CLS pooling
    v = np.concatenate(chunks)
    return v / np.linalg.norm(v, axis=1, keepdims=True)

def score(s, cases):
    h1 = h3 = 0
    for c in cases:
        ids = [a['id'] for a in s.rank(c['query'], limit=8)]
        r = next((k + 1 for k, x in enumerate(ids) if x in c['expect']), None)
        h1 += r == 1; h3 += bool(r and r <= 3)
    return h1, h3, len(cases)

variants = [('minilm (current)', orig_load, orig_embed, False), ('bge-small', bge_runtime, bge_embed, False), ('bge-small + query prefix', bge_runtime, bge_embed, True)]
for name, load, emb, prefix in variants:
    roster.load_runtime, roster.embed = load, emb
    state['prefix'] = prefix
    roster.INDEX_PATH = EXP / ('index-' + name.split()[0].replace('(', '') + ('-prefix' if prefix else '') + '.npz')
    for mode in ['embed', 'hybrid']:
        s = roster.Searcher(mode)
        tot = [0, 0, 0]
        per = []
        for f, cases in sets.items():
            a, b, n = score(s, cases)
            tot = [tot[0] + a, tot[1] + b, tot[2] + n]
            per.append(f"{b}/{n}")
        print(f"{name:24} {mode:7} hit@1 {tot[0]}/{tot[2]} ({tot[0]/tot[2]:.0%})  hit@3 {tot[1]}/{tot[2]} ({tot[1]/tot[2]:.0%})   by set hit@3: {' '.join(per)}")
