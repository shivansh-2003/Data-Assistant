"""CSV file handler with auto-detection of delimiter and encoding."""

import pandas as pd
import chardet
from typing import List, Optional
import logging
from .config import IngestionConfig

logger = logging.getLogger(__name__)


def process_csv(file_path: str, delimiter: Optional[str] = None, 
                encoding: Optional[str] = None) -> List[pd.DataFrame]:
    """Process CSV file and return list of DataFrames."""
    validation = IngestionConfig.validate_file(file_path)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    
    # Auto-detect encoding
    if encoding is None:
        with open(file_path, 'rb') as f:
            raw_data = f.read(IngestionConfig.CSV_SAMPLE_SIZE * 100)
        result = chardet.detect(raw_data)
        encoding = result.get('encoding', 'utf-8') if result.get('confidence', 0) >= 0.7 else 'utf-8'
    
    # Auto-detect delimiter
    if delimiter is None:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            sample = ''.join([f.readline() for _ in range(5)])
        delimiter_counts = {d: sample.count(d) for d in IngestionConfig.CSV_DELIMITERS if sample.count(d) > 0}
        delimiter = max(delimiter_counts, key=delimiter_counts.get) if delimiter_counts else ','
    
    # Try reading with multiple encodings
    for enc in [encoding] + [e for e in IngestionConfig.CSV_ENCODINGS if e != encoding]:
        try:
            df = pd.read_csv(file_path, delimiter=delimiter, encoding=enc, header=0,
                           on_bad_lines='skip', engine='python' if delimiter not in [',', '\t'] else 'c',
                           low_memory=False)
            if not df.empty:
                logger.info(f"CSV processed: {len(df)} rows, {len(df.columns)} columns")
                return [df]
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    
    raise ValueError("Failed to read CSV file with any encoding")

