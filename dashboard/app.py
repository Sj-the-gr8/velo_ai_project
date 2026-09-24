from __future__ import annotations

import sqlite3
import pandas as pd
import streamlit as st

from config import settings
from db.db import Database

st.set_page_config(page_title="Velo", page_icon="V", layout="wide")
st.title("Velo subscription review")

# Create empty tables on a fresh install so the page renders before the first pipeline run.
Database(settings.database_path).migrate()
connection = sqlite3.connect(settings.database_path)
try:
    subscriptions = pd.read_sql_query("SELECT * FROM subscriptions ORDER BY merchant_name", connection)
    alerts = pd.read_sql_query("SELECT a.*, s.merchant_name FROM alerts a JOIN subscriptions s ON s.id = a.subscription_id WHERE a.resolved = 0 ORDER BY a.created_at DESC", connection)
    events = pd.read_sql_query("SELECT b.billing_date, b.amount, b.currency, s.merchant_name FROM billing_events b JOIN subscriptions s ON s.id = b.subscription_id ORDER BY b.billing_date", connection)
finally:
    connection.close()

monthly_spend = float(subscriptions.loc[subscriptions["status"] == "active", "current_amount"].sum()) if not subscriptions.empty else 0
first, second, third = st.columns(3)
first.metric("Monthly recurring spend", f"{monthly_spend:,.2f}")
second.metric("Active subscriptions", int((subscriptions["status"] == "active").sum()) if not subscriptions.empty else 0)
third.metric("Open alerts", len(alerts))

st.subheader("Subscriptions")
if subscriptions.empty:
    st.info("No subscriptions have been ingested yet.")
else:
    display = subscriptions[["merchant_name", "current_amount", "currency", "cadence", "status", "last_seen"]].copy()
    display["status"] = display["status"].map(lambda value: f"[{value.upper()}]")
    st.dataframe(display, use_container_width=True, hide_index=True)

st.subheader("Alerts")
if alerts.empty:
    st.success("No open alerts.")
else:
    for row in alerts.itertuples():
        st.warning(f"{row.merchant_name}: {row.reason.replace('_', ' ').capitalize()}")

st.subheader("Cost over time")
if events.empty:
    st.info("Billing events will appear here after ingestion.")
else:
    # Bucket by month so a merchant reads as 0 only in months with no charge, not on every day between charges.
    month = pd.to_datetime(events["billing_date"]).dt.to_period("M").dt.to_timestamp()
    chart = events.assign(month=month).pivot_table(index="month", columns="merchant_name", values="amount", aggfunc="sum").fillna(0)
    st.line_chart(chart)
