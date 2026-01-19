## Finance Module

This module contains finance-specific tools and documentation for the Data Assistant.

### Trading Performance Analyzer

Use the `trading_performance_analyzer` tool for performance questions such as:

- "What was our P&L by currency pair this week?"
- "Which trader had the best Sharpe ratio?"
- "Show me win rate by trading strategy"
- "Compare average trade duration by instrument"

#### Suggested Data Columns

To answer performance queries reliably, include columns similar to:

- `Timestamp`
- `Instrument`
- `Side`
- `Quantity`
- `Price`
- `Notional`
- `Trader_ID`
- `Strategy`
- `Status`
- `Realized_PnL`
- `Unrealized_PnL`

The tool routes to the existing pandas analysis pipeline and expects the session data
to be loaded into DataFrames as usual.
