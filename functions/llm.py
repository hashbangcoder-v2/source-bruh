import os
from typing import List

import google.generativeai as genai
from logger_config import get_logger, log_exception

logger = get_logger(__name__)


class GeminiClient:
    """
    Client for Google Gemini API operations.
    
    Provides:
    - Image description generation for semantic search
    - Text embedding generation for vector similarity
    """
    
    def __init__(self, api_key_env: str, oracle_model: str, embedding_model: str) -> None:
        """
        Initialize Gemini client with API key and model configurations.
        
        Args:
            api_key_env: Environment variable name containing Gemini API key
            oracle_model: Model name for image description (e.g., "gemini-1.5-flash-latest")
            embedding_model: Model name for text embeddings (e.g., "text-embedding-004")
            
        Raises:
            RuntimeError: If API key is not found in environment
        """
        logger.info(f"🤖 Initializing Gemini client (oracle={oracle_model}, embedding={embedding_model})")
        api_key = os.environ.get(api_key_env)
        if not api_key:
            logger.error(f"✗ Missing API key in environment variable: {api_key_env}")
            raise RuntimeError(f"Missing API key in env var {api_key_env}")
        
        # Mask API key in logs
        masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        logger.debug(f"Using API key: {masked_key}")
        
        genai.configure(api_key=api_key)
        self.oracle_model_name = oracle_model
        self.embedding_model_name = embedding_model
        logger.info(f"✓ Gemini client initialized successfully")

    def describe_image(self, image_bytes: bytes) -> str:
        """
        Generate a concise description of an image for search indexing.
        
        The description focuses on:
        - Text content (labels, titles, captions)
        - Visual elements (charts, diagrams, icons)
        - Key entities and objects
        
        Args:
            image_bytes: Raw image data (JPEG format)
            
        Returns:
            Text description (~80 words)
        """
        logger.info(f"🖼️  Describing image ({len(image_bytes)} bytes) with {self.oracle_model_name}")
        try:
            model = genai.GenerativeModel(self.oracle_model_name)
            prompt = (
                "Describe this image concisely for search. Focus on pictograms/infographics/charts. "
                "Include any readable text, labels, axes, and key entities. Limit to ~80 words."
            )
            result = model.generate_content([
                {"mime_type": "image/jpeg", "data": image_bytes},
                prompt,
            ])
            description = (result.text or "").strip()
            logger.info(f"✓ Generated description ({len(description)} chars): {description[:100]}...")
            return description
        except Exception as e:
            log_exception(logger, "Failed to generate image description", e)
            raise

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Input text to embed
            
        Returns:
            768-dimensional embedding vector
            
        Raises:
            RuntimeError: If embedding is not found in API response
        """
        logger.debug(f"🧮 Generating embedding for text ({len(text)} chars): {text[:50]}...")
        try:
            embed = genai.embed_content(model=self.embedding_model_name, content=text)
            if isinstance(embed, dict):
                emb = embed.get("embedding") or embed.get("data", {}).get("embedding")
            else:
                emb = getattr(embed, "embedding", None)
            if emb is None:
                logger.error("✗ Embedding not found in API response")
                raise RuntimeError("Embedding not found in response")
            
            logger.debug(f"✓ Generated embedding (dim={len(emb)})")
            return list(emb)
        except Exception as e:
            log_exception(logger, "Failed to generate text embedding", e)
            raise


