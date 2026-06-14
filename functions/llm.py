import base64
from typing import List

import requests
from logger_config import get_logger, log_exception

logger = get_logger(__name__)


class GeminiClient:
    """
    Client for Gemini embedding operations.

    The project intentionally uses direct multimodal embeddings:
    - images are embedded from bytes for indexing
    - user search text is embedded as a retrieval query
    """

    def __init__(
        self,
        api_key: str,
        embedding_model: str,
        output_dimensionality: int = 768,
    ) -> None:
        if not api_key:
            logger.error("Missing or empty API key")
            raise RuntimeError("Missing API key")

        self.api_key = api_key
        self.embedding_model_name = embedding_model
        self.output_dimensionality = output_dimensionality
        self.endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{embedding_model}:embedContent"
        )

        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        logger.debug(f"Using Gemini API key: {masked_key}")
        logger.info(
            "Gemini client initialized "
            f"(embedding={embedding_model}, dim={output_dimensionality})"
        )

    def embed_image(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> List[float]:
        """Generate an embedding vector directly from image bytes."""
        logger.debug(f"Generating image embedding ({len(image_bytes)} bytes, {mime_type})")
        try:
            payload = {
                "content": {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type or "image/jpeg",
                                "data": base64.b64encode(image_bytes).decode("ascii"),
                            }
                        }
                    ]
                },
                "output_dimensionality": self.output_dimensionality,
            }
            return self._embed(payload)
        except Exception as e:
            log_exception(logger, "Failed to generate image embedding", e)
            raise

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding vector for a user's search query."""
        prepared = f"task: search result | query: {(text or '').strip()}"
        logger.debug(f"Generating query embedding ({len(prepared)} chars)")
        try:
            payload = {
                "content": {"parts": [{"text": prepared}]},
                "output_dimensionality": self.output_dimensionality,
            }
            return self._embed(payload)
        except Exception as e:
            log_exception(logger, "Failed to generate query embedding", e)
            raise

    def _embed(self, payload: dict) -> List[float]:
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(
                f"Gemini embedding request failed ({response.status_code}): {response.text[:500]}"
            )

        data = response.json()
        embedding = data.get("embedding")
        if embedding is None:
            embeddings = data.get("embeddings") or []
            embedding = embeddings[0] if embeddings else None

        values = embedding.get("values") if isinstance(embedding, dict) else None
        if not values:
            logger.error("Embedding values not found in Gemini response")
            raise RuntimeError("Embedding not found in response")

        logger.debug(f"Generated embedding (dim={len(values)})")
        return [float(value) for value in values]
