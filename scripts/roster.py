#!/usr/bin/env python3
"""Search the agency-agents roster without loading it into context.

Usage:
  roster.py search <words...> [--also <phrase>]... [--division d] [--limit n] [--mode hybrid|bm25|embed]

With --also, each phrase is searched too (top 15 each). The request and every phrase are merged by each
specialist's best rank, with ties going to the request, and the top --limit are shown. Use 3 or 4 phrases
written in the words a specialist's job description would use.
  roster.py divisions
  roster.py show <id-or-name>      # print the full path of one agent file
  roster.py verify-model           # check the embedding model files' SHA-256

Modes:
  hybrid  (default) keyword (BM25) score plus embedding similarity, combined
          linearly. Falls back to bm25 if the embedding setup is missing.
  bm25    keyword ranking only. No dependencies beyond the standard library.
  embed   embedding similarity only.

Roster root: $AGENCY_AGENTS_DIR, else the roster installed by /specialist-scout:setup in the
plugin data folder, else ~/.agency-agents. The roster is never downloaded here.
An agent is any .md file inside a division directory (listed in divisions.json)
whose YAML frontmatter has a `name:` key.

Exit codes: 0 ok, 1 not found, 2 bad usage, 3 roster not installed,
4 embedding search unavailable (mode embed only; hybrid falls back to bm25).
"""
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
# Persistent folder for this plugin (survives plugin updates). Outside Claude, fall back to a cache folder.
DATA_DIR = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or (Path.home() / ".cache" / "specialist-scout"))
VENV_PYTHON = Path(os.environ.get("SPECIALIST_SCOUT_VENV") or (DATA_DIR / ".venv")) / "bin" / "python"
MODEL_DIR = DATA_DIR / "model"
INDEX_PATH = DATA_DIR / "index.npz"


def roster_root():
    """The roster checkout, or None if none is installed. Never downloads anything."""
    if os.environ.get("AGENCY_AGENTS_DIR"):
        # An explicit path is taken as given; if it isn't a roster, report that instead of guessing.
        explicit = Path(os.environ["AGENCY_AGENTS_DIR"])
        return explicit if (explicit / "divisions.json").exists() else None
    for candidate in (DATA_DIR / "agency-agents", Path.home() / ".agency-agents"):
        if (candidate / "divisions.json").exists():
            return candidate
    return None


ROOT = roster_root()
# SHA-256 of the files in model/, from sentence-transformers/all-MiniLM-L6-v2 (Apache-2.0) at the
# commit in model/REVISION. model.onnx is the upstream file at onnx/model.onnx.
MODEL_FILES = {
    "model.onnx": "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452",
    "tokenizer.json": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
}
EMBED_MAX_TOKENS = 256
EMBED_BATCH = 32
# Hybrid weight of the embedding similarity against the keyword score (0..1). Flat between 0.5 and 2.0.
EMBED_WEIGHT = 1.0

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "at", "by",
    "with", "from", "as", "is", "are", "be", "it", "this", "that", "my", "our",
    "your", "i", "we", "you", "me", "do", "does", "can", "how", "what", "need",
    "want", "make", "help", "please", "agent", "specialist",
}

# Applied to queries and to documents, so both sides agree on the vocabulary.
PHRASES = [
    (r"front-end", "frontend"),
    (r"back-end", "backend"),
    (r"ci/cd", "cicd devops deployment pipeline"),
    (r"\bseo\b", "seo search engine optimization"),
    (r"pay-per-click|\bppc\b", "ppc paid search google ads"),
    (r"\bui\b", "ui user interface"),
    (r"\bux\b", "ux user experience"),
    (r"\ba/b\b", "ab split test experiment"),
    (r"\bgdpr\b", "gdpr privacy data protection"),
    (r"pen[ -]?test(ing)?", "penetration testing pentest"),
    (r"\brag\b", "rag retrieval augmented generation"),
    (r"\bwp\b|wordpress", "wordpress"),
    (r"\bsre\b", "sre reliability"),
    (r"\bready\b|readiness", "ready readiness"),
    (r"\bfaster\b|\bslow(er)?\b|\bspeed\b|\bloads?\b|\bloading\b", "performance speed"),
    (r"projections?|forecasts?|forecasting", "forecast forecasting projection"),
    (r"\bdocker\b|containers?|kubernetes|\bk8s\b", "container docker kubernetes cloud infrastructure"),
    (r"\bokrs?\b", "okr objectives key results planning"),
    (r"\broadmaps?\b", "roadmap planning"),
    (r"mockups?", "mockup wireframe design"),
]

