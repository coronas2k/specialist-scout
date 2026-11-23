"""Compare the text each specialist is embedded with (current MiniLM model). Scores embed and hybrid search on all query sets. Index caches go in the work dir.

Usage (from the plugin folder, with the venv that has the embedding packages):
  .venv-or-plugin-data/bin/python benchmarks/experiments/text_variants.py <work dir>
The work dir holds the index caches and, for bge_compare, a bge/ folder with model.onnx and tokenizer.json
from BAAI/bge-small-en-v1.5 (MIT), pinned at commit 5c38ec7c.
"""
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import roster
EXP = pathlib.Path(sys.argv[1])
ROOT = REPO / 'benchmarks' / 'data'
sets = {f: json.load(open(ROOT / f)) for f in ['eval.json', 'holdout.json', 'holdout2.json']}
wf = json.load(open(ROOT / 'workflows.json'))
sets['workflows.json'] = [{'query': s['query'], 'expect': s['expect']} for w in wf for s in w['subtasks']]

def base_text(a): return f"{a['name']}. {a['description']}. {a['vibe']}"
def nd_text(a): return f"{a['name']}. {a['description']}"
def body_text(n):
    def f(a):
        body = ' '.join(a['body'].split())[:n]
        return f"{a['name']}. {a['description']}. {a['vibe']}. {body}"
    return f
variants = {'base': base_text, 'name+description': nd_text, 'body600': body_text(600), 'body1200': body_text(1200)}

def score(s, cases):
    h1 = h3 = 0
    for c in cases:
        ids = [a['id'] for a in s.rank(c['query'], limit=8)]
        r = next((k + 1 for k, x in enumerate(ids) if x in c['expect']), None)
        h1 += r == 1; h3 += bool(r and r <= 3)
    return h1, h3, len(cases)

for name, fn in variants.items():
    roster.embed_text = fn
    roster.INDEX_PATH = EXP / f"index-{name.replace('+','_')}.npz"
    row = []
    for mode in ['embed', 'hybrid']:
        s = roster.Searcher(mode)
        tot = [0, 0, 0]
        for f, cases in sets.items():
            a, b, n = score(s, cases)
            tot = [tot[0] + a, tot[1] + b, tot[2] + n]
            row.append(f"{mode}:{f.split('.')[0][:6]} {b}/{n}")
        row.append(f"{mode} ALL hit@1 {tot[0]}/{tot[2]} hit@3 {tot[1]}/{tot[2]}")
    print(f"{name:17} " + ' | '.join(row[-2:]))
