import logging
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Internal pipeline modules
from repo_scanner import RepoScanner
from prompt_builder import PromptBuilder
from nebius_llm_summarizer import NebiusLLMSummarizer

# Initialize environment variables
load_dotenv()

# Configure application-level logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI application instance
app = FastAPI(
    title="GitHub Repository Summarization API",
    description="Extracts architectural insights from GitHub repositories using an LLM.",
    version="1.0.0"
)

class SummarizeRequest(BaseModel):
    """
    Data Transfer Object (DTO) for the summarization request.
    Validates that the incoming payload contains a 'github_url' string.
    """
    github_url: str

@app.post("/summarize")
async def summarize_repository(request: SummarizeRequest):
    """
    POST endpoint to process a GitHub repository and return architectural insights.
    
    Args:
        request (SummarizeRequest): The JSON payload containing the repository URL.
        
    Returns:
        dict | JSONResponse: A dictionary with summary, technologies, and structure on success,
                             or a JSON formatted error response on failure.
    """
    logger.info(f"Initiating summarization pipeline for URL: {request.github_url}")
    
    try:
        # Phase 1: Repository Retrieval and Filtering
        logger.info("Phase 1: Fetching and filtering repository tree.")
        scanner = RepoScanner()
        tree = scanner.get_repo_tree(request.github_url)
        
        if not tree:
            raise ValueError("Repository tree retrieval failed. Verify the URL is public and correctly formatted.")
            
        filtered_files = scanner.filter_files(tree, request.github_url)
        
        # Phase 2: Context Assembly
        logger.info("Phase 2: Building LLM prompt payload.")
        builder = PromptBuilder()
        user_data = builder.build_final_prompt(request.github_url, filtered_files)
        
        # Phase 3: LLM Inference
        logger.info("Phase 3: Executing LLM extraction via Nebius API.")
        summarizer = NebiusLLMSummarizer()
        insights = summarizer.extract_repo_insights(user_data)
        
        # Upstream error propagation check
        if "Error:" in insights.get("summary", ""):
            raise ValueError(insights["structure"])

        return insights
        
    except Exception as e:
        logger.error(f"Pipeline execution terminated with error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )

if __name__ == "__main__":
    # Development server entry point
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)