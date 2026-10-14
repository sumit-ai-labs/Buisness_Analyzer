import os
import sys

# Ensure backend directory is in sys.path so 'app' imports work regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import alerts, auth, config_api, entities, geo, network, relationships
from app.core.config import settings
from app.core.logging import logger

app = FastAPI(
    title="Business Disruption Early-Warning System API",
    description="Backend API powering supply network monitoring, AI disruption detection, graph impact analysis, and explainable risk alerting.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for local frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(auth.router, prefix="/api")
app.include_router(entities.router, prefix="/api")
app.include_router(relationships.router, prefix="/api")
app.include_router(network.router, prefix="/api")
app.include_router(config_api.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(geo.router, prefix="/api")


@app.get("/health", tags=["Health Check"])
@app.get("/api/health", tags=["Health Check"])
def health_check():
    """Health check endpoint to verify backend operational readiness."""
    return {
        "status": "healthy",
        "env": settings.ENV,
        "tavily_key_configured": settings.has_tavily_key,
        "llm_key_configured": settings.has_llm_key,
        "llm_provider": settings.LLM_PROVIDER,
    }


@app.on_event("startup")
def startup_event():
    logger.info("Business Disruption Early-Warning System API starting up...")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Tavily Configured: {settings.has_tavily_key}")
    logger.info(f"LLM Configured: {settings.has_llm_key} ({settings.LLM_PROVIDER})")
