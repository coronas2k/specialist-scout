"""ColBERT encoding for answerai-colbert-small-v1 (Apache-2.0), rebuilt from its onnx_config.json and model card.

Checked against the model card example: the ranking matches, and the scores differ by about one point (int8 file vs the card's full-precision model).
"""
import numpy as np, onnxruntime as ort
from tokenizers import Tokenizer
import string

class ColBERT:
    def __init__(self, folder, model_file='model_int8.onnx', query_len=32, doc_len=300, pad_query_with_mask=True, keep_query_mask_positions=True):
        self.tok = Tokenizer.from_file(f"{folder}/tokenizer.json")
        self.tok.no_padding(); self.tok.no_truncation()
        self.sess = ort.InferenceSession(f"{folder}/{model_file}", providers=['CPUExecutionProvider'])
        self.query_len, self.doc_len = query_len, doc_len
        self.q_id, self.d_id = self.tok.token_to_id('[unused0]'), self.tok.token_to_id('[unused1]')
        self.mask_id = self.tok.token_to_id('[MASK]')
        self.cls_id, self.sep_id = self.tok.token_to_id('[CLS]'), self.tok.token_to_id('[SEP]')
        self.keep_mask_positions = keep_query_mask_positions
        self.punct = {self.tok.token_to_id(t) for t in string.punctuation if self.tok.token_to_id(t) is not None}

    def _run(self, ids, mask):
        feeds = {'input_ids': np.array([ids], dtype=np.int64),
                 'attention_mask': np.array([mask], dtype=np.int64),
                 'token_type_ids': np.zeros((1, len(ids)), dtype=np.int64)}
        out = self.sess.run(['output'], feeds)[0][0]          # (len, 96)
        return out

    def encode_query(self, text):
        body = self.tok.encode(text, add_special_tokens=False).ids[: self.query_len - 4]
        ids = [self.cls_id, self.q_id] + body + [self.sep_id]
        keep = [True] * len(ids)
        pad = self.query_len - len(ids)
        ids = ids + [self.mask_id] * pad
        mask = [1] * len(ids)                               # attend to all query positions
        vecs = self._run(ids, mask)
        return vecs                                          # all 32 query positions, punctuation kept (as in the model card)

    def encode_doc(self, text):
        body = self.tok.encode(text, add_special_tokens=False).ids[: self.doc_len - 3]
        ids = [self.cls_id, self.d_id] + body + [self.sep_id]
        vecs = self._run(ids, [1] * len(ids))
        sel = [i for i, t in enumerate(ids) if t not in self.punct]
        return vecs[sel]

def maxsim(q, d):
    return float((q @ d.T).max(axis=1).sum())