# Field weight = how many times the field's terms count, approximating boosts.
FIELD_WEIGHTS = {"name": 3, "id": 2, "description": 2, "division": 1, "body": 0.5}
BODY_CHARS = 8000
K1, B = 1.2, 0.75
# Added to a document's BM25 score when every term of its name appears in the query.
NAME_MATCH_BONUS = 5.0
TOKEN = re.compile(r"[a-z0-9]+")


# --- roster and keyword search -------------------------------------------------

def stem(tok):
    """Strip common suffixes (up to two passes). Applied the same way to queries and docs."""
    for _ in range(2):
        for suf in ("s", "ing", "ed", "er"):
            if tok.endswith(suf) and not tok.endswith("ss") and len(tok) - len(suf) >= 4:
                tok = tok[: -len(suf)]
                break
        else:
            break
    return tok


def terms(text):
    text = (text or "").lower()
    for pattern, replacement in PHRASES:
        text = re.sub(pattern, replacement, text)
    return [stem(t) for t in TOKEN.findall(text) if t not in STOPWORDS and len(t) > 1]


def divisions():
    data = json.loads((ROOT / "divisions.json").read_text())
    return list(data["divisions"].keys())


def parse_frontmatter(lines):
    """Flat `key: value` pairs, including folded (>) and literal (|) blocks."""
    meta, key, block = {}, None, None
    for line in lines:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m and not line.startswith((" ", "\t")):
            key, val = m.group(1), m.group(2).strip()
            if val in (">", ">-", "|", "|-", ">+", "|+"):
                block, meta[key] = [], ""
            else:
                block = None
                meta[key] = val.strip("\"'")
        elif block is not None and key:
            block.append(line.strip())
            meta[key] = " ".join(x for x in block if x)
    return meta


def read_agent(path):
    """Return (frontmatter dict, body text). Empty if the file has no frontmatter."""
    lines = path.read_text(errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ""
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, ""
    return parse_frontmatter(lines[1:end]), "\n".join(lines[end + 1:])


def agents(only_division=None):
    for div in divisions():
        if only_division and div != only_division:
            continue
        for path in sorted((ROOT / div).rglob("*.md")):
            meta, body = read_agent(path)
            if meta.get("name"):
                yield {
                    "id": path.stem,
                    "division": div,
                    "name": meta["name"],
                    "description": meta.get("description", ""),
                    "vibe": meta.get("vibe", ""),
                    "body": body,
                    "path": str(path),
                    "mtime": path.stat().st_mtime_ns,
                }


def build_index(pool):
    """Term frequencies (weighted by field), document lengths and document frequencies."""
    docs = []
    df = Counter()
    for agent in pool:
        tf = Counter()
        for field, weight in FIELD_WEIGHTS.items():
            if field == "body":
                text = agent["body"][:BODY_CHARS]
            elif field == "id":
                text = agent["id"].replace("-", " ")
            else:
                text = agent.get(field, "")
            for t in terms(text):
                tf[t] += weight
        length = sum(tf.values())
        docs.append((agent, tf, length))
        df.update(tf.keys())
    avg = (sum(length for _, _, length in docs) / len(docs)) if docs else 1.0
    return docs, df, len(docs), avg


def bm25(query_terms, tf, length, df, n, avg):
    score = 0.0
    for t in set(query_terms):
        f = tf.get(t, 0)
        if not f:
            continue
        idf = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1)
        score += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * length / avg))
    return score


# --- embeddings (optional) -----------------------------------------------------

class EmbeddingUnavailable(Exception):
    pass


def load_runtime():
    """Load the ONNX model and tokenizer. Raises EmbeddingUnavailable if not set up."""
    if not (MODEL_DIR / "model.onnx").exists():
        raise EmbeddingUnavailable("embedding model not downloaded; run setup.sh")
    try:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
    except ImportError as exc:
        raise EmbeddingUnavailable(f"missing package {exc.name}; run setup.sh") from exc
    tok = Tokenizer.from_file(str(MODEL_DIR / "tokenizer.json"))
    tok.enable_truncation(max_length=EMBED_MAX_TOKENS)
    # Pad each batch to its longest text, not the 128 the shipped config asks for.
    tok.enable_padding(pad_id=tok.token_to_id("[PAD]"), pad_token="[PAD]")
    sess = ort.InferenceSession(str(MODEL_DIR / "model.onnx"), providers=["CPUExecutionProvider"])
    return {"np": np, "tok": tok, "sess": sess}


