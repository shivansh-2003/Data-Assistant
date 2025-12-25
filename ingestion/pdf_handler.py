"""
PDF file handler for processing PDF files containing tables.
Uses Docling for multi-page PDF table extraction with OCR support.
"""

import pandas as pd
from typing import List, Dict, Optional
import logging
from pathlib import Path

from .config import IngestionConfig

logger = logging.getLogger(__name__)

# Try to import Docling, handle gracefully if not available
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning("Docling not available. Install with: pip install docling")


def extract_tables_with_docling(file_path: str) -> List[Dict]:
    """
    Extract tables from PDF using Docling (supports multi-page).
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        List of table dictionaries with extracted data and metadata
    """
    if not DOCLING_AVAILABLE:
        raise ImportError("Docling is not installed. Please install it with: pip install docling")
    
    try:
        # Initialize Docling converter
        converter = DocumentConverter(
            format=InputFormat.PDF,
            ocr_enabled=IngestionConfig.DOCLING_OCR_ENABLED,
            table_extraction_mode=IngestionConfig.DOCLING_TABLE_EXTRACTION_MODE,
            layout_preservation=IngestionConfig.DOCLING_LAYOUT_PRESERVATION
        )
        
        # Convert document and extract tables
        result = converter.convert(file_path)
        
        # Extract tables from result
        tables = []
        
        # Docling typically returns a document structure with tables
        # The exact structure may vary, but typically includes a 'tables' attribute
        if hasattr(result, 'tables') and result.tables:
            for idx, table in enumerate(result.tables):
                page_num = getattr(table, 'page_number', idx + 1)
                tables.append({
                    'data': table,
                    'confidence': getattr(table, 'confidence', 1.0),
                    'page_number': page_num,
                    'table_index': idx
                })
        elif hasattr(result, 'content'):
            # Alternative structure - tables might be in content
            content = result.content
            if isinstance(content, list):
                table_idx = 0
                for item in content:
                    if hasattr(item, 'type') and item.type == 'table':
                        page_num = getattr(item, 'page_number', None)
                        tables.append({
                            'data': item,
                            'confidence': getattr(item, 'confidence', 1.0),
                            'page_number': page_num,
                            'table_index': table_idx
                        })
                        table_idx += 1
        
        logger.info(f"Extracted {len(tables)} tables from PDF")
        return tables
        
    except Exception as e:
        logger.error(f"Docling extraction failed: {str(e)}")
        raise ValueError(f"Failed to extract tables from PDF using Docling: {str(e)}")


def table_to_dataframe(table_data: Dict) -> pd.DataFrame:
    """
    Convert extracted table data to pandas DataFrame.
    
    Args:
        table_data: Table data dictionary from Docling
        
    Returns:
        pandas DataFrame
    """
    try:
        table = table_data.get('data')
        
        # Handle different table structures from Docling
        if hasattr(table, 'rows'):
            # Table has rows attribute
            rows = []
            for row in table.rows:
                cells = [cell.text if hasattr(cell, 'text') else str(cell) for cell in row.cells]
                rows.append(cells)
            
            if rows:
                # First row as header if available
                if len(rows) > 1:
                    df = pd.DataFrame(rows[1:], columns=rows[0])
                else:
                    df = pd.DataFrame(rows)
                return df
        
        elif hasattr(table, 'to_dict'):
            # Table can be converted to dict
            return pd.DataFrame(table.to_dict())
        
        elif isinstance(table, list):
            # Table is a list of rows
            if table and isinstance(table[0], list):
                if len(table) > 1:
                    df = pd.DataFrame(table[1:], columns=table[0])
                else:
                    df = pd.DataFrame(table)
                return df
        
        # Fallback: try to create DataFrame directly
        return pd.DataFrame(table)
        
    except Exception as e:
        logger.error(f"Failed to convert table to DataFrame: {str(e)}")
        raise ValueError(f"Failed to convert table to DataFrame: {str(e)}")


def process_pdf(file_path: str) -> List[pd.DataFrame]:
    """
    Process PDF file and extract tables from all pages using Docling.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        List of DataFrames, one for each extracted table (across all pages)
        
    Raises:
        ValueError: If file cannot be processed
        FileNotFoundError: If file doesn't exist
        ImportError: If Docling is not installed
    """
    try:
        # Validate file
        validation = IngestionConfig.validate_file(file_path)
        if not validation["valid"]:
            raise ValueError(validation["error"])
        
        # Check if Docling is available
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "Docling is required for PDF processing. "
                "Install with: pip install docling"
            )
        
        # Extract tables using Docling (handles multi-page automatically)
        extracted_tables = extract_tables_with_docling(file_path)
        
        if not extracted_tables:
            raise ValueError(IngestionConfig.ERROR_NO_TABLES_FOUND)
        
        # Convert tables to DataFrames
        dataframes = []
        for table_data in extracted_tables:
            try:
                confidence = table_data.get('confidence', 1.0)
                page_num = table_data.get('page_number', None)
                table_idx = table_data.get('table_index', len(dataframes))
                
                # Filter by confidence threshold
                if confidence < IngestionConfig.DOCLING_MIN_TABLE_CONFIDENCE:
                    logger.warning(
                        f"Skipping table {table_idx} (page {page_num}) "
                        f"due to low confidence: {confidence:.2f}"
                    )
                    continue
                
                df = table_to_dataframe(table_data)
                
                # Clean up empty DataFrames
                if not df.empty:
                    df = df.dropna(how='all').dropna(axis=1, how='all')
                    
                    if not df.empty:
                        # Store metadata in DataFrame attributes
                        df.attrs['confidence'] = confidence
                        df.attrs['page_number'] = page_num
                        df.attrs['table_index'] = table_idx
                        df.attrs['source'] = 'pdf'
                        
                        dataframes.append(df)
                        logger.info(
                            f"Extracted table {table_idx} from page {page_num}: "
                            f"{len(df)} rows, {len(df.columns)} columns"
                        )
                        
            except Exception as e:
                logger.warning(f"Failed to process table: {str(e)}")
                continue
        
        if not dataframes:
            raise ValueError("No valid tables extracted from PDF")
        
        return dataframes
        
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except ImportError:
        raise
    except Exception as e:
        logger.error(f"Error processing PDF file {file_path}: {str(e)}")
        raise ValueError(f"Failed to process PDF file: {str(e)}")

