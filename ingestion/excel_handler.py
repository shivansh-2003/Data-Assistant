"""Excel file handler for processing all sheets in a workbook."""

import pandas as pd
from typing import List, Optional
import logging
from pathlib import Path
from .config import IngestionConfig

logger = logging.getLogger(__name__)


def process_excel(file_path: str, sheet_name: Optional[str] = None) -> List[pd.DataFrame]:
    """Process Excel file and return list of DataFrames (one per sheet)."""
    validation = IngestionConfig.validate_file(file_path)
    if not validation["valid"]:
        raise ValueError(validation["error"])
    
    engine = 'xlrd' if Path(file_path).suffix.lower() == '.xls' else IngestionConfig.EXCEL_ENGINE
    dataframes = []
    
    if sheet_name is None:
        excel_file = pd.ExcelFile(file_path, engine=engine)
        for sheet in excel_file.sheet_names:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet, engine=engine, header=IngestionConfig.EXCEL_HEADER_ROW)
                df = df.dropna(how='all').dropna(axis=1, how='all')
                if not df.empty:
                    df.attrs['sheet_name'] = sheet
                    dataframes.append(df)
                    logger.info(f"Sheet '{sheet}': {len(df)} rows, {len(df.columns)} columns")
            except Exception as e:
                logger.warning(f"Failed to read sheet '{sheet}': {e}")
        excel_file.close()
    else:
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine, header=IngestionConfig.EXCEL_HEADER_ROW)
        df = df.dropna(how='all').dropna(axis=1, how='all')
        if not df.empty:
            dataframes.append(df)
    
    if not dataframes:
        raise ValueError("No valid data found in Excel file")
    return dataframes

