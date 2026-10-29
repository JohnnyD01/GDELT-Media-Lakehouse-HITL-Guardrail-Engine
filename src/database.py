import os
import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PRIVATE_S3_BUCKET = os.getenv("PRIVATE_S3_BUCKET")

S3_PATH = f"s3://{PRIVATE_S3_BUCKET}/processed/events/**/*.parquet"

def get_duckdb_connection():
    conn = duckdb.connect(database=":memory:")
    conn.execute("SET max_memory='2GB';")
    conn.execute("SET preserve_insertion_order=false;")
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    conn.execute(f"SET s3_region='{AWS_REGION}';")
    conn.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY_ID}';")
    conn.execute(f"SET s3_secret_access_key='{AWS_SECRET_ACCESS_KEY}';")
    return conn

def print_daily_calendar_report(conn):
    # Construct metrics using Hive partition columns (year, month, day) directly 
    # instead of relying on internal file columns.
    query = f"""
        WITH calendar AS (
            SELECT 
                CAST(day AS DATE) AS cal_date
            FROM generate_series(
                DATE '2026-08-01', 
                DATE '2026-09-30', 
                INTERVAL '1 day'
            ) AS t(day)
        ),
        metrics AS (
            SELECT 
                CAST(year || '-' || month || '-' || day AS DATE) AS event_date,
                COUNT(*) AS total_events,
                ROUND(CAST(AVG(tone) AS DOUBLE), 2) AS avg_tone
            FROM read_parquet('{S3_PATH}', hive_partitioning=1)
            GROUP BY year, month, day
        )
        SELECT 
            c.cal_date AS date,
            COALESCE(m.total_events, 0) AS total_events,
            COALESCE(m.avg_tone, 0.0) AS avg_tone
        FROM calendar c
        LEFT JOIN metrics m ON c.cal_date = m.event_date
        ORDER BY c.cal_date ASC;
    """
    df = conn.execute(query).fetchdf()
    print("\n==================================================")
    print("  DAILY CALENDAR REPORT (AUG 1 - SEP 30, 2026)    ")
    print("==================================================")
    print(df)

def print_monthly_summary(conn):
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
    df = conn.execute(query).fetchdf()
    print("\n==================================================")
    print("         MACRO MONTHLY SUMMARY (2026)             ")
    print("==================================================")
    print(df)

if __name__ == "__main__":
    pd.set_option("display.max_rows", 100)
    pd.set_option("display.width", 1000)
    
    conn = get_duckdb_connection()
    try:
        print_daily_calendar_report(conn)
        print_monthly_summary(conn)
    finally:
        conn.close()