"""Base classes and utilities for prompt management."""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class PromptTemplate:
    """Base class for prompt templates with versioning and safe substitution."""
    
    VERSION = "1.0.0"
    
    def __init__(self, template_str: str, version: Optional[str] = None):
        """
        Initialize a prompt template.
        
        Args:
            template_str: Template string with {placeholders}
            version: Optional version string (defaults to class VERSION)
        """
        self.template_str = template_str
        self.version = version or self.VERSION
    
    def format(self, **kwargs: Any) -> str:
        """
        Format the template with provided variables using str.format().
        
        Args:
            **kwargs: Variables to substitute in template
            
        Returns:
            Formatted prompt string
            
        Raises:
            KeyError: If required placeholder is missing
        """
        try:
            return self.template_str.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing required template variable: {e}")
            raise
    
    def get_version(self) -> str:
        """Get the version of this prompt."""
        return self.version
    
    def __str__(self) -> str:
        return f"PromptTemplate(v{self.version})"


def truncate_schema(schema: Dict[str, Any], max_tables: int = 5, max_columns_per_table: int = 20) -> Dict[str, Any]:
    """
    Truncate large schema to prevent prompt bloat.
    
    Args:
        schema: Full schema dictionary
        max_tables: Maximum number of tables to include
        max_columns_per_table: Maximum columns per table
        
    Returns:
        Truncated schema dictionary
    """
    if not schema or not isinstance(schema, dict):
        return schema
    
    tables = schema.get("tables", {})
    if not tables:
        return schema
    
    truncated = {"tables": {}}
    for i, (table_name, table_info) in enumerate(list(tables.items())[:max_tables]):
        if isinstance(table_info, dict):
            cols = table_info.get("columns", [])
            if isinstance(cols, list) and len(cols) > max_columns_per_table:
                truncated["tables"][table_name] = {
                    **table_info,
                    "columns": cols[:max_columns_per_table],
                    "_truncated": f"{len(cols) - max_columns_per_table} more columns..."
                }
            else:
                truncated["tables"][table_name] = table_info
    
    if len(tables) > max_tables:
        truncated["_truncated_tables"] = f"{len(tables) - max_tables} more tables..."
    
    return truncated
