import asyncio
import os
import torch
import gc
from typing import List
from .base_agent import BaseAgent, ContextChunk
from config import BASE_DIR
from llm.model_manager import model_manager
from PIL import Image

class OCRAgent(BaseAgent):
    name = "ocr_image"
    description = "Extracts text from images using GLM-OCR."

    async def run(self, file_path: str, **kwargs) -> List[ContextChunk]:
        print(f"[OCRAgent] Processing OCR for: {file_path}")

        def sync_ocr():
            chunks = []
            model = None
            processor = None
            try:
                # Stop Qwen LLM to free up 100% of the VRAM for OCR
                model_manager.stop_llm()
                
                # Wait a moment to ensure VRAM is cleared by the OS
                import time
                time.sleep(1)

                print("[OCRAgent] Loading official GLM-OCR model directly into VRAM...")
                from transformers import AutoProcessor, AutoModelForImageTextToText
                
                model_path = os.path.join(BASE_DIR, "models", "GLM-OCR")
                
                processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
                model = AutoModelForImageTextToText.from_pretrained(
                    pretrained_model_name_or_path=model_path,
                    torch_dtype=torch.bfloat16,
                    device_map="cuda",
                    trust_remote_code=True
                ).eval()
                
                print("[OCRAgent] Model loaded. Running inference...")
                
                img = Image.open(file_path).convert('RGB')
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "image": img},
                            {"type": "text", "text": "Text Recognition:"}
                        ]
                    }
                ]
                
                inputs = processor.apply_chat_template(
                    messages,
                    tokenize=True,
                    add_generation_prompt=True,
                    return_dict=True,
                    return_tensors="pt"
                ).to(model.device)
                
                inputs.pop("token_type_ids", None)
                
                with torch.no_grad():
                    generated_ids = model.generate(**inputs, max_new_tokens=2048)
                    
                output_text = processor.decode(
                    generated_ids[0][inputs["input_ids"].shape[1]:], 
                    skip_special_tokens=True
                ).strip()

                if output_text:
                    heading = "**Vision Extract: GLM-OCR Analysis of User-Provided Image**\n\n"
                    chunks.append(
                        ContextChunk(
                            text=heading + output_text,
                            source=file_path,
                            agent_name=self.name
                        )
                    )
                print(f"[OCRAgent] GLM-OCR complete. Extracted {len(output_text)} characters.")

            except Exception as e:
                print(f"[OCRAgent] GLM-OCR inference failed: {e}")
            finally:
                print("[OCRAgent] Unloading GLM-OCR model and clearing VRAM...")
                if model is not None:
                    del model
                if processor is not None:
                    del processor
                    
                # Force garbage collection and empty CUDA cache
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    
                time.sleep(1) # Give OS time to reclaim memory
                
                # Always restart the Qwen LLM so the orchestrator can continue
                model_manager.start_llm()

            return chunks

        return await asyncio.to_thread(sync_ocr)