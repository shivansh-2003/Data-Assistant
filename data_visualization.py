"""
Visualization Centre module for Data Assistant Platform.
Provides zero-latency chart generation using Plotly with session data integration.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Optional
import io
import requests

# Import session utilities from app.py
# We'll use the same SESSION_ENDPOINT pattern
SESSION_ENDPOINT = "http://localhost:8001/api/session"


def get_dataframe_from_session(session_id: str, table_name: str) -> Optional[pd.DataFrame]:
    """
    Fetch session data and convert preview to DataFrame.
    Uses preview data (first 10 rows) for visualization.
    For full data, would need to fetch with format=full and deserialize.
    
    Args:
        session_id: Session ID
        table_name: Name of the table to fetch
        
    Returns:
        DataFrame or None if error
    """
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        tables = data.get("tables", {})
        if table_name not in tables:
            return None
        
        table_info = tables[table_name]
        preview_data = table_info.get("preview", [])
        
        if not preview_data:
            return None
        
        # Convert preview to DataFrame
        df = pd.DataFrame(preview_data)
        
        # Note: This uses preview data (first 10 rows). For full dataset visualization,
        # we would need to fetch format=full and deserialize the base64 pickle data.
        # For now, preview is sufficient for demonstration.
        
        return df
        
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


def generate_chart(df: pd.DataFrame, chart_type: str, x_col: Optional[str], 
                   y_col: Optional[str], agg_func: str = 'none', 
                   color_col: Optional[str] = None) -> go.Figure:
    """
    Generate Plotly figure based on user selections.
    Supports: bar, line, scatter, area, box, histogram, pie, heatmap.
    """
    if df.empty:
        return go.Figure().add_annotation(
            text="No data available—check your manipulations!", 
            showarrow=False
        )
    
    # Apply aggregation if needed
    if agg_func != 'none' and y_col and y_col in df.columns:
        if chart_type in ['bar', 'line', 'area']:
            if x_col and x_col in df.columns:
                df_agg = df.groupby(x_col)[y_col].agg(agg_func).reset_index()
            else:
                df_agg = df
        else:
            df_agg = df  # No agg for scatter/hist/etc.
    else:
        df_agg = df
    
    # Chart-specific generation
    try:
        if chart_type == 'bar':
            if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
                fig = px.bar(df_agg, x=x_col, y=y_col, color=color_col if color_col and color_col != 'None' else None,
                           title=f"Bar Chart: {y_col} by {x_col}")
            elif x_col and x_col in df_agg.columns:
                # Count chart if only X is provided
                value_counts = df_agg[x_col].value_counts().head(20)  # Limit to top 20 for performance
                fig = px.bar(x=value_counts.index, y=value_counts.values, 
                           title=f"Bar Chart: Count by {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Bar chart requires at least X column", showarrow=False)
                
        elif chart_type == 'line':
            if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
                fig = px.line(df_agg, x=x_col, y=y_col, color=color_col if color_col and color_col != 'None' else None,
                            title=f"Line Chart: {y_col} over {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Line chart requires both X and Y columns", showarrow=False)
                
        elif chart_type == 'scatter':
            if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
                fig = px.scatter(df_agg, x=x_col, y=y_col, color=color_col if color_col and color_col != 'None' else None,
                               title=f"Scatter: {y_col} vs {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Scatter chart requires both X and Y columns", showarrow=False)
                
        elif chart_type == 'area':
            if y_col and y_col in df_agg.columns and x_col and x_col in df_agg.columns:
                fig = px.area(df_agg, x=x_col, y=y_col, color=color_col if color_col and color_col != 'None' else None,
                            title=f"Area Chart: {y_col} over {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Area chart requires both X and Y columns", showarrow=False)
                
        elif chart_type == 'box':
            if y_col and y_col in df_agg.columns:
                fig = px.box(df_agg, x=x_col if x_col and x_col != 'None' else None, y=y_col,
                           color=color_col if color_col and color_col != 'None' else None,
                           title=f"Box Plot: {y_col}" + (f" by {x_col}" if x_col and x_col != 'None' else ""))
            else:
                fig = go.Figure().add_annotation(text="Box plot requires Y column", showarrow=False)
                
        elif chart_type == 'histogram':
            if x_col and x_col in df_agg.columns:
                fig = px.histogram(df_agg, x=x_col, color=color_col if color_col and color_col != 'None' else None,
                                 title=f"Histogram: Distribution of {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Histogram requires X column", showarrow=False)
                
        elif chart_type == 'pie':
            if y_col and y_col in df_agg.columns:
                df_pie = df_agg.groupby(y_col).size().reset_index(name='count')
                fig = px.pie(df_pie, values='count', names=y_col, title=f"Pie: Distribution of {y_col}")
            elif x_col and x_col in df_agg.columns:
                value_counts = df_agg[x_col].value_counts()
                fig = px.pie(values=value_counts.values, names=value_counts.index, title=f"Pie: Distribution of {x_col}")
            else:
                fig = go.Figure().add_annotation(text="Pie chart requires at least one column", showarrow=False)
                
        elif chart_type == 'heatmap':
            if x_col and x_col in df_agg.columns and y_col and y_col in df_agg.columns:
                # Create pivot table for heatmap
                try:
                    # Sample data for performance
                    df_sample = df_agg.head(1000)
                    pivot = df_sample.pivot_table(
                        values=y_col if pd.api.types.is_numeric_dtype(df_sample[y_col]) else None,
                        index=x_col,
                        aggfunc='mean' if pd.api.types.is_numeric_dtype(df_sample[y_col]) else 'count'
                    )
                    if pivot.empty:
                        fig = go.Figure().add_annotation(text="Cannot create heatmap with selected columns", showarrow=False)
                    else:
                        fig = px.imshow(pivot, title=f"Heatmap: {y_col} by {x_col}")
                except Exception:
                    fig = go.Figure().add_annotation(text="Heatmap needs numeric data—try different columns!", showarrow=False)
            else:
                fig = go.Figure().add_annotation(text="Heatmap needs 2+ dimensions—try numeric cols!", showarrow=False)
        else:
            fig = go.Figure().add_annotation(text="Chart type not supported yet—coming soon!", showarrow=False)
        
        # Theme for dark/light mode compatibility
        try:
            # Try to detect Streamlit theme
            theme = st.get_option("theme.base")
            if theme == "dark":
                fig.update_layout(template='plotly_dark')
            else:
                fig.update_layout(template='plotly_white')
        except:
            # Default to white theme
            fig.update_layout(template='plotly_white')
        
        return fig
        
    except Exception as e:
        return go.Figure().add_annotation(
            text=f"Error generating chart: {str(e)}", 
            showarrow=False
        )


def render_visualization_tab():
    """Render the Visualization Centre tab content."""
    st.header("📈 Visualization Centre")
    st.markdown("**Select columns below to build charts instantly. Pick aggregation for grouped data.**")
    
    session_id = st.session_state.get("current_session_id")
    
    # Check if session exists
    if not session_id:
        st.warning("⚠️ No active session found. Please upload a file in the Upload tab first.")
        st.info("💡 After uploading a file, you can create visualizations here.")
        return
    
    # Get session tables
    try:
        response = requests.get(
            f"{SESSION_ENDPOINT}/{session_id}/tables",
            params={"format": "summary"},
            timeout=10
        )
        response.raise_for_status()
        tables_data = response.json()
    except Exception as e:
        st.error(f"❌ Error loading session data: {e}")
        return
    
    tables = tables_data.get("tables", {})
    if not tables:
        st.warning("⚠️ No tables found in session. Please upload a file first.")
        return
    
    # Table selection
    table_names = list(tables.keys())
    if len(table_names) > 1:
        selected_table = st.selectbox("Select Table to Visualize", table_names, key="viz_table_select")
    else:
        selected_table = table_names[0]
    
    # Get DataFrame from session
    df = get_dataframe_from_session(session_id, selected_table)
    
    if df is None or df.empty:
        st.warning("⚠️ No data available for visualization. The table may be empty.")
        return
    
    # Show data info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Rows", f"{len(df):,}")
    with col2:
        st.metric("Columns", len(df.columns))
    with col3:
        st.metric("Table", selected_table)
    
    st.divider()
    
    # Chart Controls in main area (using expander for cleaner UI)
    with st.expander("📊 Chart Controls", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Chart type selector
            chart_type = st.selectbox(
                "Chart Type",
                options=['bar', 'line', 'scatter', 'area', 'box', 'histogram', 'pie', 'heatmap'],
                index=0,
                help="Bar for categories, Line for trends, Scatter for correlations, etc.",
                key="viz_chart_type"
            )
        
        with col2:
            # Column selectors - smart defaults
            cols = ['None'] + df.columns.tolist()
            # Default to first categorical column for X, or first column if none
            default_x_idx = 0
            if len(df.columns) > 0:
                # Try to find a good default (categorical or first column)
                for i, col in enumerate(df.columns):
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        default_x_idx = i + 1  # +1 because 'None' is at index 0
                        break
                if default_x_idx == 0 and len(df.columns) > 0:
                    default_x_idx = 1  # Use first column as default
            
            x_col = st.selectbox("X-Axis (or Category)", options=cols, index=default_x_idx, key="viz_x_col")
        
        with col3:
            # Default to first numeric column for Y, or second column if none
            default_y_idx = 0
            if len(df.columns) > 1:
                # Try to find a numeric column
                for i, col in enumerate(df.columns):
                    if pd.api.types.is_numeric_dtype(df[col]):
                        default_y_idx = i + 1  # +1 because 'None' is at index 0
                        break
                if default_y_idx == 0 and len(df.columns) > 1:
                    default_y_idx = 2 if len(df.columns) > 1 else 1  # Use second column as default
            
            y_col = st.selectbox("Y-Axis (or Value)", options=cols, index=default_y_idx, key="viz_y_col")
        
        with col4:
            color_col = st.selectbox("Color/Group By (Optional)", options=cols, index=0, key="viz_color_col")
        
        # Aggregation row
        col_agg1, col_agg2 = st.columns([1, 3])
        with col_agg1:
            if y_col != 'None' and y_col in df.columns and pd.api.types.is_numeric_dtype(df[y_col]):
                agg_options = ['none', 'sum', 'mean', 'count', 'min', 'max']
                agg_func = st.selectbox("Aggregate Y By", options=agg_options, index=0, key="viz_agg")
            else:
                agg_func = 'none'
                st.caption("Aggregation\n(requires numeric Y)")
        with col_agg2:
            st.caption("💡 Tip: Select columns above to generate chart instantly")
    
    # Main area: Render chart
    # Check if we have valid column selections for the chart type
    can_render = False
    validation_message = None
    
    if chart_type in ['line', 'scatter', 'area']:
        if x_col != 'None' and y_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ This chart type requires both X and Y columns. Please select both."
    elif chart_type == 'box':
        if y_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ Box plot requires Y column. Please select a Y-axis column."
    elif chart_type == 'histogram':
        if x_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ Histogram requires X column. Please select an X-axis column."
    elif chart_type == 'pie':
        if x_col != 'None' or y_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ Pie chart requires at least one column. Please select X or Y column."
    elif chart_type == 'heatmap':
        if x_col != 'None' and y_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ Heatmap requires both X and Y columns. Please select both."
    else:  # bar chart
        if x_col != 'None' or y_col != 'None':
            can_render = True
        else:
            validation_message = "⚠️ Please select at least one column (X or Y)."
    
    if validation_message:
        st.warning(validation_message)
    
    if can_render:
        with st.spinner("Generating chart..."):
            fig = generate_chart(
                df, 
                chart_type, 
                x_col if x_col != 'None' else None,
                y_col if y_col != 'None' else None, 
                agg_func,
                color_col if color_col != 'None' else None
            )
        
        # Display interactive Plotly chart
        st.plotly_chart(fig, width='stretch', theme="streamlit")
        
        # Data table below chart (optional toggle)
        if st.checkbox("Show Raw Data Preview", key="viz_table"):
            st.dataframe(df, width='stretch', height=300)
        
        # One-click Exports
        st.divider()
        st.subheader("📥 Export Chart")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            try:
                img_bytes = fig.to_image(format="png", width=1200, height=800)
                st.download_button(
                    "📥 Download PNG", 
                    img_bytes, 
                    f"chart_{chart_type}_{selected_table}.png", 
                    "image/png",
                    key="download_png",
                    width='stretch'
                )
            except Exception as e:
                st.error(f"PNG export failed: {e}")
                st.caption("💡 Install kaleido: `pip install kaleido`")
        
        with col2:
            try:
                svg_bytes = fig.to_image(format="svg", width=1200, height=800)
                st.download_button(
                    "📐 Download SVG", 
                    svg_bytes, 
                    f"chart_{chart_type}_{selected_table}.svg", 
                    "image/svg+xml",
                    key="download_svg",
                    width='stretch'
                )
            except Exception as e:
                st.error(f"SVG export failed: {e}")
                st.caption("💡 Install kaleido: `pip install kaleido`")
        
        with col3:
            try:
                html_str = fig.to_html(full_html=False)
                st.download_button(
                    "🌐 Download HTML", 
                    html_str.encode(), 
                    f"chart_{chart_type}_{selected_table}.html", 
                    "text/html",
                    key="download_html",
                    width='stretch'
                )
            except Exception as e:
                st.error(f"HTML export failed: {e}")
    
    elif not validation_message:
        # No columns selected and no validation message
        st.info("👆 Select at least one column to get started. Try selecting a column for X or Y axis!")
        
        # Show column suggestions
        numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
        categorical_cols = [col for col in df.columns if not pd.api.types.is_numeric_dtype(df[col])]
        
        if numeric_cols or categorical_cols:
            with st.expander("💡 Quick Start Suggestions", expanded=False):
                if categorical_cols:
                    st.write(f"**For X-Axis (Category):** Try `{categorical_cols[0]}`")
                if numeric_cols:
                    st.write(f"**For Y-Axis (Value):** Try `{numeric_cols[0]}`")
                if len(categorical_cols) > 0 and len(numeric_cols) > 0:
                    st.write(f"**Example:** X=`{categorical_cols[0]}`, Y=`{numeric_cols[0]}`, Chart=`Bar`")

