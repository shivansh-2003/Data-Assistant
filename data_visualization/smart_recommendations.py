"""
Smart Chart Recommendations module for Data Assistant Platform.
Uses LangChain agents to analyze data and recommend optimal visualizations.
"""

import os
import asyncio
import pandas as pd
import numpy as np
import json
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI


# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# System message for chart recommendation agent
CHART_RECOMMENDATION_SYSTEM_MESSAGE = """You are a data visualization expert. Your task is to analyze data characteristics and recommend the best chart types for visualization.

Consider these factors:
1. **Data Distribution**: Normal, skewed, categorical distributions
2. **Cardinality**: Number of unique values (low < 10, medium 10-50, high > 50)
3. **Time Series**: Presence of datetime columns or sequential patterns
4. **Correlation Strength**: Relationships between numeric columns
5. **Data Types**: Numeric vs categorical columns
6. **Sample Size**: Number of rows

Chart Type Guidelines:
- **Bar Chart**: Best for categorical X with numeric Y, low-medium cardinality categories
- **Line Chart**: Ideal for time series, trends over time, sequential data
- **Scatter Plot**: Perfect for correlation analysis between two numeric variables
- **Histogram**: Best for distribution analysis of a single numeric column
- **Box Plot**: Excellent for outlier detection, comparing distributions across categories
- **Pie Chart**: Good for proportional breakdown, low cardinality (typically < 10 categories)
- **Heatmap**: Great for correlation matrices, pivot tables, categorical relationships
- **Area Chart**: Similar to line but shows cumulative values, good for stacked comparisons

Provide recommendations ranked by relevance (1 = most relevant). Return 3-5 recommendations."""


