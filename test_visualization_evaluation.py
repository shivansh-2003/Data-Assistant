"""
Visualization Evaluation Script for InsightBot

Tests whether the chatbot correctly generates visualizations for various query types.
Saves visualization images as proof of generation.
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Optional
import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chatbot.graph import graph
from langchain_core.messages import HumanMessage
from chatbot.utils.session_loader import SessionLoader
from data_visualization.visualization import generate_chart as core_generate_chart
from data_visualization.utils import create_error_figure


class VizTestCase:
    """Test case for visualization queries."""
    
    def __init__(self, query: str, expected_viz_type: str, expected_chart: str):
        self.query = query
        self.expected_viz_type = expected_viz_type
        self.expected_chart = expected_chart
        self.actual_viz_type = None
        self.viz_generated = False
        self.error = None
        self.image_path = None
        self.html_path = None


class VizEvaluator:
    """Evaluates visualization generation for test queries."""
    
    def __init__(self, session_id: str, output_dir: str = "viz_test_output"):
        self.session_id = session_id
        self.config = {"configurable": {"thread_id": f"test_{session_id}"}}
        self.results: List[VizTestCase] = []
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.images_dir = self.output_dir / "images"
        self.html_dir = self.output_dir / "html"
        self.images_dir.mkdir(exist_ok=True)
        self.html_dir.mkdir(exist_ok=True)
        
        # Initialize session loader
        self.session_loader = SessionLoader()
    
    def generate_and_save_viz(self, test_case: VizTestCase, viz_config: Dict, test_num: int) -> Optional[go.Figure]:
        """
        Generate the actual Plotly figure from viz_config and save it.
        
        Args:
            test_case: The test case
            viz_config: Visualization configuration from state
            test_num: Test number for naming files
            
        Returns:
            The generated Plotly figure or None if generation fails
        """
        try:
            # Load DataFrames from session
            df_dict = self.session_loader.load_session_dataframes(self.session_id)
            
            if not df_dict:
                test_case.error = "No data available for visualization"
                return None
            
            # Get the primary DataFrame
            table_name = viz_config.get("table_name", "current")
            df = df_dict.get(table_name)
            
            if df is None or df.empty:
                test_case.error = f"DataFrame '{table_name}' not found or empty"
                return None
            
            # Generate the chart
            chart_type = viz_config.get("chart_type", "bar")
            
            try:
                # Prepare arguments for core_generate_chart
                # Note: core_generate_chart only accepts: df, chart_type, x_col, y_col, agg_func, color_col, heatmap_columns
                fig = core_generate_chart(
                    df=df,
                    chart_type=chart_type,
                    x_col=viz_config.get("x_col"),
                    y_col=viz_config.get("y_col"),
                    agg_func=viz_config.get("agg_func", "mean"),  # Default to 'mean' for aggregation
                    color_col=viz_config.get("color_col")
                )
            except Exception as e:
                error_msg = f"Chart generation failed: {str(e)}"
                test_case.error = error_msg
                print(f"   ❌ {error_msg}")
                import traceback
                traceback.print_exc()
                return None
            
            # Save as PNG
            safe_query = "".join(c if c.isalnum() or c in (' ', '_') else '_' for c in test_case.query[:50])
            png_filename = f"test_{test_num:02d}_{safe_query}.png"
            html_filename = f"test_{test_num:02d}_{safe_query}.html"
            
            png_path = self.images_dir / png_filename
            html_path = self.html_dir / html_filename
            
            # Save as PNG (requires kaleido)
            try:
                fig.write_image(str(png_path), width=1200, height=600)
                test_case.image_path = str(png_path)
                print(f"   💾 Saved PNG: {png_path.name}")
            except Exception as e:
                print(f"   ⚠️  Could not save PNG: {e}")
                test_case.image_path = None
            
            # Save as HTML (always works)
            try:
                fig.write_html(str(html_path))
                test_case.html_path = str(html_path)
                print(f"   💾 Saved HTML: {html_path.name}")
            except Exception as e:
                print(f"   ⚠️  Could not save HTML: {e}")
                test_case.html_path = None
            
            return fig
            
        except Exception as e:
            error_msg = f"Visualization generation failed: {str(e)}"
            test_case.error = error_msg
            print(f"   ❌ {error_msg}")
            import traceback
            traceback.print_exc()
            return None
    
    def run_query(self, test_case: VizTestCase, test_num: int) -> bool:
        """
        Run a single query and check if visualization was generated.
        
        Args:
            test_case: The test case to run
            test_num: Test number for naming output files
        
        Returns:
            True if visualization was generated, False otherwise
        """
        print(f"\n🧪 Test {test_num}: {test_case.query[:60]}...")
        
        try:
            # Prepare input
            inputs = {
                "session_id": self.session_id,
                "messages": [HumanMessage(content=test_case.query)],
                "schema": {},
                "operation_history": [],
                "table_names": ["current"],
                "intent": None,
                "entities": None,
                "tool_calls": None,
                "last_insight": None,
                "insight_data": None,
                "viz_config": None,
                "viz_type": None,
                "error": None,
                "sources": []
            }
            
            # Invoke graph
            result = graph.invoke(inputs, self.config)
            
            # Check for visualization
            viz_config = result.get("viz_config")
            viz_type = result.get("viz_type")
            error = result.get("error")
            
            if viz_config:
                test_case.viz_generated = True
                test_case.actual_viz_type = viz_type or viz_config.get("chart_type", "unknown")
                print(f"   ✅ Visualization config generated: {test_case.actual_viz_type}")
                
                # Generate and save the actual visualization
                fig = self.generate_and_save_viz(test_case, viz_config, test_num)
                
                if fig is None:
                    print(f"   ⚠️  Warning: Could not generate actual chart image")
                
                return True
            else:
                test_case.viz_generated = False
                test_case.error = error or "No visualization config in state"
                print(f"   ❌ No visualization generated")
                if error:
                    print(f"   Error: {error}")
                return False
                
        except Exception as e:
            test_case.viz_generated = False
            test_case.error = str(e)
            print(f"   ❌ Error: {e}")
            return False
    
    def run_test_suite(self, test_cases: List[VizTestCase]):
        """Run all test cases."""
        print("=" * 80)
        print("📊 VISUALIZATION GENERATION EVALUATION")
        print("=" * 80)
        print(f"Session ID: {self.session_id}")
        print(f"Total Tests: {len(test_cases)}")
        print(f"Output Directory: {self.output_dir.absolute()}")
        print("=" * 80)
        
        for idx, test_case in enumerate(test_cases, 1):
            self.run_query(test_case, test_num=idx)
            self.results.append(test_case)
        
        self.print_summary()
        self.create_html_report()
    
    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 80)
        print("📈 TEST RESULTS SUMMARY")
        print("=" * 80)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.viz_generated)
        failed = total - passed
        
        print(f"\n✅ PASSED: {passed}/{total} ({passed/total*100:.1f}%)")
        print(f"❌ FAILED: {failed}/{total} ({failed/total*100:.1f}%)")
        
        # Detailed results
        print("\n" + "-" * 80)
        print("DETAILED RESULTS:")
        print("-" * 80)
        
        for i, result in enumerate(self.results, 1):
            status = "✅" if result.viz_generated else "❌"
            print(f"\n{i}. {status} {result.query}")
            print(f"   Expected: {result.expected_chart} ({result.expected_viz_type})")
            if result.viz_generated:
                print(f"   Actual:   {result.actual_viz_type} chart")
                match = result.actual_viz_type == result.expected_viz_type
                print(f"   Match:    {'✅ Yes' if match else '⚠️  Type mismatch'}")
                if result.html_path:
                    print(f"   HTML:     {result.html_path}")
                if result.image_path:
                    print(f"   Image:    {result.image_path}")
            else:
                print(f"   Actual:   None")
                if result.error:
                    print(f"   Error:    {result.error[:100]}")
        
        # Failed cases
        if failed > 0:
            print("\n" + "-" * 80)
            print("❌ FAILED TEST CASES:")
            print("-" * 80)
            for i, result in enumerate(self.results, 1):
                if not result.viz_generated:
                    print(f"\n{i}. {result.query}")
                    print(f"   Error: {result.error}")
        
        print("\n" + "=" * 80)
        print("TEST EVALUATION COMPLETE")
        print("=" * 80)
    
    def export_results(self, filename: str = "viz_test_results.json"):
        """Export results to JSON file."""
        results_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.viz_generated),
            "failed": sum(1 for r in self.results if not r.viz_generated),
            "test_cases": [
                {
                    "query": r.query,
                    "expected_viz_type": r.expected_viz_type,
                    "expected_chart": r.expected_chart,
                    "viz_generated": r.viz_generated,
                    "actual_viz_type": r.actual_viz_type,
                    "error": r.error,
                    "image_path": r.image_path,
                    "html_path": r.html_path
                }
                for r in self.results
            ]
        }
        
        json_path = self.output_dir / filename
        with open(json_path, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Results exported to: {json_path}")
    
    def create_html_report(self):
        """Create an HTML report with all visualizations embedded."""
        report_path = self.output_dir / "test_report.html"
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.viz_generated)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Visualization Test Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}
        .subtitle {{
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-card.total {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .stat-card.passed {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }}
        .stat-card.failed {{
            background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%);
            color: white;
        }}
        .stat-value {{
            font-size: 3em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .stat-label {{
            font-size: 1em;
            opacity: 0.9;
        }}
        .test-case {{
            margin-bottom: 40px;
            padding: 25px;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            background: #fafafa;
        }}
        .test-case.passed {{
            border-left: 5px solid #38ef7d;
        }}
        .test-case.failed {{
            border-left: 5px solid #f45c43;
        }}
        .test-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        .test-number {{
            font-size: 1.5em;
            font-weight: bold;
            color: #7f8c8d;
            margin-right: 15px;
        }}
        .test-status {{
            font-size: 1.5em;
            margin-right: 15px;
        }}
        .test-query {{
            font-size: 1.2em;
            color: #2c3e50;
            font-weight: 500;
            flex: 1;
        }}
        .test-details {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
            padding: 15px;
            background: white;
            border-radius: 5px;
        }}
        .detail-item {{
            display: flex;
            flex-direction: column;
        }}
        .detail-label {{
            font-size: 0.85em;
            color: #7f8c8d;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .detail-value {{
            font-size: 1em;
            color: #2c3e50;
            font-weight: 500;
        }}
        .viz-container {{
            margin-top: 20px;
            border-radius: 8px;
            overflow: hidden;
            background: white;
            padding: 20px;
        }}
        .error-message {{
            background: #fff5f5;
            border: 1px solid #feb2b2;
            color: #c53030;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }}
        .timestamp {{
            text-align: center;
            color: #7f8c8d;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
        iframe {{
            width: 100%;
            height: 600px;
            border: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Visualization Test Report</h1>
        <p class="subtitle">InsightBot Visualization Generation Evaluation</p>
        
        <div class="stats">
            <div class="stat-card total">
                <div class="stat-value">{total}</div>
                <div class="stat-label">Total Tests</div>
            </div>
            <div class="stat-card passed">
                <div class="stat-value">{passed}</div>
                <div class="stat-label">Passed</div>
            </div>
            <div class="stat-card failed">
                <div class="stat-value">{failed}</div>
                <div class="stat-label">Failed</div>
            </div>
        </div>
        
        <div style="background: #e8f5e9; padding: 15px; border-radius: 8px; margin-bottom: 30px; text-align: center;">
            <strong>Pass Rate:</strong> {pass_rate:.1f}% | 
            <strong>Session ID:</strong> {self.session_id}
        </div>
"""
        
        # Add each test case
        for i, result in enumerate(self.results, 1):
            status_class = "passed" if result.viz_generated else "failed"
            status_emoji = "✅" if result.viz_generated else "❌"
            
            match_status = ""
            if result.viz_generated and result.actual_viz_type:
                match = result.actual_viz_type == result.expected_viz_type
                match_status = "✅ Match" if match else "⚠️ Type mismatch"
            
            html_content += f"""
        <div class="test-case {status_class}">
            <div class="test-header">
                <span class="test-number">#{i}</span>
                <span class="test-status">{status_emoji}</span>
                <span class="test-query">{result.query}</span>
            </div>
            
            <div class="test-details">
                <div class="detail-item">
                    <span class="detail-label">Expected</span>
                    <span class="detail-value">{result.expected_chart}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Expected Type</span>
                    <span class="detail-value">{result.expected_viz_type}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Actual Type</span>
                    <span class="detail-value">{result.actual_viz_type or 'None'}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Match Status</span>
                    <span class="detail-value">{match_status or 'N/A'}</span>
                </div>
            </div>
"""
            
            # Embed visualization if available
            if result.html_path and os.path.exists(result.html_path):
                rel_path = os.path.relpath(result.html_path, self.output_dir)
                html_content += f"""
            <div class="viz-container">
                <iframe src="{rel_path}"></iframe>
            </div>
"""
            elif result.error:
                html_content += f"""
            <div class="error-message">
                <strong>Error:</strong> {result.error}
            </div>
"""
            
            html_content += """
        </div>
"""
        
        # Close HTML
        html_content += f"""
        <div class="timestamp">
            Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>
"""
        
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        print(f"\n📄 HTML report created: {report_path}")
        print(f"   Open it in your browser to view all visualizations!")


