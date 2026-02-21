"""
Dynamic Dashboard Builder module for Data Assistant Platform.
Enables multi-chart layouts with flexible grid templates and chart pinning.
"""

import streamlit as st
import plotly.graph_objects as go
from typing import Dict, Any, Optional
import pandas as pd
import json


class DashboardBuilder:
    """Builder for creating multi-chart dashboards with flexible layouts."""
    
    def __init__(self):
        """Initialize DashboardBuilder instance."""
        self._initialize_state()
    
    def _initialize_state(self):
        """Initialize dashboard state variables."""
        if 'dashboard_charts' not in st.session_state:
            st.session_state['dashboard_charts'] = []
        if 'dashboard_layout' not in st.session_state:
            st.session_state['dashboard_layout'] = '2x2'  # Default layout
        if 'dashboard_active' not in st.session_state:
            st.session_state['dashboard_active'] = False
    
    def get_layout_grid(self, layout: str) -> tuple:
        """
        Get grid dimensions from layout string.
        
        Args:
            layout: Layout string like '2x2', '3x3', '2x3', etc.
            
        Returns:
            Tuple of (rows, cols)
        """
        try:
            rows, cols = map(int, layout.split('x'))
            return (rows, cols)
        except:
            return (2, 2)  # Default
    
    def pin_chart(
        self,
        chart_config: Dict[str, Any],
        position: Optional[int] = None
    ) -> bool:
        """
        Pin a chart to the dashboard.
        
        Args:
            chart_config: Dictionary with chart configuration
            position: Optional position index (None = append to end)
            
        Returns:
            True if successful
        """
        if 'dashboard_charts' not in st.session_state:
            self._initialize_state()
        
        chart_entry = {
            'id': len(st.session_state['dashboard_charts']),
            'config': chart_config,
            'position': position if position is not None else len(st.session_state['dashboard_charts'])
        }
        
        if position is not None and position < len(st.session_state['dashboard_charts']):
            st.session_state['dashboard_charts'][position] = chart_entry
        else:
            st.session_state['dashboard_charts'].append(chart_entry)
        
        return True
    
    def remove_chart(self, chart_id: int):
        """
        Remove a chart from the dashboard by ID.
        
        Args:
            chart_id: ID of the chart to remove
        """
        if 'dashboard_charts' not in st.session_state:
            return
        
        st.session_state['dashboard_charts'] = [
            chart for chart in st.session_state['dashboard_charts']
            if chart['id'] != chart_id
        ]
    
    def generate_chart_from_config(self, df: pd.DataFrame, config: Dict[str, Any]) -> go.Figure:
        """
        Generate a chart figure from saved configuration.
        
        Args:
            df: DataFrame
            config: Chart configuration dictionary
            
        Returns:
            Plotly figure
        """
        from .core.chart_generator import generate_chart
        from .charts.combo import generate_combo_chart

        chart_mode = config.get('mode', 'basic')

        if chart_mode == 'basic':
            return generate_chart(
                df,
                config.get('chart_type', 'bar'),
                config.get('x_col'),
                config.get('y_col'),
                config.get('agg_func', 'none'),
                config.get('color_col'),
                config.get('heatmap_columns'),
                None,
                None
            )
        elif chart_mode == 'combo':
            return generate_combo_chart(
                df,
                config.get('x_col'),
                config.get('y_col'),
                config.get('y2_col'),
                config.get('chart1_type', 'bar'),
                config.get('chart2_type', 'line'),
                config.get('color_col')
            )
        else:
            return generate_chart(
                df,
                config.get('chart_type', 'bar'),
                config.get('x_col'),
                config.get('y_col'),
                config.get('agg_func', 'none'),
                config.get('color_col'),
                config.get('heatmap_columns'),
                None,
                None
            )
    
    def render_tab(self, df: pd.DataFrame, selected_table: str) -> bool:
        """
        Render the dashboard builder interface.
        
        Args:
            df: DataFrame to visualize
            selected_table: Name of the selected table
            
        Returns:
            Dashboard active status
        """
        self._initialize_state()
        
        st.header("📊 Dynamic Dashboard Builder")
        st.markdown("**Create multi-chart dashboards with flexible layouts. Pin charts side-by-side for comprehensive analysis.**")
        
        # Dashboard controls
        col_dash1, col_dash2, col_dash3 = st.columns([2, 2, 1])
        
        with col_dash1:
            layout_options = ['2x2', '2x3', '3x2', '3x3', '1x2', '2x1', '1x3', '3x1']
            dashboard_layout = st.selectbox(
                "Dashboard Layout",
                options=layout_options,
                index=0,
                key="dashboard_layout_select",
                help="Choose grid layout for your dashboard"
            )
            st.session_state['dashboard_layout'] = dashboard_layout
        
        with col_dash2:
            dashboard_active = st.checkbox(
                "Enable Dashboard Mode",
                value=st.session_state.get('dashboard_active', False),
                key="dashboard_active_check",
                help="Toggle dashboard mode to pin multiple charts"
            )
            st.session_state['dashboard_active'] = dashboard_active
        
        with col_dash3:
            if st.button("🗑️ Clear Dashboard", key="clear_dashboard"):
                st.session_state['dashboard_charts'] = []
                st.success("✅ Dashboard cleared!")
                st.rerun()
        
        st.divider()
        
        # Show pinned charts count
        pinned_count = len(st.session_state.get('dashboard_charts', []))
        if pinned_count > 0:
            st.info(f"📌 {pinned_count} chart(s) pinned to dashboard")
        
        # Dashboard grid display
        if dashboard_active and pinned_count > 0:
            rows, cols = self.get_layout_grid(dashboard_layout)
            st.subheader(f"📊 Dashboard View ({dashboard_layout} Grid)")
            
            # Create grid layout
            charts = st.session_state['dashboard_charts']
            
            # Render charts in grid
            chart_idx = 0
            for row in range(rows):
                grid_cols = st.columns(cols)
                for col_idx in range(cols):
                    with grid_cols[col_idx]:
                        if chart_idx < len(charts):
                            chart_entry = charts[chart_idx]
                            config = chart_entry['config']
                            
                            # Generate chart
                            try:
                                fig = self.generate_chart_from_config(df, config)
                                
                                # Display chart with unique key to avoid ID conflicts
                                chart_key = f"dashboard_chart_{chart_entry['id']}_{row}_{col_idx}"
                                st.plotly_chart(fig, width='stretch', theme="streamlit", key=chart_key)
                                
                                # Chart info and controls
                                # Note: expander doesn't need a key parameter - Streamlit handles uniqueness
                                with st.expander(f"Chart {chart_idx + 1} Info", expanded=False):
                                    st.caption(f"**Mode:** {config.get('mode', 'basic')}")
                                    st.caption(f"**X:** {config.get('x_col', 'N/A')}")
                                    st.caption(f"**Y:** {config.get('y_col', 'N/A')}")
                                    
                                    # Remove button with unique key including position
                                    remove_key = f"remove_chart_{chart_entry['id']}_{row}_{col_idx}_{chart_idx}"
                                    if st.button(f"Remove Chart {chart_idx + 1}", key=remove_key):
                                        self.remove_chart(chart_entry['id'])
                                        st.success(f"✅ Chart {chart_idx + 1} removed!")
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Error rendering chart {chart_idx + 1}: {str(e)}")
                                st.caption("Chart configuration may be invalid for current data.")
                            
                            chart_idx += 1
                        else:
                            # Empty slot
                            st.info("📌 Pin a chart here")
            
            # Dashboard Export Section
            if dashboard_active and pinned_count > 0:
                st.divider()
                st.subheader("📥 Export Dashboard")
                
                col_exp1, col_exp2, col_exp3 = st.columns(3)
                
                with col_exp1:
                    try:
                        # Export as HTML (interactive)
                        html_parts = []
                        html_parts.append("""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <title>Dashboard Export</title>
                            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
                            <style>
                                body { font-family: Arial, sans-serif; margin: 20px; }
                                .dashboard-grid { display: grid; gap: 20px; margin: 20px 0; }
                                .chart-container { border: 1px solid #ddd; padding: 10px; border-radius: 5px; }
                                h2 { color: #333; }
                            </style>
                        </head>
                        <body>
                            <h1>📊 Dashboard Export</h1>
                            <p>Generated on """ + pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S") + """</p>
                            <div class="dashboard-grid" style="grid-template-columns: repeat(""" + str(cols) + """, 1fr);">
                        """)
                        
                        # Generate all charts and add to HTML
                        plotlyjs_included = False
                        for chart_idx, chart_entry in enumerate(charts):
                            try:
                                fig = self.generate_chart_from_config(df, chart_entry['config'])
                                # Only include plotlyjs once (for first chart)
                                include_plotlyjs = 'cdn' if not plotlyjs_included else False
                                chart_html = fig.to_html(full_html=False, include_plotlyjs=include_plotlyjs)
                                html_parts.append(f'<div class="chart-container"><h3>Chart {chart_idx + 1}</h3>{chart_html}</div>')
                                if not plotlyjs_included:
                                    plotlyjs_included = True
                            except Exception as e:
                                html_parts.append(f'<div class="chart-container"><p>Error rendering chart {chart_idx + 1}: {str(e)}</p></div>')
                        
                        html_parts.append("""
                            </div>
                        </body>
                        </html>
                        """)
                        
                        dashboard_html = "\n".join(html_parts)
                        
                        st.download_button(
                            "🌐 Download Dashboard (HTML)",
                            dashboard_html.encode(),
                            f"dashboard_{selected_table}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.html",
                            "text/html",
                            key="download_dashboard_html",
                            width='stretch'
                        )
                    except Exception as e:
                        st.error(f"HTML export failed: {e}")
                
                with col_exp2:
                    try:
                        # Export dashboard configuration as JSON
                        dashboard_config = {
                            'layout': dashboard_layout,
                            'table': selected_table,
                            'charts': [
                                {
                                    'id': chart['id'],
                                    'config': chart['config']
                                }
                                for chart in charts
                            ],
                            'exported_at': pd.Timestamp.now().isoformat()
                        }
                        
                        config_json = json.dumps(dashboard_config, indent=2)
                        
                        st.download_button(
                            "📋 Download Config (JSON)",
                            config_json.encode(),
                            f"dashboard_config_{selected_table}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                            "application/json",
                            key="download_dashboard_config",
                            width='stretch'
                        )
                    except Exception as e:
                        st.error(f"Config export failed: {e}")
                
                with col_exp3:
                    st.caption("💡 HTML export includes all charts as interactive Plotly visualizations. JSON export saves dashboard configuration for later use.")
            
            st.divider()
        
        return dashboard_active
    
    def get_chart_config(
        self,
        chart_mode: str,
        chart_type: str,
        x_col: str,
        y_col: str,
        agg_func: str,
        color_col: Optional[str],
        composition_params: Dict[str, Any],
        heatmap_columns: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Get current chart configuration for pinning.
        
        Args:
            chart_mode: Chart mode (basic, combo, etc.)
            chart_type: Chart type
            x_col: X column
            y_col: Y column
            agg_func: Aggregation function
            color_col: Color column
            composition_params: Composition-specific parameters
            
        Returns:
            Configuration dictionary
        """
        config = {
            'mode': chart_mode,
            'chart_type': chart_type,
            'x_col': x_col if x_col != 'None' else None,
            'y_col': y_col if y_col != 'None' else None,
            'agg_func': agg_func,
            'color_col': color_col if color_col != 'None' else None
        }
        
        # Add heatmap columns if provided
        if chart_type == 'heatmap' and heatmap_columns:
            config['heatmap_columns'] = heatmap_columns
        
        # Add composition-specific params
        if chart_mode == 'combo':
            config.update({
                'y2_col': composition_params.get('y2_col'),
                'chart1_type': composition_params.get('chart1_type', 'bar'),
                'chart2_type': composition_params.get('chart2_type', 'line')
            })
        
        return config


# Create default instance for backward compatibility
_default_builder = DashboardBuilder()
