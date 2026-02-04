"""
Ollama LLM wrapper for local language model inference.

Ollama Documentation: https://ollama.ai/
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Wrapper for Ollama local LLM inference."""
    
    BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:0.5b"  # Lightweight model for 8GB RAM
    
    def __init__(self):
        """Initialize Ollama client."""
        self.model = os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self._available = None
        logger.info(f"OllamaLLM initialized with model: {self.model}")
    
    def is_available(self) -> bool:
        """
        Check if Ollama service is running and model is available.
        
        Returns:
            True if Ollama is accessible, False otherwise
        """
        if self._available is not None:
            return self._available
        
        try:
            # Check if Ollama server is running
            response = requests.get(f"{self.BASE_URL}/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                self._available = any(self.model in name for name in model_names)
                
                if not self._available:
                    logger.warning(f"Model {self.model} not found in Ollama")
                else:
                    logger.info("Ollama is available and ready")
            else:
                self._available = False
                
        except Exception as e:
            logger.info(f"Ollama not available: {e}")
            self._available = False
        
        return self._available
    
    def generate(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """
        Generate text using Ollama.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated text or None if failed
        """
        if not self.is_available():
            logger.info("Ollama not available, skipping generation")
            return None
        
        try:
            url = f"{self.BASE_URL}/api/generate"
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            generated_text = data.get('response', '').strip()
            
            logger.info(f"Generated {len(generated_text)} characters")
            return generated_text
            
        except Exception as e:
            logger.error(f"Error generating with Ollama: {e}")
            return None
