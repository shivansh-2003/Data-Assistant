"""Table extraction from images using Google Gemini API."""

import pandas as pd
from google import genai
from io import StringIO
import logging
import base64
from typing import List
from .config import IngestionConfig

logger = logging.getLogger(__name__)


def _get_client():
    """Get Gemini client with API key from config."""
    api_key = IngestionConfig.GEMINI_API_KEY
    if not api_key:
        raise ValueError("Please set GEMINI_API_KEY environment variable")
    return genai.Client(api_key=api_key)


def extract_table_with_gemini(image_path: str) -> pd.DataFrame:
    """Extract table from image using Gemini and return as pandas DataFrame."""
    logger.info(f"Loading image: {image_path}")
    client = _get_client()
    
    # Determine MIME type from file extension
    ext = image_path.lower().split('.')[-1]
    mime_types = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
    mime_type = mime_types.get(ext, "image/png")
    
    # Read image as bytes
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    prompt = "This image contains a table. Extract it exactly as shown. Use the first row as column headers. Preserve all values. Output ONLY valid CSV format (no extra text, no markdown). Use comma as separator. If no table found, respond with 'NO_TABLE'."
    
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    
    response = client.models.generate_content(
        model=IngestionConfig.GEMINI_MODEL_NAME,
        contents=[{"parts": [{"text": prompt}, {"inline_data": {"mime_type": mime_type, "data": image_b64}}]}]
    )
    if not response.text:
        raise ValueError("Empty response from Gemini")
    
    text = response.text.strip()
    if text == "NO_TABLE":
        raise ValueError("No table detected in image")

    # Remove markdown code block wrapper if present
    if text.startswith("```"):
        text = text[text.find("\n") + 1:] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    df = pd.read_csv(StringIO(text))
    df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)
    logger.info(f"Extracted table: {df.shape[0]} rows × {df.shape[1]} columns")
    return df


def process_image(file_path: str) -> List[pd.DataFrame]:
    """Process image file and return list of DataFrames (one per detected table)."""
    validation = IngestionConfig.validate_file(file_path)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    
    try:
        df = extract_table_with_gemini(file_path)
        df.attrs["source"] = "image"
        df.attrs["table_index"] = 0
        return [df]
    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        raise ValueError(f"Failed to extract tables from image: {str(e)}")
