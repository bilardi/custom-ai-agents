# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-11
### 🚀 Features
- Use Ollama's OpenAI-compatible /v1 endpoint for agent tool-calling

### 💼 Other
- Release 0.3.0

## [0.2.0] - 2026-07-11
### 🚀 Features
- Add agent-as-tool engine with coder sub-agent and code validation
- Add reviewer sub-agent with reliable code delegation, progress trace and RAG robustness (agent-as-tool)

### 💼 Other
- Release 0.2.0

## [0.1.0] - 2026-07-06
### 🚀 Features
- Add tool-agent engine on any_agent tinyagent with async engines and prompt loader
- Stream tool-call trace to the IDE behind SHOW_TOOL_TRACE (async engine streaming)
- Ground tool-agent answers on retrieved chunks (nomic embedder, larger chunks, chunk overlap, reindex reset)

### 💼 Other
- Release 0.1.0

## [0.0.1] - 2026-07-04
### 🚀 Features
- Add WebBrowser tool class in app/tools
- Add ChromaDb ag backend and Retriever interface
- Add Router and DeterministicEngine (ENGINE strategy)
- Add FastAPI proxy with engine routing and Ollama pass-through
- Add /v1 endpoints and composition root to proxy
- Add indexing scripts and data skeleton
- Separate embedding model, expose TOP_K/MAX_WORDS/CONTEXT_LENGTH via .env
- Stream tokens from the deterministic engine to the proxy
- Add coding Modelfile and Continue (VS Code) setup

### 💼 Other
- Release 0.0.1

### 📚 Documentation
- Add engine strategy to planned app structure
- Add end-to-end usage and configuration to README
- Add OpenAI-compatible and streaming/generate examples

### ⚙️ Miscellaneous Tasks
- Scaffold app config, tests skeleton and docs
- Add release tagging and changelog (bump-my-version, git-cliff)

[0.3.0]: https://github.com/bilardi/custom-ai-agents/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/bilardi/custom-ai-agents/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/bilardi/custom-ai-agents/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/bilardi/custom-ai-agents/compare/...v0.0.1

