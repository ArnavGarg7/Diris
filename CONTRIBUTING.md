# Contributing & Development Conventions

Project conventions for DIRIS. We build **milestone by milestone** (see
[ROADMAP.md](ROADMAP.md)); the system must work after every milestone.

## Environment setup

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# Git Bash:            source .venv/Scripts/activate
pip install -r requirements-dev.txt      # runtime deps + pytest
cp .env.example .env                      # then paste your ANTHROPIC_API_KEY
```

## Running tests

```bash
pytest                 # runs the whole suite (offline — no API key needed)
pytest tests/test_graph.py -v
```

The current suite is intentionally **offline**: it exercises the chunker, graph,
vector store, and persistence without calling any external API. Keep it that way
— tests that need the LLM belong behind an explicit marker/opt-in so the core
suite stays fast and deterministic.

## Git workflow

- **One branch per milestone.** Branch name: `feat/mN-short-name` (e.g. `feat/m1-auth`).
- **Small, logical commits** — never one giant commit spanning multiple milestones.
- Open work off `main`; merge a milestone only when its Definition of Done is met.

### Commit message style — Conventional Commits

```
<type>(<scope>): <summary>
```

Types we use: `feat`, `fix`, `test`, `docs`, `chore`, `refactor`.
Examples:

```
feat(auth): add user registration and JWT login
test(graph): cover entity dedupe and neighborhood traversal
chore(repo): add .gitignore and pytest config
docs(roadmap): pull MySQL forward into M1
```

## Definition of Done (every milestone)

1. The feature works.
2. Existing functionality still works (tests pass).
3. Important failure cases are handled.
4. The implementation is documented.
5. The acceptance criteria in ROADMAP.md are satisfied.
6. The change is committed on its milestone branch.

## Hard rules

- **Never commit secrets** (`.env`) or generated state (`data/store/`) — both are gitignored.
- No LangChain unless explicitly approved.
- No building ahead into future milestones ("scope creep").
- Type hints on new code; handle errors explicitly; keep DB access out of route handlers.