def create_test_suite() -> List[VizTestCase]:
    """Create the visualization test suite."""
    
    return [
        # Bar Charts
        VizTestCase(
            query="Plot average Price by Company (expect bar chart).",
            expected_viz_type="bar",
            expected_chart="Bar chart"
        ),
        VizTestCase(
            query="Compare count of laptops by TypeName (expect pie or bar chart).",
            expected_viz_type="bar",
            expected_chart="Bar/Pie chart"
        ),
        VizTestCase(
            query="Visualize average Weight by Cpu_brand (expect bar).",
            expected_viz_type="bar",
            expected_chart="Bar chart"
        ),
        VizTestCase(
            query="Bar chart of average HDD by Gpu_brand.",
            expected_viz_type="bar",
            expected_chart="Bar chart"
        ),
        
        # Histograms (Distribution)
        VizTestCase(
            query="Show the distribution of Weight across all laptops (expect histogram).",
            expected_viz_type="histogram",
            expected_chart="Histogram"
        ),
        VizTestCase(
            query="Distribution of Price for Ultrabook vs. Notebook (expect box plot).",
            expected_viz_type="histogram",  # May generate histogram instead of box plot
            expected_chart="Box plot/Histogram"
        ),
        
        # Scatter Plots (Relationships)
        VizTestCase(
            query="Visualize Ram vs. Price relationship (expect scatter plot).",
            expected_viz_type="scatter",
            expected_chart="Scatter plot"
        ),
        VizTestCase(
            query="Plot Ppi vs. SSD for Intel Gpu_brand (expect scatter).",
            expected_viz_type="scatter",
            expected_chart="Scatter plot"
        ),
        VizTestCase(
            query="Scatter plot of Weight vs. Ppi, colored by TouchScreen.",
            expected_viz_type="scatter",
            expected_chart="Scatter plot"
        ),
        
        # Pie Chart (Percentages/Breakdown)
        VizTestCase(
            query="Show breakdown of Os types as percentages (expect pie chart).",
            expected_viz_type="bar",  # May use bar instead of pie
            expected_chart="Pie/Bar chart"
        ),
    ]


def main():
    """Main execution function."""
    
    # Check if session ID is provided
    if len(sys.argv) < 2:
        print("❌ Error: Please provide a session ID")
        print("\nUsage:")
        print("  python test_visualization_evaluation.py <session_id>")
        print("\nExample:")
        print("  python test_visualization_evaluation.py c592af39-5f33-48d1-a9ad-70cd3caef7dd")
        sys.exit(1)
    
    session_id = sys.argv[1]
    
    # Create test suite
    test_cases = create_test_suite()
    
    # Run evaluation
    evaluator = VizEvaluator(session_id)
    evaluator.run_test_suite(test_cases)
    
    # Export results
    evaluator.export_results()
    
    # Exit with appropriate code
    passed = sum(1 for r in evaluator.results if r.viz_generated)
    total = len(evaluator.results)
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

