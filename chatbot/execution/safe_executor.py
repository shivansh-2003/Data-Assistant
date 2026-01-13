"""Safe pandas code execution without signals (Streamlit-compatible)."""

import logging
from typing import Dict, Any
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time

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
                    "error": None
                }
                
            except FuturesTimeoutError:
                logger.error(f"Code execution timeout after {timeout}s")
                return {
                    "success": False,
                    "output": None,
                    "error": f"Execution timed out (>{timeout} seconds)"
                }
            
    except Exception as e:
        logger.error(f"Error executing pandas code: {e}", exc_info=True)
        return {
            "success": False,
            "output": None,
            "error": str(e)
        }

