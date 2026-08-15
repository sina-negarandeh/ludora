# Ludora

Ludora is an end-to-end Machine Learning web application built to serve intelligent, multi-algorithmic board game recommendations. Built on the expansive BoardGameGeek dataset, it showcases a scalable Python API paired with a dynamic, highly-polished React frontend.

The system is designed to demonstrate various modern recommendation system architectures, transitioning smoothly from simple popularity baselines to complex graph-based and latent factor models.

## Architecture & Features

The system bridges complex backend data science with a beautiful, responsive frontend UI.

### 1. The ML Backend (Data & Algorithms)
The backend pipeline ingests raw BGG datasets and exposes multiple recommendation algorithms, allowing for real-time comparative analysis of recommendation performance (Coverage vs. Intra-List Diversity). 

**Recommendation Models Supported:**
- **Popularity-Based:** Fast baseline model using total ratings and rank.
- **Content-Based Filtering (NLP):** 
  - `TF-IDF` Vectorization over game mechanics and themes.
  - Semantic Embeddings using `sentence-transformers` for deep contextual similarity.
- **Collaborative Filtering:**
  - Item-Item Cosine Similarity.
  - Matrix Factorization (`scikit-surprise` SVD).
  - Alternating Least Squares (ALS) via `implicit`.
- **Graph-Based Systems:**
  - Graph Jaccard indexing via `networkx`.
  - Node2Vec (DeepWalk) semantic graph embeddings.
- **Hybrid System:** Weighted ensemble algorithms providing a balanced, highly diverse output.

### 2. The Frontend (Dynamic UI/UX)
The UI is a React Single Page Application that feels premium, highly interactive, and data-rich.
- **"You Are Here" Distribution Curves:** Pre-computes and perfectly renders Gaussian density curves via SVG mathematical paths to show users *exactly* where a game sits relative to its peers on metrics like Complexity, Playtime, and Age.
- **Data Visualization:** Interactive 10-bar histograms for 0.5-increment score distributions, complete with hover tooltips and dynamic gauge arcs for "Recommended" percentages.
- **Glassmorphism & Polish:** Sleek aesthetic leveraging TailwindCSS, strict geometric baseline alignment, and fluid CSS transitions.

## Technology Stack

- **Python 3.10+**
- **Backend Framework**: FastAPI, Uvicorn
- **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic, `pgvector`
- **Data Science & ML**: Pandas, Scikit-Learn, Sentence-Transformers, NetworkX, Node2Vec, Implicit, Scikit-Surprise
- **Frontend Framework**: React 19, Vite, TypeScript
- **State Management & Data Fetching**: React Router, TanStack React Query, Axios
- **Styling**: Tailwind CSS, Heroicons
- **Containerization**: Docker Compose

## Project Structure

```text
.
├── backend/                  # FastAPI application and ML pipelines
│   ├── alembic/              # Database migration scripts
│   ├── app/                  # FastAPI application code
│   │   ├── api/              # API routers and endpoints
│   │   ├── core/             # Configuration and database setup
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic validation schemas
│   │   └── services/         # ML models and recommendation logic
│   ├── evaluation/           # Scripts for evaluating RecSys metrics (Coverage, ILD)
│   ├── scripts/              # Data generation and pipeline scripts
│   ├── Dockerfile            # Backend container definition
│   └── pyproject.toml        # Python project dependencies (Hatch)
├── frontend/                 # React SPA
│   ├── public/               # Static assets (JSON distributions)
│   ├── src/                  # UI source code
│   │   ├── api/              # Axios hooks
│   │   ├── components/       # Reusable UI components (GameCard, etc)
│   │   └── pages/            # View components (GameDetail, etc)
│   └── package.json          # Node dependencies
├── data/                     # Raw datasets (BGG CSVs)
├── infrastructure/           # Deployment configs
└── docker-compose.yml        # Multi-container local orchestration
```

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js (if running frontend locally)
- Python 3.10+ (if running backend locally via `uv`)

### Running the Application

To spin up the entire application (PostgreSQL, FastAPI Backend, and Vite Frontend) in development mode with live-reloading:

```bash
docker-compose up -d
```

### Accessing the Services
- **Frontend UI**: http://localhost:5173
- **FastAPI Swagger Docs**: http://localhost:8000/docs
- **PostgreSQL Database**: localhost:5432

### Local Development (Without Docker)

**Backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Data Pipeline

To recalculate the SVG distributions and rating aggregations for the frontend UI, run the data generation scripts:
```bash
cd backend
uv run python scripts/generate_distributions.py
uv run python scripts/populate_rating_distribution.py
```