def embed(runtime, texts):
    """L2-normalised sentence embeddings, one row per text.

    Same pipeline as the upstream sentence-transformers model: the ONNX graph returns
    token vectors (last_hidden_state), then mean pooling over non-padding tokens, then L2 normalisation.
    """
    np, tok, sess = runtime["np"], runtime["tok"], runtime["sess"]
    chunks = []
    for start in range(0, len(texts), EMBED_BATCH):
        enc = tok.encode_batch(texts[start:start + EMBED_BATCH])
        feeds = {
            "input_ids": np.array([e.ids for e in enc], dtype=np.int64),
            "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64),
            "token_type_ids": np.array([e.type_ids for e in enc], dtype=np.int64),
        }
        hidden = sess.run(["last_hidden_state"], feeds)[0]
        mask = feeds["attention_mask"][..., None].astype(np.float32)
        chunks.append((hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None))
    vectors = np.concatenate(chunks)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def embed_text(agent):
    return f"{agent['name']}. {agent['description']}. {agent['vibe']}"


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def bad_model_files():
    return [name for name, want in MODEL_FILES.items()
            if not (MODEL_DIR / name).exists() or file_sha256(MODEL_DIR / name) != want]


def vector_index(runtime, pool):
    """Embed the whole roster once; reuse the saved index until an agent file or the model changes."""
    np = runtime["np"]
    h = hashlib.sha256(MODEL_FILES["model.onnx"].encode())
    for a in pool:
        h.update(f"{a['id']}|{a['mtime']}|{embed_text(a)}".encode())
    stamp = h.hexdigest()
    if INDEX_PATH.exists():
        data = np.load(INDEX_PATH)
        if str(data["stamp"]) == stamp:
            return [str(i) for i in data["ids"]], data["vectors"]
    bad = bad_model_files()
    if bad:
        raise EmbeddingUnavailable(f"model files fail their checksum: {bad}; run setup.sh")
    ids = [a["id"] for a in pool]
    vectors = embed(runtime, [embed_text(a) for a in pool])
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(INDEX_PATH, stamp=np.array(stamp), ids=np.array(ids), vectors=vectors)
    return ids, vectors


# --- ranking -------------------------------------------------------------------

class Searcher:
    def __init__(self, mode="hybrid"):
        self.pool = list(agents())
        self.docs, self.df, self.n, self.avg = build_index(self.pool)
        self.mode = mode
        self.runtime = None
        if mode in ("hybrid", "embed"):
            try:
                self.runtime = load_runtime()
                self.ids, self.vectors = vector_index(self.runtime, self.pool)
                self.row = {agent_id: k for k, agent_id in enumerate(self.ids)}
            except EmbeddingUnavailable as exc:
                if mode == "embed":
                    raise
                print(f"note: keyword search only ({exc})", file=sys.stderr)
                self.mode = "bm25"

    def rank(self, query, division=None, limit=8):
        query_terms = terms(query)
        candidates = [i for i, a in enumerate(self.pool) if not division or a["division"] == division]

        bm = {}
        if self.mode in ("bm25", "hybrid") and query_terms:
            qset = set(query_terms)
            for i in candidates:
                agent, tf, length = self.docs[i]
                s = bm25(query_terms, tf, length, self.df, self.n, self.avg)
                name_terms = set(terms(agent["name"]))
                if name_terms and name_terms <= qset:
                    s += NAME_MATCH_BONUS
                if s > 0:
                    bm[i] = s

        emb = {}
        if self.mode in ("hybrid", "embed"):
            query_vec = embed(self.runtime, [query])[0]
            sims = self.vectors @ query_vec
            for i in candidates:
                emb[i] = float(sims[self.row[self.pool[i]["id"]]])

        def key(i):
            return (self.pool[i]["division"], self.pool[i]["id"])

        if self.mode == "bm25":
            order = sorted(bm, key=lambda i: (-bm[i], *key(i)))
        elif self.mode == "embed":
            order = sorted(emb, key=lambda i: (-emb[i], *key(i)))
        else:
            # Keyword score scaled to 0..1 by the best match, plus the embedding similarity.
            top_bm = max(bm.values()) if bm else 1.0
            fused = {}
            for i in candidates:
                fused[i] = (bm.get(i, 0.0) / top_bm) + EMBED_WEIGHT * max(0.0, emb[i])
            order = sorted((i for i in fused if fused[i] > 0), key=lambda i: (-fused[i], *key(i)))
        return [self.pool[i] for i in order[:limit]]


