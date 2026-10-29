import os
import streamlit as st
import duckdb
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PRIVATE_S3_BUCKET = os.getenv("PRIVATE_S3_BUCKET")

S3_PATH = f"s3://{PRIVATE_S3_BUCKET}/processed/events/**/*.parquet"

st.set_page_config(
    page_title="GDELT Media Lakehouse & HITL Guardrail",
    page_icon="🦆",
    layout="wide"
)

@st.cache_resource
def get_duckdb_conn():
    conn = duckdb.connect(database=":memory:")
    conn.execute("SET max_memory='256MB';")
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    conn.execute(f"SET s3_region='{AWS_REGION}';")
    conn.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY_ID}';")
    conn.execute(f"SET s3_secret_access_key='{AWS_SECRET_ACCESS_KEY}';")
    return conn

conn = get_duckdb_conn()

st.title("🦆 GDELT Media Lakehouse & HITL Guardrail Control Room")
st.markdown("Operational interface for auditing automated news claims against S3 Parquet telemetry.")

st.sidebar.header("Navigation Control")
page = st.sidebar.radio("Select View", ["Macro Lakehouse Overview", "HITL Guardrail Audit Queue"])

if page == "Macro Lakehouse Overview":
    st.subheader("Macro Lakehouse Summary (August - September 2026)")
    
    query = f"""
        SELECT 
            year,
            month,
            COUNT(*) AS total_events,
            ROUND(CAST(AVG(tone) AS DOUBLE), 2) AS avg_tone,
            APPROX_COUNT_DISTINCT(source_url) AS approx_unique_sources
        FROM read_parquet('{S3_PATH}', hive_partitioning=1)
        GROUP BY year, month
        ORDER BY month ASC;
    """
    # Fetch as native tuples to avoid Pandas/NumPy/OpenBLAS memory overhead
    data = conn.execute(query).fetchall()
    columns = ["Year", "Month", "Total Events", "Average Tone", "Unique Sources"]
    
    # Display using native Streamlit table
    st.table([columns] + [list(row) for row in data])

    st.subheader("Daily Event Volume")
    daily_query = f"""
        SELECT 
            CAST(year || '-' || LPAD(month, 2, '0') || '-' || LPAD(day, 2, '0') AS VARCHAR) AS event_date,
            COUNT(*) AS total_events
        FROM read_parquet('{S3_PATH}', hive_partitioning=1)
        GROUP BY event_date
        ORDER BY event_date ASC;
    """
    daily_data = conn.execute(daily_query).fetchall()
    
    # Convert to chart dictionary
    chart_data = {row[0]: row[1] for row in daily_data}
    st.bar_chart(chart_data)

elif page == "HITL Guardrail Audit Queue":
    st.subheader("Human-In-The-Loop (HITL) Review Queue")
    st.markdown("Auditing claims flagged by the semantic uncertainty engine (< 85% confidence threshold).")

    queue_data = [
        {
            "id": "CLM-101",
            "claim": "Global media coverage experienced massive event volumes and negative sentiment spikes.",
            "target_date": "2026-08-05",
            "lakehouse_telemetry": "105,774 events | Avg Tone: -1.90",
            "confidence": 0.4261,
            "status": "CONTRADICTS DATA"
        },
        {
            "id": "CLM-102",
            "claim": "Geopolitical stability reached record highs with zero negative news reporting.",
            "target_date": "2026-09-01",
            "lakehouse_telemetry": "116,766 events | Avg Tone: -1.79",
            "confidence": 0.1245,
            "status": "HALLUCINATION RISK"
        }
    ]

    for item in queue_data:
        with st.expander(f"[{item['id']}] {item['target_date']} — Confidence: {item['confidence']*100:.1f}% ({item['status']})"):
            st.write(f"**Claim:** {item['claim']}")
            st.write(f"**Lakehouse Telemetry:** {item['lakehouse_telemetry']}")
            st.warning("Routed to HITL Queue due to semantic uncertainty score below threshold (0.85).")
            
            c1, c2, c3 = st.columns(3)
            if c1.button("Approve & Publish", key=f"app_{item['id']}"):
                st.success(f"Claim {item['id']} approved.")
            if c2.button("Flag Hallucination", key=f"flag_{item['id']}"):
                st.error(f"Claim {item['id']} flagged as hallucination.")
            if c3.button("Manual Override", key=f"over_{item['id']}"):
                st.info(f"Claim {item['id']} overridden.")