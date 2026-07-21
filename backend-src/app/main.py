from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import os
from .core.config import settings
from .api.jobs import router as jobs_router
from .api.job_ingestion import router as job_ingestion_router
from .api.endpoints.data_ingestion import router as data_ingestion_router
from .api.endpoints.reranking import router as reranking_router
from .api.endpoints.csv_ingestion import router as csv_ingestion_router
from .api.endpoints.kg_analysis import router as kg_analysis_router  # 新增这一行
from .api.endpoints.auth import router as auth_router
from .api.endpoints.keyword_extraction import router as keyword_extraction_router
from .api.endpoints.bm25 import router as bm25_router
from .api.endpoints.semantic import router as semantic_router
from .api.endpoints.fusion import router as fusion_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A semantic job matching application using Elasticsearch and Knowledge Graphs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add validation error handler to see detailed errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error in {request.url.path}")
    logger.error(f"Errors: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": exc.errors(),
            "message": "Request validation failed. Check the 'detail' field for specific errors."
        }
    )

# Include routers
app.include_router(jobs_router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(job_ingestion_router, prefix="/api/v1/ingestion", tags=["job-ingestion"])
app.include_router(data_ingestion_router, prefix="/api/v1/ingest", tags=["data-ingestion"])
app.include_router(reranking_router, prefix="/api/v1/reranking", tags=["reranking"])
app.include_router(csv_ingestion_router, prefix="/api/v1/csv", tags=["csv-ingestion"])
app.include_router(kg_analysis_router, prefix="/api/v1/kg", tags=["knowledge_graph"])  # 新增这一行
app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(keyword_extraction_router, prefix="/api/v1/keyword-extraction", tags=["keyword-extraction"])
app.include_router(bm25_router, prefix="/api/v1/bm25", tags=["chinese-bm25"])
app.include_router(semantic_router, prefix="/api/v1/semantic", tags=["semantic-reranking"])
app.include_router(fusion_router, prefix="/api/v1/fusion", tags=["fusion"])

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with basic information"""
    return """
    <html>
        <head>
            <title>Job Matching API</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .header { background: #f4f4f4; padding: 20px; border-radius: 5px; }
                .endpoint { background: #e8f4f8; padding: 10px; margin: 10px 0; border-radius: 3px; }
                code { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🚀 Job Matching API</h1>
                    <p>A semantic job matching application using Elasticsearch and Knowledge Graphs</p>
                </div>
                
                <h2>Available Endpoints</h2>
                
                <div class="endpoint">
                    <h3>📊 Job Search</h3>
                    <p><code>POST /api/v1/jobs/search</code> - Search for jobs using hybrid search</p>
                    <p><code>POST /api/v1/jobs/search-with-resume</code> - Search with resume-based matching</p>
                    <p><code>GET /api/v1/jobs/{job_id}</code> - Get specific job details</p>
                    <p><code>GET /api/v1/jobs/{job_id}/similar</code> - Get similar jobs</p>
                </div>
                
                <div class="endpoint">
                    <h3>📝 Job Management</h3>
                    <p><code>POST /api/v1/jobs/</code> - Create new job posting</p>
                    <p><code>PUT /api/v1/jobs/{job_id}</code> - Update job posting</p>
                    <p><code>DELETE /api/v1/jobs/{job_id}</code> - Delete job posting</p>
                    <p><code>POST /api/v1/jobs/bulk</code> - Bulk create jobs</p>
                </div>
                
                <div class="endpoint">
                    <h3>👤 Resume Processing</h3>
                    <p><code>POST /api/v1/jobs/upload-resume</code> - Upload and process resume</p>
                    <p><code>GET /api/v1/jobs/resume-insights/{candidate_id}</code> - Get resume insights</p>
                </div>
                
                <div class="endpoint">
                    <h3>📈 Analytics</h3>
                    <p><code>GET /api/v1/jobs/market-trends/{skill}</code> - Get market trends for skill</p>
                    <p><code>POST /api/v1/jobs/recommendations</code> - Get job recommendations</p>
                </div>
                
                <div class="endpoint">
                    <h3>🔄 Job Ingestion</h3>
                    <p><code>POST /api/v1/ingestion/fetch-jobs</code> - Fetch jobs from external sources</p>
                    <p><code>POST /api/v1/ingestion/fetch-jobs-background</code> - Fetch jobs in background</p>
                    <p><code>POST /api/v1/ingestion/bulk-ingest</code> - Bulk ingest jobs for multiple queries</p>
                    <p><code>GET /api/v1/ingestion/sources</code> - Get available job sources</p>
                    <p><code>GET /api/v1/ingestion/stats</code> - Get ingestion statistics</p>
                </div>
                
                <div class="endpoint">
                    <h3>🚀 Rise API Integration</h3>
                    <p><code>POST /api/v1/ingest/rise</code> - Ingest jobs from Rise API</p>
                    <p><code>POST /api/v1/ingest/rise/bulk</code> - Bulk ingest from multiple Rise API pages</p>
                    <p><code>GET /api/v1/ingest/status</code> - Get current ingestion status</p>
                    <p><code>POST /api/v1/ingest/rise/test</code> - Test Rise API integration</p>
                    <p><code>DELETE /api/v1/ingest/clear</code> - Clear ingested data (use with caution)</p>
                </div>
                
                <div class="endpoint">
                    <h3>📄 CSV Job Ingestion</h3>
                    <p><code>POST /api/v1/csv/ingest-csv</code> - Ingest jobs from any CSV file (upload)</p>
                    <p><code>POST /api/v1/csv/ingest-swe-csv</code> - Ingest jobs from SWE.csv file</p>
                    <p><code>GET /api/v1/csv/ingest-swe-csv/status</code> - Get CSV ingestion status</p>
                </div>
                
                <div class="endpoint">
                    <h3>🎯 Personalized Reranking</h3>
                    <p><code>POST /api/v1/reranking/search-reranked</code> - Search with personalized reranking</p>
                    <p><code>POST /api/v1/reranking/search-reranked-with-resume</code> - Search with resume-based reranking</p>
                    <p><code>POST /api/v1/reranking/personalized-recommendations</code> - Get personalized job recommendations</p>
                    <p><code>GET /api/v1/reranking/reranking-explanation/{job_id}</code> - Get detailed ranking explanations</p>
                    <p><code>PUT /api/v1/reranking/reranking-weights</code> - Customize reranking factors</p>
                    <p><code>GET /api/v1/reranking/reranking-statistics</code> - Get reranking performance stats</p>
                </div>
                
                <div class="endpoint">
                    <h3>🔧 System</h3>
                    <p><code>GET /health</code> - Health check</p>
                    <p><code>GET /docs</code> - Interactive API documentation</p>
                </div>
                
                <h2>Quick Start</h2>
                <p>1. Visit <code>/docs</code> for interactive API documentation</p>
                <p>2. Use <code>POST /api/v1/jobs/search</code> to search for jobs</p>
                <p>3. Upload a resume with <code>POST /api/v1/jobs/upload-resume</code></p>
                <p>4. Get personalized recommendations with <code>POST /api/v1/jobs/recommendations</code></p>
            </div>
        </body>
    </html>
    """

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting Job Matching API...")
    
    # Create upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Created upload directory: {settings.UPLOAD_DIR}")
    
    # Test database connections (non-blocking - app will start even if databases are unavailable)
    try:
        from .core.database import get_elasticsearch, get_neo4j
        
        # Test Elasticsearch connection
        try:
            es = get_elasticsearch()
            if es.ping():
                logger.info("✅ Elasticsearch connection successful")
            else:
                logger.warning("⚠️ Elasticsearch connection failed - continuing anyway")
        except Exception as es_error:
            logger.warning(f"⚠️ Elasticsearch connection error: {es_error} - continuing anyway")
        
        # Test Neo4j connection
        try:
            neo4j = get_neo4j()
            with neo4j.get_session() as session:
                session.run("RETURN 1")
            logger.info("✅ Neo4j connection successful")
        except Exception as neo4j_error:
            logger.warning(f"⚠️ Neo4j connection error: {neo4j_error} - continuing anyway")
        
    except Exception as e:
        logger.warning(f"⚠️ Database connection check failed: {e} - app will continue to start")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Job Matching API...")
    
    try:
        from .core.database import neo4j_client
        neo4j_client.close()
        logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
