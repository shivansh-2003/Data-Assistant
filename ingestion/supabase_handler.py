"""
Supabase handler for importing all tables via Postgres connection string.
"""

import logging
from typing import List

import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def load_supabase_tables(connection_string: str, schema: str = "public") -> List[pd.DataFrame]:
    """
    Load all tables from a Supabase project using a Postgres connection string.
    
    Args:
        connection_string: Postgres connection string for Supabase
        schema: Schema name to load tables from (default: public)
        
    Returns:
        List of DataFrames, one per table
    """
    if not connection_string:
        raise ValueError("Supabase connection string is required")
    
    tables: List[pd.DataFrame] = []
    engine = create_engine(connection_string)
    
    query_tables = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    
    with engine.connect() as conn:
        result = conn.execute(query_tables, {"schema": schema})
        table_names = [row[0] for row in result.fetchall()]
        
        for table_name in table_names:
            try:
                df = pd.read_sql(
                    text(f'SELECT * FROM "{schema}"."{table_name}"'),
                    conn
                )
                df.attrs["table_name"] = table_name
                tables.append(df)
            except Exception as e:
                logger.warning(f"Failed to load table {table_name}: {e}")
                continue
    
    return tables

