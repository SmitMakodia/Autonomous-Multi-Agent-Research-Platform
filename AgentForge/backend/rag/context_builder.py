import tiktoken
from typing import List, Dict, Any
class ContextBuilder:
    def __init__(self, max_tokens: int = 6000):
        self.max_tokens = max_tokens
        self.encoder = tiktoken.get_encoding("cl100k_base")
    def build_context_string(self, chunks: List[Dict[str, Any]]) -> str:
        context_parts = []
        current_tokens = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            source = chunk.get("metadata", {}).get("source", "Unknown Source")
            block = f"[Source: {source}]\n{text}\n\n---\n\n"
            block_tokens = len(self.encoder.encode(block))
            if current_tokens + block_tokens > self.max_tokens:
                break
            context_parts.append(block)
            current_tokens += block_tokens
        return "".join(context_parts)
context_builder = ContextBuilder()