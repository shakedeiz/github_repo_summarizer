# GitHub Repository Summarizer API

A FastAPI web service that analyzes public GitHub repositories and generates a structured JSON summary outlining the project's core purpose, utilized technologies, and architectural structure using a Large Language Model.

## Setup and Run Instructions

Assuming a clean machine with Python 3.10+ installed:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure the Environment
Set your Nebius API key as an environment variable (or create a `.env` file in the project root):
```env
NEBIUS_API_KEY=your_api_key_here
```

### 3. Start the Server
Launch the FastAPI application using the Uvicorn ASGI server:
```bash
uvicorn main:app
```
*(Note for Windows environments: If the `uvicorn` command is unrecognized, execute `python -m uvicorn main:app` instead).*

### 4. Test the API
The server listens on `http://127.0.0.1:8000`. You can test the endpoint using the requested curl command:
```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "[https://github.com/psf/requests](https://github.com/psf/requests)"}'
```

---

## Architectural Decisions

### Framework Selection
FastAPI was selected over Flask primarily for its native integration with Pydantic. By defining a strict `SummarizeRequest` schema, FastAPI automatically handles payload validation for the `POST /summarize` endpoint, verifying URL formatting via regex and returning appropriate 422 Unprocessable Entity errors for malformed requests.

### LLM Selection & Comparison
The **`meta-llama/Llama-3.3-70B-Instruct`** model was selected via Nebius. Compared to smaller 8B models, the 70B parameter count maintains much stronger reasoning across multi-file context windows. Compared to base models, this "Instruct" variant is prioritized because of its reliability in adhering to strict JSON schemas, ensuring a flat array for `technologies` rather than conversational filler.

### Repository Processing Strategy
Feeding an entire raw repository directly into an LLM context window is impractical. To ensure the model only receives the most relevant information, I built a targeted filtering pipeline:
* **Filtering:** The application explicitly ignores binaries, images, lock files, and heavy data extensions (`.zip`, `.sqlite`, `.wasm`). More importantly, it dynamically fetches the repository's native `.gitignore` file and applies those rules. This automatically excludes heavy directories like `node_modules/` and prevents the accidental exposure of `.env` or credential files.
* **Prioritization:** Files are sorted so the LLM processes high-level architectural context first (like `README.md` and configuration files) before analyzing the raw source code. 
* **Truncation:** To prevent individual massive files from dominating the context window, they are truncated. The pipeline retains the head and tail of these files to preserve their overall structure, omitting the middle.
* **Branching Strategy:** The GitHub REST API tree endpoint is used without a hardcoded branch. By targeting `HEAD`, the API automatically resolves to the repository's default branch (whether `main`, `master`, or otherwise) without breaking on custom repository setups.
* **Context Management & Fetch Budgets:** To prevent massive repositories from causing excessive HTTP requests, a dynamic token budget is enforced *during* the fetch loop. The total payload is strictly capped at 18,000 characters. This conservative limit prevents severe latency spikes and GitHub API rate-limiting from fetching hundreds of files, while still providing the 70B model with dense, high-signal architecture files.

### Security Implementation
To mitigate the risk of directory traversal vulnerabilities, this application does not utilize `git clone` to download files to the host machine's local storage. Instead, the `RepoScanner` uses the GitHub REST API to fetch tree data directly into memory. This eliminates the risk of malicious symlinks exploiting the local file system.