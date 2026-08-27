# Module 9: Capstone — AI-Powered Application — Starter Kit

## Quick Setup

### Option A: Clone with Git

```bash
git clone <repo-url>
cd module-09-capstone
```

### Option B: Download ZIP (no Git required)

1. Go to this repo on GitHub
2. Click the green **Code** button
3. Click **Download ZIP**
4. Unzip the downloaded file and open the folder

---

## Module Format

Module 9 has no lessons, exercises, or a solutions folder. It's a **two-week guided workshop** — you design and build a portfolio-ready AI-powered application of your own choosing, using everything from Modules 1–8.

| Day   | Session                         | Deliverable                                            |
| ----- | ------------------------------- | ------------------------------------------------------ |
| 1     | Capstone Kickoff                | Project proposal                                       |
| 2     | Architecture Workshop           | Architecture diagram + database schema + endpoint list |
| 3–7   | Building Phase                  | Independent work, daily stand-ups                      |
| 8     | Mid-Capstone Review             | Demo "what you have"                                   |
| 9     | Docker + Compose                | `docker-compose up` runs the full stack                |
| 10–11 | Polish, Documentation & Testing | 5+ passing tests, README, code quality                 |
| 12    | Presentation Prep               | Practice the 5-minute demo                             |

See `course-content/` for the full session guides and grading rubric.

---

## Required Components

Every capstone must include:

- FastAPI backend with at least 3 endpoints
- SQLAlchemy database with at least 2 related tables
- Pydantic validation on all endpoints
- JWT authentication (register, login, protected routes)
- RAG pipeline (ChromaDB + Ollama or an API-based LLM)
- Streamlit frontend
- Docker Compose configuration (entire app runs with `docker-compose up`)
- At least 5 passing tests (pytest + `TestClient`)
- README with setup instructions, architecture diagram, and usage guide
- `requirements.txt` (or per-service requirements files)

---

## Module Project

The project is your choice of **AI-powered application** — Study Buddy, Recipe Assistant, Job Posting Analyzer, Documentation Helper, Personal Knowledge Base, or your own idea. See `course-content/Module Project AI-Powered Application.md` for the full brief, project ideas, and grading rubric.

### Starter

The starter is intentionally minimal: folder structure, a `docker-compose.yml` skeleton with TODO comments, `.env.example`, and `.gitignore`. You build everything else — this tests independence, not tutorial-following.

```bash
cd project/starter
cp .env.example .env

# Fill in the TODOs in docker-compose.yml, then:
docker-compose up --build
```

The starter includes:

- `backend/` — empty FastAPI project skeleton (`main.py`, `models.py`, `schemas.py`, `auth.py`, `rag_pipeline.py`, `database.py`, `tests/`)
- `frontend/` — empty Streamlit project skeleton (`app.py`, `api_client.py`)
- `docs/` — drop your RAG document corpus here
- `docker-compose.yml` — service stubs to complete (backend, frontend, and optionally chromadb/ollama)
- `.env.example` — placeholders for the environment variables your app will need
- `.gitignore` — standard Python/Docker ignores, including `.env`

Rename `project/starter/` (or copy it out of this repo) to start your own project — it is not meant to be built up in place across the whole class.

---

## Need Help?

- Re-read the session guide in `course-content/` for that day
- Bring questions to daily stand-ups and instructor check-ins
- Post in the course discussion board
