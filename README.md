# 🚀 GitHub Repository Summarizer API

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)
![Nebius AI](https://img.shields.io/badge/AI-Llama%203.3%2070B-purple)

A high-performance FastAPI service that securely analyzes public GitHub repositories and generates structured JSON summaries. Utilizing `Llama-3.3-70B-Instruct`, the service extracts core purposes, tech stacks, and architectural overviews from codebases of any scale.

---

## ✨ Technical Highlights
* **Secure In-Memory Processing:** Eliminates local directory traversal and symlink vulnerabilities by utilizing the GitHub REST API for tree traversal instead of executing local `git clone` commands.
* **Dynamic Context Budgeting:** Implements a priority-sorted, 18,000-character "fetch budget" to safely summarize massive codebases (successfully tested against the Linux kernel) without triggering API rate limits or LLM context overflow.
* **Resilient Architecture:** Dynamically maps native `.gitignore` rules and utilizes the Git `HEAD` pointer to seamlessly handle custom branch structures without hardcoding fallbacks.
* **Strict Schema Enforcement:** Leverages FastAPI exception handlers and Pydantic models to guarantee 100% reliable, strongly-typed JSON outputs.

---

## 🛠️ Setup and Run Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure the Environment
Set your Nebius API key in a `.env` file in the project root:
```env
NEBIUS_API_KEY=your_api_key_here
```

### 3. Start the Server
```bash
uvicorn main:app --reload
```

### 4. Test the API
```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

---

## 🧠 Architectural Decisions

### Framework & Validation
**FastAPI** was selected for its native integration with **Pydantic**. By defining a strict `SummarizeRequest` schema, the API automatically validates incoming payloads (including regex URL verification) and returns standardized 422 errors for malformed requests.

### LLM Selection: Llama-3.3-70B-Instruct
The **70B parameter** model was chosen via Nebius for its superior reasoning over multi-file context windows compared to 8B alternatives. The **"Instruct"** variant ensures high reliability in adhering to the requested JSON schema, preventing conversational filler and ensuring machine-readable output.

### Repository Processing Strategy
To deliver high-signal context to the LLM while staying within token limits:
* **Intelligent Filtering:** Dynamically fetches the repository's `.gitignore` to exclude `node_modules/`, lock files, and binary assets.
* **High-Signal Prioritization:** Files are sorted to prioritize architectural anchors (READMEs, config files, entry points) over raw source code.
* **Context Truncation:** Massive files are "head-and-tail" truncated to preserve overall structure while omitting the middle content.
* **Dynamic Fetch Budgets:** A strict 18,000-character budget is enforced *during* the fetch loop. This prevents latency spikes and rate-limiting when analyzing massive repositories like the Linux kernel.

### Security Implementation
To protect the host system, the `RepoScanner` fetches tree data directly into memory via the GitHub REST API. By avoiding `git clone`, we mitigate risks associated with malicious symlinks exploiting the local file system.
