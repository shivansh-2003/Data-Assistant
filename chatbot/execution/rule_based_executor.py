"""Rule-based executor for simple queries (fallback before LLM)."""

import logging
import re
from typing import Dict, Any, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)


def detect_simple_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if query can be handled by rule-based executor.
    
    Args:
        query: User query
        
    Returns:
        Tuple of (is_simple, operation_type)
    """
    query_lower = query.lower().strip()
    
    # Simple aggregation patterns
    simple_patterns = {
        "mean": r"(average|mean|avg)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        "sum": r"sum\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        "count": r"(count|how many|number of)\s+(?:rows|records|items)?",
        "max": r"(maximum|max|highest|largest)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        "min": r"(minimum|min|lowest|smallest)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
    }
    
    for op_type, pattern in simple_patterns.items():
        if re.search(pattern, query_lower):
            return True, op_type
    
    # Simple filtering (very basic)
    if re.search(r"^(show|list|find|filter)\s+.*(?:where|with|having)", query_lower):
        # Too complex for rule-based, needs LLM
        return False, None
    
    return False, None


def extract_column_name(query: str, operation: str) -> Optional[str]:
    """
    Extract column name from query for simple operations.
    
    Args:
        query: User query
        operation: Operation type (mean, sum, max, min)
        
    Returns:
        Column name or None
    """
    query_lower = query.lower()
    
    # Patterns to extract column name
    patterns = [
        rf"{operation}\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        rf"(?:average|mean|avg)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        rf"(?:maximum|max|highest|largest)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        rf"(?:minimum|min|lowest|smallest)\s+(?:of\s+)?([a-zA-Z_][a-zA-Z0-9_]*)",
        rf"([a-zA-Z_][a-zA-Z0-9_]*)\s+(?:average|mean|avg)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            col = match.group(1)
            # Filter out common words
            if col not in ["the", "a", "an", "all", "each", "every"]:
                return col
    
    return None


def execute_simple_query(
    query: str,
    df: pd.DataFrame,
    operation: str
) -> Optional[Any]:
    """
    Execute simple query using rule-based logic.
    
    Args:
        query: User query
        df: DataFrame to query
        operation: Operation type (mean, sum, count, max, min)
        
    Returns:
        Result value or None if cannot execute
    """
    try:
        if operation == "count":
            result = len(df)
            logger.info(f"Rule-based count: {result}")
            return result
        
        # Extract column name
        col_name = extract_column_name(query, operation)
        if not col_name:
            return None
        
        # Check if column exists
        if col_name not in df.columns:
            # Try case-insensitive match
            col_match = [c for c in df.columns if c.lower() == col_name.lower()]
            if col_match:
                col_name = col_match[0]
            else:
                logger.warning(f"Column '{col_name}' not found for rule-based execution")
                return None
        
        # Execute operation
        if operation == "mean":
            result = df[col_name].mean()
        elif operation == "sum":
            result = df[col_name].sum()
        elif operation == "max":
            result = df[col_name].max()
        elif operation == "min":
            result = df[col_name].min()
        else:
            return None
        
        logger.info(f"Rule-based {operation} on {col_name}: {result}")
        return result
        
    except Exception as e:
        logger.warning(f"Rule-based execution failed: {e}")
        return None


def try_rule_based_execution(
    query: str,
    dfs: Dict[str, pd.DataFrame]
) -> Optional[Dict[str, Any]]:
    """
    Try to execute query using rule-based logic.
    
    Args:
        query: User query
        dfs: Dictionary of DataFrames
        
    Returns:
        Execution result dict or None if cannot execute rule-based
    """
    # Detect if query is simple
    is_simple, operation = detect_simple_query(query)
    if not is_simple or not operation:
        return None
    
    # Use primary DataFrame
    if len(dfs) == 1:
        df = list(dfs.values())[0]
    elif 'df' in dfs:
        df = dfs['df']
    else:
        # Can't determine which DataFrame to use
        return None
    
    # Execute
    result = execute_simple_query(query, df, operation)
    if result is None:
        return None
    
    return {
        "success": True,
        "output": result,
        "error": None,
        "error_type": None,
        "suggested_columns": None,
        "execution_method": "rule_based"
    }
