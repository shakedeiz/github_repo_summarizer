"""
Module: prompt_builder
Description: Responsible for assembling the filtered GitHub files into a dense, 
highly structured prompt payload for the LLM, strictly adhering to context window limits.
"""

import logging
from repo_scanner import RepoScanner

logger = logging.getLogger(__name__)

class PromptBuilder:
    def __init__(self):
        # We use XML-style tags. LLMs (especially Instruct models) parse XML boundaries 
        # highly effectively, preventing them from confusing source code with prompt instructions.
        self.file_template = '<file path="{path}">\n{content}\n</file>\n'

    def get_system_prompt(self) -> str:
        """
        Defines the strict persona and output schema instructions for the LLM.
        
        Why this matters: Instructing the model to return a "flat array of strings" 
        prevents it from returning conversational sentences (e.g., "The project uses Python") 
        which would break the required JSON format.
        """
        return """You are a Senior Software Architect. Analyze the following GitHub repository files.
Your output MUST be valid JSON containing exactly these three keys:
1. "summary": A high-level, 2-3 sentence overview of the project's primary purpose.
2. "technologies": A flat array of strings containing only the names of the main languages, frameworks, and tools used (e.g., ["Python", "FastAPI", "React"]). Do not use sentences.
3. "structure": A brief description of the core directory layout and architecture.
"""

    def build_final_prompt(self, github_url: str, filtered_files: list) -> str:
        """
        Assembles the final payload string, enforcing a strict character budget to 
        prevent severe latency spikes or API rate-limiting.

        Args:
            github_url (str): The target repository URL.
            filtered_files (list): A list of dictionaries containing file 'path' and 'download_url'.
                                   (Provided by RepoScanner.filter_files)

        Returns:
            str: The final prompt payload string.
        """
        scanner = RepoScanner()
        payload = f"Repository: {github_url}\n\n"
        
        current_length = len(payload)
        
        # 18,000 chars is roughly 4,500 tokens. This conservative limit ensures rapid 
        # LLM inference and prevents GitHub from rate-limiting our HTTP requests.
        max_length = 18000
        
        for file in filtered_files:
            # STOP FETCHING: If we are already near the token limit, there is no point 
            # making further HTTP requests to GitHub. This saves massive amounts of time.
            if current_length >= max_length:
                payload += "\n[NOTE: Further files omitted due to context limits.]"
                logger.info("Reached 18,000 character context limit. Halting further file fetches.")
                break
                
            content = scanner.get_raw_content(file["download_url"])
            if not content:
                continue
                
            # Truncate individual massive files (like a 5,000-line main.py).
            # Retaining the head and tail preserves the imports and the main execution 
            # block, which provide the most architectural context.
            if len(content) > 3000:
                content = content[:1500] + "\n\n...[MIDDLE TRUNCATED FOR CONTEXT LIMITS]...\n\n" + content[-1500:]
                
            file_block = self.file_template.format(path=file['path'], content=content)
            
            payload += file_block
            current_length += len(file_block)
            
        # Hard cap the final string just in case the last file pushed us slightly over
        return payload[:max_length]