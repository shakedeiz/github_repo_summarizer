import json
from dotenv import load_dotenv
from repo_scanner import RepoScanner
from prompt_builder import PromptBuilder
from nebius_llm_summarizer import NebiusLLMSummarizer


load_dotenv() # Load environment variables from .env file, including NEBIUS_API_KEY

def run_pipeline(repo_url: str):
    print(f"Starting analysis pipeline for: {repo_url}\n")

    # 1. SCAN
    print("[1/3] Scanning repository and applying .gitignore rules...")
    scanner = RepoScanner()
    tree = scanner.get_repo_tree(repo_url)
    filtered_files = scanner.filter_files(tree, repo_url)
    print(f"      Found {len(filtered_files)} highly relevant files.\n")

    # 2. BUILD
    print("[2/3] Downloading file contents and building user data payload...")
    builder = PromptBuilder()
    user_data = builder.build_final_prompt(repo_url, filtered_files)
    print(f"      Payload built. Total size: {len(user_data)} characters.\n")

    # 3. EXTRACT
    print("[3/3] Sending payload to Nebius LLM for architectural analysis...")
    summarizer = NebiusLLMSummarizer()
    insights = summarizer.extract_repo_insights(user_data)

    # OUTPUT
    print("\n" + "="*50)
    print("FINAL REPOSITORY ANALYSIS (JSON):")
    print("="*50)
    print(json.dumps(insights, indent=2))
    print("="*50 + "\n")

if __name__ == "__main__":
    target_repo = "https://github.com/psf/requests"
    run_pipeline(target_repo)