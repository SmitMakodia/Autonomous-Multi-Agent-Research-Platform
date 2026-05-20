import httpx
import json
from typing import AsyncGenerator, List, Dict
from config import LLAMA_SERVER_URL, LLM_MODEL
class LlamaClient:
    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "stream": True,
            "temperature": 0.3,
            "max_tokens": 4096
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{LLAMA_SERVER_URL}/chat/completions", json=payload) as response:
                response.raise_for_status()
                
                is_thinking = False
                buffer = ""
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            
                            content = delta.get("content")
                            if content:
                                buffer += content
                                
                                while True:
                                    if not is_thinking:
                                        if "<think>" in buffer:
                                            before_think, rest = buffer.split("<think>", 1)
                                            before_think = before_think.replace("<response>", "").replace("</response>", "")
                                            if before_think.strip():
                                                yield {"type": "content", "content": before_think}
                                            buffer = rest
                                            is_thinking = True
                                        elif "<response>" in buffer:
                                            before_resp, rest = buffer.split("<response>", 1)
                                            if before_resp.strip():
                                                yield {"type": "content", "content": before_resp}
                                            buffer = rest
                                        else:
                                            if "<" not in buffer:
                                                content_out = buffer.replace("</response>", "")
                                                if content_out:
                                                    yield {"type": "content", "content": content_out}
                                                buffer = ""
                                            break
                                    else:
                                        if "</think>" in buffer:
                                            inside_think, rest = buffer.split("</think>", 1)
                                            if inside_think:
                                                yield {"type": "reasoning", "content": inside_think}
                                            buffer = rest
                                            is_thinking = False
                                        elif "<response>" in buffer: # Fallback if model forgot </think>
                                            inside_think, rest = buffer.split("<response>", 1)
                                            if inside_think:
                                                yield {"type": "reasoning", "content": inside_think}
                                            buffer = rest
                                            is_thinking = False
                                        else:
                                            if "<" not in buffer:
                                                yield {"type": "reasoning", "content": buffer}
                                                buffer = ""
                                            break
                                            
                        except json.JSONDecodeError:
                            continue
                
                if buffer:
                    if is_thinking:
                        yield {"type": "reasoning", "content": buffer}
                    else:
                        content_out = buffer.replace("<response>", "").replace("</response>", "")
                        if content_out:
                            yield {"type": "content", "content": content_out}
llama_client = LlamaClient()