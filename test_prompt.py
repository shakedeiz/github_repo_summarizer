from repo_scanner import RepoScanner
from prompt_builder import PromptBuilder

def run_test():
    repo_url = "https://github.com/psf/requests"
    print(f"Testing context generation for: {repo_url}\n")

    scanner = RepoScanner()
    print("Fetching repository tree from GitHub...")
    tree = scanner.get_repo_tree(repo_url)
    
    if not tree:
        print("Error: Could not fetch tree.")
        return

    filtered_files = scanner.filter_files(tree, repo_url)
    print(f"Found {len(filtered_files)} important files after filtering.\n")

    builder = PromptBuilder()
    print("Building the final prompt (downloading files, please wait)...")
    final_prompt = builder.build_final_prompt(repo_url, filtered_files)

    print("\n" + "="*50)
    print("PROMPT STATISTICS:")
    print(f"Total prompt length: {len(final_prompt)} characters")
    print("="*50 + "\n")

    print("--- PROMPT PREVIEW (First 1500 characters) ---")
    print(final_prompt[:1500])
    print("\n... [PROMPT CONTINUES] ...\n")

if __name__ == "__main__":
    run_test()