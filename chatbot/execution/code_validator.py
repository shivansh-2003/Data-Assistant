"""Code validation and sanitization for safe pandas execution."""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Forbidden patterns
FORBIDDEN_PATTERNS = [
    (r'\.plot\s*\(', "Plotting operations (.plot()) are not allowed. Use visualization tools instead."),
    (r'\.to_csv\s*\(', "File writes (.to_csv()) are not allowed."),
    (r'\.to_excel\s*\(', "File writes (.to_excel()) are not allowed."),
    (r'\.to_json\s*\(', "File writes (.to_json()) are not allowed."),
    (r'\.to_parquet\s*\(', "File writes (.to_parquet()) are not allowed."),
    (r'open\s*\(', "File operations (open()) are not allowed."),
    (r'__import__', "Dynamic imports are not allowed."),
    (r'eval\s*\(', "eval() is not allowed."),
    (r'exec\s*\(', "exec() is not allowed."),
    (r'subprocess', "Subprocess operations are not allowed."),
    (r'os\.', "OS operations are not allowed."),
    (r'sys\.', "System operations are not allowed."),
    (r'import\s+os', "OS module imports are not allowed."),
    (r'import\s+sys', "System module imports are not allowed."),
    (r'import\s+subprocess', "Subprocess imports are not allowed."),
]


def validate_code(code: str) -> Tuple[bool, Optional[str]]:
    """
    Validate code for forbidden operations.
    
    Args:
        code: Code string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    code_lower = code.lower()
    
    for pattern, error_msg in FORBIDDEN_PATTERNS:
        if re.search(pattern, code_lower):
            logger.warning(f"Code validation failed: {error_msg}")
            return False, error_msg
    
    return True, None


def ensure_result_variable(code: str) -> Tuple[str, bool]:
    """
    Ensure code assigns final result to 'result' variable.
    
    Checks if code assigns to 'result'. If not, tries to add assignment.
    This is best-effort; complex cases may need manual fixing.
    
    Args:
        code: Code string
        
    Returns:
        Tuple of (modified_code, was_modified)
    """
    code_lines = [line for line in code.strip().split('\n') if line.strip() and not line.strip().startswith('#')]
    
    if not code_lines:
        return code, False
    
    # Check if 'result' is already assigned anywhere
    has_result = any(re.search(r'result\s*=', line) for line in code_lines)
    
    if has_result:
        return code, False
    
    # Try to find the last meaningful line (assignment or expression)
    last_line = code_lines[-1].strip()
    
    # Skip comments and empty lines
    if not last_line or last_line.startswith('#'):
        if len(code_lines) > 1:
            last_line = code_lines[-2].strip()
        else:
            return code, False
    
    # If last line is an expression (not assignment), wrap it
    if last_line and not re.search(r'^\s*\w+\s*=', last_line):
        # Check if it's a valid pandas expression
        pandas_keywords = [
            'df[', 'df.', 'groupby', '.mean()', '.sum()', '.count()', 
            '.max()', '.min()', '.agg(', '.corr()', '.reset_index()',
            '.head(', '.tail(', '.nlargest(', '.nsmallest(', '.loc[',
            '.iloc[', '.sort_values(', '.dropna(', '.fillna('
        ]
        
        if any(keyword in last_line for keyword in pandas_keywords):
            # Check if it's already a complete statement (ends with something)
            if last_line.endswith(')') or last_line.endswith(']') or '=' in last_line:
                modified_code = code.rstrip() + f"\nresult = {last_line}"
                logger.info("Added result variable assignment")
                return modified_code, True
    
    # If we can't auto-fix, return original (will fail at execution)
    logger.warning("Could not ensure result variable assignment - code may fail")
    return code, False


def sanitize_code(code: str) -> Tuple[str, Optional[str]]:
    """
    Validate and sanitize code.
    
    Args:
        code: Raw code string
        
    Returns:
        Tuple of (sanitized_code, error_message)
    """
    # Validate for forbidden patterns
    is_valid, error = validate_code(code)
    if not is_valid:
        return code, error
    
    # Ensure result variable
    sanitized, _ = ensure_result_variable(code)
    
    return sanitized, None
