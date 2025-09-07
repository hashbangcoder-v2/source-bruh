import os
from typing import List

import google.generativeai as genai


class GeminiClient:
    def __init__(self, api_key_env: str, oracle_model: str, embedding_model: str) -> None:
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key in env var {api_key_env}")
        genai.configure(api_key=api_key)
        self.oracle_model_name = oracle_model
        self.embedding_model_name = embedding_model

    def describe_image(self, image_bytes: bytes) -> str:
        # Using Gemini 1.5 Flash multimodal prompt
        model = genai.GenerativeModel(self.oracle_model_name)
        prompt = (
            "Describe this image concisely for search. Focus on pictograms/infographics/charts. "
            "Include any readable text, labels, axes, and key entities. Limit to ~80 words."
        )
        result = model.generate_content([
            {"mime_type": "image/jpeg", "data": image_bytes},
            prompt,
        ])
        return (result.text or "").strip()

    def embed_text(self, text: str) -> List[float]:
        embed = genai.embed_content(model=self.embedding_model_name, content=text)
        # google-generativeai may return dict or object; normalize
        if isinstance(embed, dict):
            emb = embed.get("embedding") or embed.get("data", {}).get("embedding")
        else:
            emb = getattr(embed, "embedding", None)
        if emb is None:
            raise RuntimeError("Embedding not found in response")
        return list(emb)


