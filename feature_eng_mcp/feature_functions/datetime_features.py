"""Advanced datetime and time-since features."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .core import run_fe_tool, preview_tail


def _to_dt(s: pd.Series, date_format: Optional[str]) -> pd.Series:
    if date_format:
        return pd.to_datetime(s, format=date_format, errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def create_advanced_date_features_impl(
    df: pd.DataFrame,
    date_column: str,
    features: List[str],
    cyclical_period: Optional[Dict[str, int]] = None,
    reference_date: Optional[str] = None,
    date_format: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if date_column not in df.columns:
        raise ValueError(f"Column {date_column} not found")
    dt = _to_dt(df[date_column], date_format)
    out = df.copy()
    created = []
    cyclical_period = cyclical_period or {}

    for f in features:
        colname = None
        if f == "year":
            colname = f"{date_column}_year"
            out[colname] = dt.dt.year
        elif f == "month":
            colname = f"{date_column}_month"
            out[colname] = dt.dt.month
        elif f == "day":
            colname = f"{date_column}_day"
            out[colname] = dt.dt.day
        elif f == "weekday":
            colname = f"{date_column}_weekday"
            out[colname] = dt.dt.dayofweek
        elif f == "quarter":
            colname = f"{date_column}_quarter"
            out[colname] = dt.dt.quarter
        elif f == "is_weekend":
            colname = f"{date_column}_is_weekend"
            out[colname] = dt.dt.dayofweek >= 5
        elif f == "hour":
            colname = f"{date_column}_hour"
            out[colname] = dt.dt.hour
        elif f == "day_of_year":
            colname = f"{date_column}_day_of_year"
            out[colname] = dt.dt.dayofyear
        elif f == "week_of_year":
            colname = f"{date_column}_week_of_year"
            out[colname] = dt.dt.isocalendar().week.astype(int)
        elif f == "month_sin":
            colname = f"{date_column}_month_sin"
            m = dt.dt.month.fillna(1).astype(float)
            p = cyclical_period.get("month", 12)
            out[colname] = np.sin(2 * np.pi * m / p)
        elif f == "month_cos":
            colname = f"{date_column}_month_cos"
            m = dt.dt.month.fillna(1).astype(float)
            p = cyclical_period.get("month", 12)
            out[colname] = np.cos(2 * np.pi * m / p)
        elif f == "weekday_sin":
            colname = f"{date_column}_weekday_sin"
            w = dt.dt.dayofweek.fillna(0).astype(float)
            p = cyclical_period.get("weekday", 7)
            out[colname] = np.sin(2 * np.pi * w / p)
        elif f == "weekday_cos":
            colname = f"{date_column}_weekday_cos"
            w = dt.dt.dayofweek.fillna(0).astype(float)
            p = cyclical_period.get("weekday", 7)
            out[colname] = np.cos(2 * np.pi * w / p)
        elif f == "hour_sin":
            colname = f"{date_column}_hour_sin"
            h = dt.dt.hour.fillna(0).astype(float)
            p = cyclical_period.get("hour", 24)
            out[colname] = np.sin(2 * np.pi * h / p)
        elif f == "hour_cos":
            colname = f"{date_column}_hour_cos"
            h = dt.dt.hour.fillna(0).astype(float)
            p = cyclical_period.get("hour", 24)
            out[colname] = np.cos(2 * np.pi * h / p)
        elif f == "days_since_epoch":
            colname = f"{date_column}_days_since_epoch"
            out[colname] = (dt - pd.Timestamp("1970-01-01")).dt.days
        elif f == "is_month_start":
            colname = f"{date_column}_is_month_start"
            out[colname] = dt.dt.is_month_start
        elif f == "is_month_end":
            colname = f"{date_column}_is_month_end"
            out[colname] = dt.dt.is_month_end
        else:
            continue
        if colname:
            created.append(colname)

    return out, {
        "created_columns": created,
        "preview": preview_tail(out),
        "message": "create_advanced_date_features",
    }


def create_time_since_features_impl(
    df: pd.DataFrame,
    date_column: str,
    reference_column: Optional[str] = None,
    reference_date: Optional[str] = None,
    unit: str = "days",
    new_name: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if date_column not in df.columns:
        raise ValueError("date_column missing")
    d1 = _to_dt(df[date_column], None)
    out = df.copy()
    name = new_name or f"{date_column}_since_ref_{unit}"
    if reference_column and reference_column in df.columns:
        d2 = _to_dt(df[reference_column], None)
        secs = (d1 - d2).dt.total_seconds()
    elif reference_date:
        ref = pd.Timestamp(reference_date)
        secs = (d1 - ref).dt.total_seconds()
    else:
        ref = pd.Timestamp.utcnow().tz_localize(None)
        secs = (d1 - ref).dt.total_seconds()
    u = unit.lower()
    if u == "days":
        out[name] = secs / 86400.0
    elif u == "hours":
        out[name] = secs / 3600.0
    elif u == "minutes":
        out[name] = secs / 60.0
    elif u == "weeks":
        out[name] = secs / (86400.0 * 7)
    else:
        out[name] = secs
    return out, {
        "new_column": name,
        "stats": {
            "min": float(pd.Series(out[name]).min()),
            "max": float(pd.Series(out[name]).max()),
            "mean": float(pd.Series(out[name]).mean()),
            "null_count": int(pd.Series(out[name]).isna().sum()),
        },
        "preview": preview_tail(out),
        "message": "create_time_since_features",
    }


def create_advanced_date_features(
    session_id: str,
    date_column: str,
    features: List[str],
    cyclical_period: Optional[Dict[str, int]] = None,
    reference_date: Optional[str] = None,
    date_format: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "create_advanced_date_features",
        lambda d: create_advanced_date_features_impl(
            d, date_column, features, cyclical_period, reference_date, date_format
        ),
    )


def create_time_since_features(
    session_id: str,
    date_column: str,
    reference_column: Optional[str] = None,
    reference_date: Optional[str] = None,
    unit: str = "days",
    new_name: Optional[str] = None,
    table_name: str = "current",
) -> Dict[str, Any]:
    return run_fe_tool(
        session_id,
        table_name,
        "create_time_since_features",
        lambda d: create_time_since_features_impl(
            d, date_column, reference_column, reference_date, unit, new_name
        ),
    )
