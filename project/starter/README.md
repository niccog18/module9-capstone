# Capstone Starter (STARTER)

This is deliberately minimal — folder structure and skeleton files only. You
decide the models, endpoints, and RAG pipeline for your chosen application.
See `course-content/Architecture Workshop Designing Your System.md` and
`course-content/Module Project AI-Powered Application.md` for what to design
before you fill these files in.

## Setup

```bash
cp .env.example .env
# fill in the TODOs in docker-compose.yml, backend/, and frontend/
docker-compose up --build
```

## Running the services locally (before Dockerizing)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

## Structure

```
project/starter/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── rag_pipeline.py
│   ├── database.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_auth.py
│       ├── test_crud.py
│       └── test_rag.py
├── frontend/
│   ├── Dockerfile
│   ├── app.py
│   ├── api_client.py
│   └── requirements.txt
└── docs/
    └── (your document corpus goes here)
```
