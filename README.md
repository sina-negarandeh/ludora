# Ludora

Ludora is an end-to-end Machine Learning web application built to serve intelligent, multi-algorithmic board game recommendations alongside a powerful Conversational AI Assistant. Built on the expansive BoardGameGeek dataset, it showcases a scalable Python API paired with a dynamic, highly-polished React frontend and local AI execution.

## Comprehensive Feature List

Ludora bridges complex backend data science, locally-hosted LLMs, and zero-shot classifiers with a beautiful, responsive frontend UI to create the ultimate board game discovery platform.

### 1. Game Browsing & Discovery
- **View and Browse Board Games:** A highly-polished, responsive catalog displaying thousands of board games in a grid view, designed for rapid scanning.
- **Dedicated Game Detail Pages:** Deep-dive pages for every single game featuring immersive headers, structured data, and rich visual layouts.
- **Advanced Search Engine:** 
  - **Lexical Search:** Fast, exact-keyword matching for specific titles or designers.
  - **Semantic Search:** Vector-embedding based search allowing users to search by "vibe" or descriptive phrases (e.g., "A tense sci-fi trading game").
  - **Hybrid Search:** Intelligently combines lexical precision and semantic recall to deliver the most relevant results possible.
- **Comprehensive Filters:** Robust filtering capabilities allowing users to narrow down games by exact Player Count, Play Time, Complexity Weight, Year, Categories, and Mechanics.
- **Sorting Options:** Sort the vast catalog by Rank, Average Rating, Total Ratings, Year Published, or Complexity.

### 2. Rich Metadata & UI Design
- **Premium Aesthetics:** Sleek, glassmorphic design language leveraging TailwindCSS. The "All Games" feed and individual Game pages feature strict geometric baseline alignment, fluid CSS transitions, and an elegant color palette.
- **Extensive Metadata Sections:** Every game page neatly organizes a massive amount of data:
  - Title & Year Published
  - High-level taxonomy: Categories, Themes, and Mechanics
  - Full "About the Game" rich-text descriptions
  - Core metrics: Player Count (Min-Max), Playtime (Mfg & Community), Age, and Complexity Weight
  - Credits: Designers, Artists, and Publishers
- **Ranking Badges:** Distinctive visual trophy badges indicating a game's official rank across the entire database.

### 3. Statistics, Graphs & Visualizations
- **"You Are Here" Distributions:** Pre-computes and beautifully renders Gaussian density curves via SVG mathematical paths to show users exactly where a game sits relative to the rest of the database for Complexity, Playtime, and Age.
- **Interactive Histograms:** 10-bar interactive histograms representing the 0.5-increment score distributions of community ratings, complete with hover tooltips.
- **Dynamic Arcs:** Visual gauges showing the percentage of players who "Recommend" the game.

### 4. Ratings, Reviews & Advanced NLP
Ludora doesn't just show reviews; it deeply analyzes them using state-of-the-art Natural Language Processing.
- **Review Browsing:** A dedicated interface to read through tens of thousands of community reviews.
- **Review Filter Options:** Filter user reviews by specific star ratings or sentiment buckets.
- **Review Language & Quality Detection:** Employs Meta's `fastText` model to assign quality scores to incoming reviews, automatically filtering out non-English, spam, or unhelpful one-liners.
- **Aspect-Based Sentiment Analysis (ABSA):** 
  - A zero-shot classification pipeline running on `deberta-v3-large-absa`.
  - Automatically identifies sub-sentential mentions of 22 specific game aspects (e.g., *Rulebook*, *Downtime*, *Component Quality*, *Player Interaction*) and categorizes them into granular positive/negative sentiments.
- **Aspect Cards UI:** Clean, glassmorphic UI cards that group extracted community feedback by Aspect, displaying exactly what players loved (Positive Feedback) or disliked (Negative Feedback) about specific parts of the game.
- **ABSA + Multi-Review Summarization (Community Consensus):**
  - Dynamically synthesizes the extracted ABSA metrics into cohesive, localized paragraph summaries using local LLMs.
  - Generates an intelligent "Community Consensus" that summarizes the overall vibe of the reviews in a human-readable format.

### 5. Recommendation Engine (RecSys)
A multi-algorithmic engine allowing for real-time comparative analysis of recommendation performance.
- **Similar Games & Recommendations:** Dedicated UI sections displaying games similar to the one currently being viewed.
- **Popularity-Based:** Fast baseline model using total ratings and rank.
- **Content-Based Filtering:** `TF-IDF` Vectorization and Semantic Embeddings for deep contextual similarity.
- **Collaborative Filtering:** Item-Item Cosine Similarity, Matrix Factorization (SVD), and Alternating Least Squares (ALS).
- **Hybrid System:** Weighted ensemble algorithms providing a balanced, highly diverse output of recommendations.

### 6. Conversational AI Assistant
An intelligent, locally-hosted sidebar companion that helps users discover games using natural language.
- **Local Apple Silicon Execution:** Integrates Apple's `MLX` framework to run a 30-Billion parameter LLM (`Qwen3-30B-A3B-MLX-4bit`) directly on local hardware.
- **Dynamic Semantic Routing:** The assistant uses an intent-classifier to route user queries into distinct functional states:
  - `Searcher`: Extracts complex metadata parameters from fuzzy natural language.
  - `Clarifier`: Disambiguates vague queries or multiple game matches gracefully.
  - `Comparer`: Compares multiple games side-by-side on key attributes.
  - `Recommender`: Explains *why* a specific game fits the user's previously stated preferences.
  - `GameDetail`: Pulls up high-level summaries for specific titles.
- **Contextual Memory:** Maintains a rolling multi-turn memory buffer, allowing users to progressively refine searches (e.g., *"Find economic games"* -> *"Actually, only ones that play well at 2 players"*).
- **Inline UI Widgets:** Renders interactive mini-cards directly inside the chat interface to surface game details (ratings, weight, player count) seamlessly.

## Technology Stack

- **Python 3.10+** (managed via `uv`)
- **Backend Framework**: FastAPI, Uvicorn
- **Database & ORM**: PostgreSQL, SQLAlchemy, Alembic, `pgvector`
- **Data Science & NLP**: Pandas, Scikit-Learn, Sentence-Transformers, HuggingFace Transformers, PyTorch, fastText
- **AI & LLM Integration**: Apple `MLX`, `mlx_lm`, Qwen3-30B
- **Frontend Framework**: React 19, Vite, TypeScript
- **State Management & Routing**: React Router, TanStack React Query, Axios
- **Styling**: Tailwind CSS, Heroicons
- **Containerization**: Docker Compose

## Getting Started

### Prerequisites
- Docker and Docker Compose
- Node.js (if running frontend locally)
- Python 3.10+ with `uv` (if running backend or ML scripts locally)

### Running the Application

To spin up the entire application in development mode with live-reloading:

```bash
docker compose up -d
```

### Accessing the Services
- **Frontend UI**: http://localhost:5173
- **FastAPI Swagger Docs**: http://localhost:8000/docs
- **PostgreSQL Database**: localhost:5432

### Local Development (Native Execution via UV)

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

**MLX Local LLM Server:**
```bash
mlx_lm.server --model "Qwen/Qwen3-30B-A3B-MLX-4bit"
```