def rank_merged(searcher, query, phrases, division=None, limit=8, depth=15):
    """Merge the request and its rewritten phrases by best rank (ties to the request).

    This is the method measured in the fresh6 pipeline test (benchmarks/experiments/pipeline_eval.py).
    Each query is searched to depth 15, a specialist keeps its best (rank, is_phrase) pair, and the
    top `limit` pairs are returned in that order.
    """
    queries = [query] + [p for p in phrases if p and p.strip()]
    best = {}
    for k, q in enumerate(queries):
        for r, agent in enumerate(searcher.rank(q, division, depth), start=1):
            cand = (r, 0 if k == 0 else 1)
            key = agent["id"]
            if key not in best or cand < best[key][0]:
                best[key] = (cand, agent)
    return [agent for _, agent in sorted(best.values(), key=lambda x: x[0])[:limit]]


def format_results(results):
    lines = []
    for a in results:
        desc = a["description"]
        desc = desc if len(desc) <= 160 else desc[:157] + "..."
        lines.append(f"{a['id']}  [{a['division']}]  {a['name']}\n    {desc}")
    return "\n".join(lines)


# --- command line ----------------------------------------------------------------

def ensure_venv():
    """Re-run this script with the skill's virtualenv, if it exists."""
    if os.environ.get("SPECIALIST_SCOUT_NO_REEXEC") or not VENV_PYTHON.exists():
        return
    if os.path.abspath(sys.executable) == str(VENV_PYTHON.absolute()):
        return
    os.environ["SPECIALIST_SCOUT_NO_REEXEC"] = "1"
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]

    if cmd == "verify-model":
        bad = bad_model_files()
        print("model files OK" if not bad else f"checksum mismatch or missing: {bad}")
        return 0 if not bad else 1

    if ROOT is None:
        print("Agency roster not found. Run /specialist-scout:setup roster, or set AGENCY_AGENTS_DIR.", file=sys.stderr)
        return 3

    if cmd == "divisions":
        for div in divisions():
            print(f"{div}\t{sum(1 for _ in agents(div))}")
        return 0

    if cmd == "show":
        if not rest:
            print("show needs an agent id", file=sys.stderr)
            return 2
        want = rest[0].lower()
        for a in agents():
            if want in (a["id"].lower(), a["name"].lower()):
                print(a["path"])
                return 0
        print(f"no agent with id or name '{rest[0]}'", file=sys.stderr)
        return 1

    if cmd == "search":
        division, limit, mode, words, alsos = None, 8, "hybrid", [], []
        i = 0
        while i < len(rest):
            if rest[i] == "--also" and i + 1 < len(rest):
                alsos.append(rest[i + 1])
                i += 2
            elif rest[i] == "--division" and i + 1 < len(rest):
                division, i = rest[i + 1].lower(), i + 2
            elif rest[i] == "--limit" and i + 1 < len(rest):
                limit, i = int(rest[i + 1]), i + 2
            elif rest[i] == "--mode" and i + 1 < len(rest):
                mode, i = rest[i + 1], i + 2
            else:
                words.append(rest[i])
                i += 1
        query = " ".join(words).strip()
        if not query:
            print("no matches; try broader words or `divisions`")
            return 0
        try:
            searcher = Searcher(mode)
        except EmbeddingUnavailable as exc:
            print(f"embedding search unavailable: {exc}", file=sys.stderr)
            return 4
        if alsos:
            results = rank_merged(searcher, query, alsos, division, limit)
        else:
            results = searcher.rank(query, division, limit)
        print(format_results(results) or "no matches; try broader words or `divisions`")
        return 0

    print(f"unknown command '{cmd}'", file=sys.stderr)
    return 2


if __name__ == "__main__":
    ensure_venv()
    sys.exit(main(sys.argv[1:]))
