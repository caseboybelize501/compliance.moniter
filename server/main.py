"""
ACMP API Server

FastAPI application for the Autonomous Compliance Monitoring Platform.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from server.api import controls, violations, evidence, reports, frameworks, integrations, auth
from engine.framework_registry import registry as framework_registry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("ACMP API Server starting...")
    await framework_registry.initialize()
    logger.info("Framework registry initialized")
    yield
    # Shutdown
    logger.info("ACMP API Server shutting down...")


app = FastAPI(
    title="ACMP API",
    description="Autonomous Compliance Monitoring Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "name": "ACMP API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(frameworks.router, prefix="/api/frameworks", tags=["frameworks"])
app.include_router(controls.router, prefix="/api/controls", tags=["controls"])
app.include_router(violations.router, prefix="/api/violations", tags=["violations"])
app.include_router(evidence.router, prefix="/api/evidence", tags=["evidence"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