def _analyze_dataframe_stats_internal(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Internal function to analyze DataFrame statistics.
    This is called by the tool wrapper.
    """
    stats = {
        "row_count": len(df),
        "column_count": len(df.columns),
        "columns": {},
        "numeric_columns": [],
        "categorical_columns": [],
        "datetime_columns": [],
        "correlations": {}
    }
    
    for col in df.columns:
        col_info = {
            "dtype": str(df[col].dtype),
            "null_count": df[col].isnull().sum(),
            "null_percentage": (df[col].isnull().sum() / len(df)) * 100,
            "unique_count": df[col].nunique(),
            "cardinality": "low" if df[col].nunique() < 10 else ("medium" if df[col].nunique() < 50 else "high")
        }
        
        if pd.api.types.is_numeric_dtype(df[col]):
            stats["numeric_columns"].append(col)
            col_info["mean"] = float(df[col].mean()) if not df[col].isnull().all() else None
            col_info["std"] = float(df[col].std()) if not df[col].isnull().all() else None
            col_info["min"] = float(df[col].min()) if not df[col].isnull().all() else None
            col_info["max"] = float(df[col].max()) if not df[col].isnull().all() else None
            # Skewness detection
            if not df[col].isnull().all():
                skew_val = float(df[col].skew())
                if abs(skew_val) < 0.5:
                    col_info["distribution"] = "normal"
                elif abs(skew_val) < 1:
                    col_info["distribution"] = "moderately_skewed"
                else:
                    col_info["distribution"] = "highly_skewed"
                col_info["skewness"] = skew_val
            else:
                col_info["distribution"] = "unknown"
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            stats["datetime_columns"].append(col)
            col_info["is_temporal"] = True
        else:
            stats["categorical_columns"].append(col)
            # Most common values
            value_counts = df[col].value_counts().head(5)
            col_info["top_values"] = value_counts.to_dict()
        
        stats["columns"][col] = col_info
    
    # Calculate correlations for numeric columns
    if len(stats["numeric_columns"]) > 1:
        numeric_df = df[stats["numeric_columns"]].select_dtypes(include=[np.number])
        if not numeric_df.empty:
            corr_matrix = numeric_df.corr()
            # Get strong correlations (|r| > 0.5)
            strong_corrs = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr_val = corr_matrix.iloc[i, j]
                    if abs(corr_val) > 0.5 and not np.isnan(corr_val):
                        strong_corrs.append({
                            "col1": corr_matrix.columns[i],
                            "col2": corr_matrix.columns[j],
                            "correlation": float(corr_val)
                        })
            stats["correlations"]["strong"] = strong_corrs[:10]  # Limit to top 10
    
    return stats


async def get_chart_recommendations_from_llm(stats: Dict[str, Any], user_query: Optional[str] = None) -> str:
    """
    Get chart recommendations from LLM using direct chat completion.
    
    Args:
        stats: DataFrame statistics dictionary
        user_query: Optional user query
        
    Returns:
        LLM response text
    """
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for smart recommendations. "
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )
    
    # Create OpenAI LLM
    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0.3,  # Lower temperature for more consistent recommendations
    )
    
    # Build analysis prompt
    analysis_prompt = f"""Analyze this DataFrame and recommend the best chart types for visualization.

DataFrame Statistics:
- Rows: {stats['row_count']:,}
- Columns: {stats['column_count']}
- Numeric columns: {', '.join(stats['numeric_columns']) if stats['numeric_columns'] else 'None'}
- Categorical columns: {', '.join(stats['categorical_columns']) if stats['categorical_columns'] else 'None'}
- Datetime columns: {', '.join(stats['datetime_columns']) if stats['datetime_columns'] else 'None'}

Column Details:
"""
    
    for col_name, col_info in stats['columns'].items():
        analysis_prompt += f"\n**{col_name}** ({col_info['dtype']}):\n"
        analysis_prompt += f"  - Unique values: {col_info['unique_count']} (cardinality: {col_info['cardinality']})\n"
        analysis_prompt += f"  - Null values: {col_info['null_count']} ({col_info['null_percentage']:.1f}%)\n"
        
        if col_name in stats['numeric_columns']:
            if col_info.get('distribution'):
                analysis_prompt += f"  - Distribution: {col_info['distribution']}\n"
            if col_info.get('mean') is not None:
                analysis_prompt += f"  - Mean: {col_info['mean']:.2f}, Std: {col_info.get('std', 0):.2f}\n"
        elif col_name in stats['categorical_columns']:
            if col_info.get('top_values'):
                top_vals = list(col_info['top_values'].keys())[:3]
                analysis_prompt += f"  - Top values: {', '.join(str(v) for v in top_vals)}\n"
        elif col_name in stats['datetime_columns']:
            analysis_prompt += f"  - Temporal column detected\n"
    
    if stats['correlations'].get('strong'):
        analysis_prompt += f"\nStrong Correlations (|r| > 0.5):\n"
        for corr in stats['correlations']['strong'][:5]:
            analysis_prompt += f"  - {corr['col1']} ↔ {corr['col2']}: {corr['correlation']:.2f}\n"
    
    if user_query:
        analysis_prompt += f"\nUser Goal: {user_query}\n"
    
    analysis_prompt += "\nBased on this analysis, recommend 3-5 chart types ranked by relevance. For each recommendation, provide:\n"
    analysis_prompt += "1. Chart type (bar, line, scatter, histogram, box, pie, heatmap, area)\n"
    analysis_prompt += "2. Suggested X-axis column (if applicable)\n"
    analysis_prompt += "3. Suggested Y-axis column (if applicable)\n"
    analysis_prompt += "4. Reasoning for why this chart type is suitable\n"
    analysis_prompt += "5. Relevance score (1-5, where 1 is most relevant)\n"
    analysis_prompt += "\nFormat your response as a structured list with clear recommendations."
    
    # Use LLM directly
    response = await llm.ainvoke([
        {"role": "system", "content": CHART_RECOMMENDATION_SYSTEM_MESSAGE},
        {"role": "user", "content": analysis_prompt}
    ])
    
    return response.content


async def get_chart_recommendations_async(df: pd.DataFrame, user_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get smart chart recommendations using LangChain agent.
    
    Args:
        df: pandas DataFrame to analyze
        user_query: Optional user query describing visualization goal
        
    Returns:
        List of chart recommendations with rankings
    """
    if df.empty:
        return []
    
    # Analyze DataFrame using internal function
    stats = _analyze_dataframe_stats_internal(df)
    
    try:
        # Get LLM response
        response_text = await get_chart_recommendations_from_llm(stats, user_query)
        
        # Parse response
        recommendations = _parse_recommendations(response_text, stats)
        
        return recommendations
        
    except Exception as e:
        # Fallback to rule-based recommendations if LLM fails
        import traceback
        print(f"Error in chart recommendation LLM: {e}")
        print(traceback.format_exc())
        return _get_rule_based_recommendations(df, stats)


def _parse_recommendations(response_text: str, stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse LLM response into structured recommendations.
    
    Args:
        response_text: LLM response text
        stats: DataFrame statistics
        
    Returns:
        List of recommendation dictionaries
    """
    recommendations = []
    
    # Try to extract structured recommendations from response
    # This is a simple parser - can be enhanced with more sophisticated parsing
    lines = response_text.split('\n')
    current_rec = None
    
    chart_types = ['bar', 'line', 'scatter', 'histogram', 'box', 'pie', 'heatmap', 'area']
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if line mentions a chart type
        for chart_type in chart_types:
            if chart_type in line.lower():
                if current_rec:
                    recommendations.append(current_rec)
                
                current_rec = {
                    "chart_type": chart_type,
                    "relevance": 5,  # Default
                    "x_column": None,
                    "y_column": None,
                    "reasoning": line
                }
                break
        
        if current_rec:
            # Try to extract X/Y columns
            if 'x' in line.lower() and 'axis' in line.lower():
                for col in stats['columns'].keys():
                    if col.lower() in line.lower():
                        current_rec["x_column"] = col
                        break
            if 'y' in line.lower() and 'axis' in line.lower():
                for col in stats['columns'].keys():
                    if col.lower() in line.lower():
                        current_rec["y_column"] = col
                        break
            
            # Try to extract relevance score
            if 'relevance' in line.lower() or 'score' in line.lower():
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    current_rec["relevance"] = min(int(numbers[0]), 5)
    
    if current_rec:
        recommendations.append(current_rec)
    
    # If parsing failed, use rule-based fallback
    if not recommendations:
        return _get_rule_based_recommendations(None, stats)
    
    # Sort by relevance
    recommendations.sort(key=lambda x: x.get("relevance", 5))
    
    # Limit to top 5
    return recommendations[:5]


def _get_rule_based_recommendations(df: Optional[pd.DataFrame], stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Fallback rule-based recommendations when LLM is unavailable.
    
    Args:
        df: Optional DataFrame (may be None)
        stats: DataFrame statistics
        
    Returns:
        List of recommendation dictionaries
    """
    recommendations = []
    
    # Rule 1: Time series detection
    if stats['datetime_columns']:
        time_col = stats['datetime_columns'][0]
        if stats['numeric_columns']:
            num_col = stats['numeric_columns'][0]
            recommendations.append({
                "chart_type": "line",
                "relevance": 1,
                "x_column": time_col,
                "y_column": num_col,
                "reasoning": f"Time series detected: {time_col} column with numeric values. Line chart is ideal for showing trends over time."
            })
    
    # Rule 2: Correlation analysis
    if stats['correlations'].get('strong'):
        corr = stats['correlations']['strong'][0]
        recommendations.append({
            "chart_type": "scatter",
            "relevance": 2,
            "x_column": corr['col1'],
            "y_column": corr['col2'],
            "reasoning": f"Strong correlation ({corr['correlation']:.2f}) detected between {corr['col1']} and {corr['col2']}. Scatter plot will reveal the relationship."
        })
    
    # Rule 3: Categorical with numeric
    if stats['categorical_columns'] and stats['numeric_columns']:
        cat_col = None
        for col in stats['categorical_columns']:
            if stats['columns'][col]['cardinality'] in ['low', 'medium']:
                cat_col = col
                break
        if not cat_col:
            cat_col = stats['categorical_columns'][0]
        
        num_col = stats['numeric_columns'][0]
        recommendations.append({
            "chart_type": "bar",
            "relevance": 3,
            "x_column": cat_col,
            "y_column": num_col,
            "reasoning": f"Bar chart is perfect for comparing {num_col} across {cat_col} categories."
        })
    
    # Rule 4: Distribution analysis
    if stats['numeric_columns']:
        num_col = stats['numeric_columns'][0]
        dist = stats['columns'][num_col].get('distribution', 'unknown')
        recommendations.append({
            "chart_type": "histogram",
            "relevance": 4,
            "x_column": num_col,
            "y_column": None,
            "reasoning": f"Histogram will show the distribution of {num_col} ({dist} distribution)."
        })
    
    # Rule 5: Low cardinality categorical
    if stats['categorical_columns']:
        for col in stats['categorical_columns']:
            if stats['columns'][col]['cardinality'] == 'low' and stats['columns'][col]['unique_count'] <= 10:
                recommendations.append({
                    "chart_type": "pie",
                    "relevance": 5,
                    "x_column": col,
                    "y_column": None,
                    "reasoning": f"Pie chart suitable for {col} with {stats['columns'][col]['unique_count']} categories (low cardinality)."
                })
                break
    
    # Sort by relevance
    recommendations.sort(key=lambda x: x.get("relevance", 5))
    
    return recommendations[:5]


def get_chart_recommendations(df: pd.DataFrame, user_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Synchronous wrapper for get_chart_recommendations_async.
    
    Args:
        df: pandas DataFrame to analyze
        user_query: Optional user query describing visualization goal
        
    Returns:
        List of chart recommendations with rankings
    """
    try:
        return asyncio.run(get_chart_recommendations_async(df, user_query))
    except Exception as e:
        # Fallback to rule-based if async fails
        stats = _analyze_dataframe_stats_internal(df)
        return _get_rule_based_recommendations(df, stats)

