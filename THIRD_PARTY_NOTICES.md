# Third-party notices

This plugin does not contain the third-party components below. It downloads them at the
user's request (see `commands/setup.md`) or, for Python packages, installs them with pip.
The notices are listed so that anyone who redistributes a copy with these components can
meet their licence terms.

## 1. Agency roster (agency-agents)

- Source: https://github.com/msitarzewski/agency-agents
- Licence: MIT
- Copyright: Copyright (c) 2025 AgentLand Contributors
- Use: `/specialist-scout:setup roster` clones it into the plugin data folder, or the plugin reads an existing clone at `~/.agency-agents`. Not included in this repository.

## 2. Embedding model (all-MiniLM-L6-v2)

- Source: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
- Files used: `onnx/model.onnx` (ONNX file) and `tokenizer.json`, both from the upstream repository at a pinned commit (`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`).
- Licence: Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0), stated in the upstream model card.
- Use: `/specialist-scout:setup embeddings` downloads them and checks SHA-256 hashes. Not included in this repository.
- Modifications: none. The files are used as published; the plugin applies mean pooling and normalisation in its own code.

## 3. Python packages

Pinned in `scripts/requirements.lock.txt`. Licences as read from the installed package metadata.

| Package | Version | Licence |
|---|---|---|
| onnxruntime | 1.32.0 | MIT |
| tokenizers | 0.23.3 | Apache-2.0 |
| numpy | 2.5.5 | BSD-3-Clause; bundled parts under 0BSD, MIT, Zlib, CC0-1.0 |
| huggingface_hub | 2.4.0 | Apache-2.0 |
| tqdm | 4.70.1 | MPL-2.0 AND MIT |
| protobuf | 7.36.2 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| typing_extensions | 4.16.0 | PSF-2.0 |
| anyio | 4.16.0 | MIT |
| click | 8.5.1 | BSD-3-Clause |
| filelock | 4.3.0 | MIT |
| flatbuffers | 25.12.19 | Apache-2.0 |
| fsspec | 2026.9.0 | BSD-3-Clause |
| h11 | 0.16.0 | MIT |
| hf-xet | 1.8.0 | Apache-2.0 |
| httpcore2 | 2.16.2 | BSD-3-Clause |
| httpx2 | 2.16.2 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| PyYAML | 6.0.4 | MIT |
| truststore | 0.10.5 | MIT |

Full licence texts are in each package's own distribution. tqdm is licensed under MPL-2.0;
this plugin uses it unmodified.

## 4. Original material

Benchmark queries and labels are original to this project. The plugin's manifest shape
follows the fast-compact plugin (MIT), and its structure follows the plugin-dev documentation
(Apache-2.0). No text from either is reproduced.
