"""Safe pandas code execution without signals (Streamlit-compatible)."""

import logging
import re
from typing import Dict, Any, List
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from difflib import get_close_matches

logger = logging.getLogger(__name__)


def _execute_code_in_thread(code: str, safe_globals: Dict, locals_dict: Dict) -> Any:
    """Execute code in a thread-safe manner."""
    exec(code, safe_globals, locals_dict)
    return locals_dict.get('result')


def execute_pandas_code(code: str, dfs: Dict[str, pd.DataFrame], timeout: int = 10) -> Dict[str, Any]:
    """
    Execute pandas code safely with thread-based timeout.
    
    Args:
        code: Pandas code to execute
        dfs: Dictionary of DataFrames
        timeout: Timeout in seconds (default: 10)
        
    Returns:
        Dict with success, output, and optional error
    """
    try:
        # Prepare safe globals
        safe_globals = {
            "pd": pd,
            "__builtins__": {
                "len": len,
                "sum": sum,
                "min": min,
                "max": max,
                "abs": abs,
                "round": round,
                "int": int,
                "float": float,
                "str": str,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
                "any": any,
                "all": all,
                "print": print,
            }
        }
        
        # Add DataFrames to locals
        locals_dict = {}
        for name, df in dfs.items():
            locals_dict[name] = df
        
        # If there's only one DataFrame, also make it available as 'df'
        if len(dfs) == 1:
            locals_dict['df'] = list(dfs.values())[0]
        
        # Execute with thread-based timeout
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_execute_code_in_thread, code, safe_globals, locals_dict)
            try:
                result = future.result(timeout=timeout)
                
                logger.info("Code executed successfully")
                
                return {
                    "success": True,
                    "output": result,
                    "error": None,
                    "error_type": None,
                    "suggested_columns": None
                }
                
            except FuturesTimeoutError:
                logger.error(f"Code execution timeout after {timeout}s")
                return {
                    "success": False,
                    "output": None,
                    "error": f"Execution timed out (>{timeout} seconds)",
                    "error_type": "timeout",
                    "suggested_columns": None
                }
            
    except Exception as e:
        logger.error(f"Error executing pandas code: {e}", exc_info=True)
        err_msg = str(e)
        error_type = "other"
        suggested_columns = None

        # Detect column-not-found errors and suggest similar column names
        if isinstance(e, KeyError):
            bad_name = str(e).strip("'\"")
            error_type = "column_not_found"
            all_cols = []
            for _df in dfs.values():
                all_cols.extend(_df.columns.tolist())
            all_cols = list(dict.fromkeys(all_cols))
            if bad_name and all_cols:
                suggested_columns = get_close_matches(bad_name, all_cols, n=3, cutoff=0.5)
        elif "not in index" in err_msg or "column" in err_msg.lower() and ("not found" in err_msg.lower() or "not in" in err_msg.lower()):
            # Try to extract column name from error (e.g. " 'revnue' not in index")
            match = re.search(r"['\"]([^'\"]+)['\"].*not in index|KeyError:\s*['\"]?([^'\"]+)", err_msg, re.I)
            bad_name = (match.group(1) or match.group(2) or "").strip() if match else ""
            error_type = "column_not_found"
            all_cols = []
            for _df in dfs.values():
                all_cols.extend(_df.columns.tolist())
            all_cols = list(dict.fromkeys(all_cols))
            if bad_name and all_cols:
                suggested_columns = get_close_matches(bad_name, all_cols, n=3, cutoff=0.5)
            if not suggested_columns and all_cols:
                suggested_columns = all_cols[:3]

        return {
            "success": False,
            "output": None,
            "error": err_msg,
            "error_type": error_type,
            "suggested_columns": suggested_columns
        }

