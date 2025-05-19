# backend/app/llm_loader.py
import os
import logging
from typing import Optional, Tuple
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedModel,
    PreTrainedTokenizerBase,
)
from accelerate.hooks import remove_hook_from_module

from .core.config import settings

logger = logging.getLogger(__name__)

_loaded_qwen_model: Optional[PreTrainedModel] = None
_loaded_qwen_tokenizer: Optional[PreTrainedTokenizerBase] = None


def load_qwen_model_and_tokenizer() -> (
    Tuple[Optional[PreTrainedModel], Optional[PreTrainedTokenizerBase]]
):
    """
    Loads the Qwen3 model and tokenizer based on settings (Singleton pattern).
    Handles device placement and returns raw HF objects.
    """
    global _loaded_qwen_model, _loaded_qwen_tokenizer
    if _loaded_qwen_model is None or _loaded_qwen_tokenizer is None:
        logger.info(
            f"Loading Qwen3 model and tokenizer: '{settings.QWEN_MODEL_NAME}'..."
        )
        logger.info(f"Device Map: {settings.GENERATION_MODEL_DEVICE}")
        # Add quantization info log if needed

        try:
            # --- Quantization (Optional) ---
            model_kwargs = {"device_map": settings.GENERATION_MODEL_DEVICE}
            # Add BitsAndBytesConfig logic here if GENERATION_MODEL_QUANTIZATION is set in config

            # --- Load Model and Tokenizer ---
            logger.info(
                f"Loading Qwen3 model and tokenizer from '{settings.QWEN_MODEL_NAME}'..."
            )
            logger.info(f"Cache Directory: {settings.LOCAL_MODELS_DIR}")
            _loaded_qwen_tokenizer = AutoTokenizer.from_pretrained(
                settings.QWEN_MODEL_NAME,
                cache_dir=settings.LOCAL_MODELS_DIR,
            )
            _loaded_qwen_model = AutoModelForCausalLM.from_pretrained(
                settings.QWEN_MODEL_NAME,
                torch_dtype="auto",  # Use auto precision
                **model_kwargs,
                cache_dir=settings.LOCAL_MODELS_DIR,
            )
            # Pad token check (though Qwen should have one)
            if _loaded_qwen_tokenizer.pad_token is None:
                _loaded_qwen_tokenizer.pad_token = _loaded_qwen_tokenizer.eos_token
                if _loaded_qwen_model.config.pad_token_id is None:
                    _loaded_qwen_model.config.pad_token_id = (
                        _loaded_qwen_model.config.eos_token_id
                    )
                logger.info("Set tokenizer pad_token to eos_token for Qwen model.")

            logger.info(
                f"Qwen3 model and tokenizer '{settings.QWEN_MODEL_NAME}' loaded successfully."
            )

        except ImportError as ie:
            logger.critical(
                f"Import error during Qwen loading: {ie}. Dependencies missing?",
                exc_info=True,
            )
            _loaded_qwen_model = None
            _loaded_qwen_tokenizer = None
            raise RuntimeError(f"Missing dependencies for LLM loading: {ie}") from ie
        except Exception as e:
            logger.critical(f"Failed to load Qwen model/tokenizer: {e}", exc_info=True)
            _loaded_qwen_model = None
            _loaded_qwen_tokenizer = None
            raise RuntimeError("Could not initialize Qwen model/tokenizer") from e

    return _loaded_qwen_model, _loaded_qwen_tokenizer


def cleanup_llm_resources():
    """Optional: Function to clean up resources."""
    global _loaded_qwen_model, _loaded_qwen_tokenizer
    logger.info("Cleaning up Qwen LLM resources...")
    if _loaded_qwen_model:
        try:
            remove_hook_from_module(_loaded_qwen_model)
            logger.debug("Removed accelerate hooks from Qwen model.")
        except Exception as e:
            logger.warning(f"Could not remove accelerate hooks cleanly: {e}")
    _loaded_qwen_model = None
    _loaded_qwen_tokenizer = None
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        logger.info("Cleared CUDA cache.")
    logger.info("Qwen LLM resources cleanup attempt finished.")


# --- Getter for dependencies ---
def get_qwen_model() -> PreTrainedModel:
    model, _ = load_qwen_model_and_tokenizer()
    if model is None:
        raise RuntimeError("Qwen model not loaded")
    return model


def get_qwen_tokenizer() -> PreTrainedTokenizerBase:
    _, tokenizer = load_qwen_model_and_tokenizer()
    if tokenizer is None:
        raise RuntimeError("Qwen tokenizer not loaded")
    return tokenizer
