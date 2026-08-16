from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import games, search, recommendations, metadata

app = FastAPI(title="Ludora API", version="0.1.0")

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games.router, prefix="/api/games", tags=["games"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(metadata.router, prefix="/api", tags=["metadata"])
app.include_router(recommendations.router, prefix="/api", tags=["recommendations"])
@app.get("/health")
def health_check():
    return {"status": "ok"}
