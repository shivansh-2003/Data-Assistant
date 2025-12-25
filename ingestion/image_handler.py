"""
Simple Table Extraction from Images using Google Gemini API
Outputs clean pandas DataFrame – perfect replacement/alternative for Docling
"""

import os
import pandas as pd
import google.generativeai as genai
from PIL import Image
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------------
# Setup (Get your free API key from https://aistudio.google.com/app/apikey)
# -----------------------------
API_KEY = os.getenv("GEMINI_API_KEY")  # Set this in your environment: export GEMINI_API_KEY="your_key_here"

if not API_KEY:
    raise ValueError("Please set GEMINI_API_KEY environment variable")

genai.configure(api_key=API_KEY)

# Use gemini-1.5-flash (fast & great at tables) or gemini-1.5-pro for complex cases
MODEL_NAME = "gemini-1.5-flash"

def extract_table_with_gemini(image_path: str) -> pd.DataFrame:
    """
    Extract table from image using Gemini and return as pandas DataFrame.
    
    Args:
        image_path: Path to image file (PNG, JPG, etc.)
    
    Returns:
        pandas DataFrame with extracted table
    """
    logger.info(f"Loading image: {image_path}")
    img = Image.open(image_path)
    
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Strong prompt for reliable CSV output
    prompt = """
    This image contains a table. Extract it exactly as shown.
    - Use the first row as column headers.
    - Preserve all values (including 'k' for thousands like 9.8k).
    - Output ONLY valid CSV format (no extra text, no markdown, no explanations).
    - Use comma as separator.
    - If no table found, respond with "NO_TABLE".
    """
    
    logger.info("Sending to Gemini...")
    response = model.generate_content([prompt, img])
    
    if not response.text:
        raise ValueError("Empty response from Gemini")
    
    text = response.text.strip()
    
    if text == "NO_TABLE":
        raise ValueError("No table detected in image")
    
    # Clean response (sometimes has ```csv wrapper)
    if text.startswith("```csv"):
        text = text[6:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    
    logger.info("Raw extracted CSV:\n" + text)
    
    # Convert CSV string to DataFrame
    from io import StringIO
    df = pd.read_csv(StringIO(text))
    
    # Basic cleaning
    df = df.dropna(how='all').dropna(axis=1, how='all').reset_index(drop=True)
    
    logger.info(f"Extracted table: {df.shape[0]} rows × {df.shape[1]} columns")
    return df


# -----------------------------
# Example Usage
# -----------------------------
if __name__ == "__main__":
    # Replace with your image path (e.g., the tabular data screenshot)
    IMAGE_PATH = "tabular_data_image.png"
    
    try:
        df = extract_table_with_gemini(IMAGE_PATH)
        
        print("\n=== Extracted Table ===")
        print(df)
        
        # Save to CSV for further use
        df.to_csv("extracted_with_gemini.csv", index=False)
        print("\nSaved to extracted_with_gemini.csv")
        
    except Exception as e:
        print(f"Error: {e}")