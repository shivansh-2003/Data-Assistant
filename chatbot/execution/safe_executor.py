"""Safe pandas code execution using LangChain pandas agent."""

import logging
from typing import Dict, Any
import pandas as pd
import signal
import os

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Exception raised when code execution times out."""
    pass


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutException("Code execution timed out")


def execute_pandas_code(code: str, dfs: Dict[str, pd.DataFrame], timeout: int = 5) -> Dict[str, Any]:
    """
    Execute pandas code safely with timeout.
    
    Args:
        code: Pandas code to execute
        dfs: Dictionary of DataFrames
        timeout: Timeout in seconds
        
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
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
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
        
        # Set timeout (Unix-based systems only)
        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        try:
            # Execute code
            exec(code, safe_globals, locals_dict)
            
            # Get result
            result = locals_dict.get('result')
            
            # Cancel timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            
            logger.info("Code executed successfully")
            
            return {
                "success": True,
                "output": result,
                "error": None
            }
            
        except TimeoutException as e:
            logger.error(f"Code execution timeout: {e}")
            return {
                "success": False,
                "output": None,
                "error": "Execution timed out (>5 seconds)"
            }
            
    except Exception as e:
        logger.error(f"Error executing pandas code: {e}", exc_info=True)
        return {
            "success": False,
            "output": None,
            "error": str(e)
        }
    finally:
        # Ensure timeout is cancelled
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)

