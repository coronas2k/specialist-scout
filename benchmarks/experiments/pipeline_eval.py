"""End-to-end pipeline test (fresh6), pre-registered in benchmarks/results/PREREG-pipeline.md.

Phases:
  lists   build arm B candidate lists: the original request plus four rewriter phrases, each searched with the
          plugin's hybrid search (top 15), merged by each specialist's best rank (ties to the original request),
          top 8 kept. Writes armB_batch{1..4}.json (no labels).
  score   score arm A and arm B picks against fresh6 labels, with paired bootstrap and the decision rule.

Inputs (scratch folder, passed as <work dir>): queries_all.json, armA_batch*.json, picks_armA_batch*.json,
rewrites_batch*.json, picks_armB_batch*.json.
Usage: CLAUDE_PLUGIN_DATA=<plugin data> <plugin venv>/bin/python benchmarks/experiments/pipeline_eval.py <phase> <work dir>
"""
import sys, json, pathlib, math
import numpy as np
REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
import roster  # noqa: E402

phase, work = sys.argv[1], pathlib.Path(sys.argv[2])
f6 = json.loads((REPO / 'benchmarks' / 'data' / 'fresh6.json').read_text(encoding='utf-8'))
DOUBTFUL = {28, 45, 51, 60, 90}          # fixed 1-based numbers from PREREG-pipeline.md

def batches(prefix):
    out = {}
    for b in range(1, 5):
        p = work / f'{prefix}{b}.json'
        if p.exists():
            out.update(json.loads(p.read_text()) if prefix.startswith('picks') else {str(x['idx']): x for x in json.loads(p.read_text())})
    return out

if phase == 'lists':
    S = roster.Searcher('hybrid')
    rw = {}
    for b in range(1, 5):
        rw.update(json.loads((work / f'rewrites_batch{b}.json').read_text()))
    assert len(rw) == 100, f'expected 100 rewrites, got {len(rw)}'
    def short(a): return ' '.join(a['description'].split())[:160]
    lists = []
    for i, q in enumerate(f6):
        phrases = [q['query']] + rw[str(i)][:4]
        best = {}
        for k, ph in enumerate(phrases):
            ranked = S.rank(ph, limit=15)
            for r, a in enumerate(ranked):
                key = a['id']
                cand = (r + 1, 0 if k == 0 else 1)     # ties to the original request
                if key not in best or cand < best[key][0]:
                    best[key] = (cand, a)
        top = sorted(best.values(), key=lambda x: x[0])[:8]
        lists.append({'idx': i, 'query': q['query'], 'candidates': [
            {'id': a['id'], 'name': a['name'], 'description': short(a)} for _, a in top]})
    for b in range(4):
        (work / f'armB_batch{b+1}.json').write_text(json.dumps(lists[b*25:(b+1)*25], indent=1, ensure_ascii=False))
    print('arm B lists written for 100 requests')

elif phase == 'score':
    by = {a['id']: a for a in roster.agents()}
    picks_a = batches('picks_armA_batch')
    picks_b = batches('picks_armB_batch')
    cand_a = batches('armA_batch')
    cand_b = batches('armB_batch')
    def correct(picks, i):
        pick = picks.get(str(i))
        return pick is not None and pick != 'NONE' and pick in f6[i]['expect']
    def shortlist_hit(cands, i):
        return any(c['id'] in f6[i]['expect'] for c in cands[str(i)]['candidates'])
    n = len(f6)
    A = np.array([correct(picks_a, i) for i in range(n)], float)
    B = np.array([correct(picks_b, i) for i in range(n)], float)
    RA = np.array([shortlist_hit(cand_a, i) for i in range(n)], float)
    RB = np.array([shortlist_hit(cand_b, i) for i in range(n)], float)
    invalid = {'A': sum(1 for i in range(n) if picks_a.get(str(i)) not in (None, 'NONE') and picks_a.get(str(i)) not in by),
               'B': sum(1 for i in range(n) if picks_b.get(str(i)) not in (None, 'NONE') and picks_b.get(str(i)) not in by)}
    WORD = __import__('re').compile(r'[a-z]{3,}')
    cw = lambda t: {w for w in WORD.findall(t.lower()) if w not in roster.STOPWORDS}
    overlap = np.array([any(cw(by[e]['name']) & cw(q['query']) for e in q['expect'] if e in by) for q in f6])
    doubtful_mask = np.array([(i + 1) not in DOUBTFUL for i in range(n)])
    def boot(d, seed=1):
        rng = np.random.default_rng(seed)
        b = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(10000)])
        return np.percentile(b, [2.5, 97.5])
    def block(label, a, b, sel):
        d = (b - a)[sel]
        lo, hi = boot(d)
        print(f"{label:34} A {a[sel].mean():.2f}  B {b[sel].mean():.2f}  diff {d.mean():+.3f} [{lo:+.3f}, {hi:+.3f}] (n={int(sel.sum())})")
        return d.mean(), lo, hi
    all_ = np.ones(n, bool)
    print(f"invalid picks: arm A {invalid['A']}, arm B {invalid['B']}")
    print(f"recall@8 of the shortlist the picker sees: A {RA.mean():.2f}, B {RB.mean():.2f}")
    print(f"end-to-end pick accuracy:")
    block('all 100', A, B, all_)
    block('plain stratum', A, B, ~overlap)
    block('name-overlap stratum', A, B, overlap)
    print('sensitivity without the five doubtful labels:')
    block('without doubtful', A, B, doubtful_mask)
    d, lo, hi = block('primary (all 100)', A, B, all_)
    plain_d = (B - A)[~overlap].mean()
    rule1 = lo > 0; rule2 = RB.mean() >= RA.mean(); rule3 = plain_d >= 0
    print(f"rule 1 (interval lower bound above zero): {rule1}")
    print(f"rule 2 (recall@8, B at least A): {rule2}")
    print(f"rule 3 (plain stratum, B minus A non-negative): {rule3}")
    if rule1 and rule2 and rule3:
        print('DECISION: adoption candidate (needs approval; the skill instructions would change)')
    else:
        print(f"DECISION: not adopted; {'not supported' if hi < 0.06 else 'inconclusive'} (upper bound {hi:+.3f})")
