import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import duckdb
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PRIVATE_S3_BUCKET = os.getenv("PRIVATE_S3_BUCKET")

S3_PATH = f"s3://{PRIVATE_S3_BUCKET}/processed/events/**/*.parquet"

def export_executive_data():
    conn = duckdb.connect(database=":memory:")
    conn.execute("SET max_memory='512MB';")
    conn.execute("PRAGMA threads=1;")  # Force single-threaded execution to prevent OpenBLAS thread contention
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    conn.execute(f"SET s3_region='{AWS_REGION}';")
    conn.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY_ID}';")
    conn.execute(f"SET s3_secret_access_key='{AWS_SECRET_ACCESS_KEY}';")

    os.makedirs("data", exist_ok=True)
    output_path = "data/power_bi_summary.csv"

    print("Querying S3 Lakehouse & Exporting Directly to CSV...")
    
    copy_query = f"""
        COPY (
            SELECT 
                CAST(year || '-' || LPAD(month, 2, '0') || '-' || LPAD(day, 2, '0') AS DATE) AS EventDate,
                year AS Year,
                month AS Month,
                day AS Day,
                COUNT(*) AS TotalEvents,
                ROUND(CAST(AVG(tone) AS DOUBLE), 2) AS AverageTone,
                APPROX_COUNT_DISTINCT(source_url) AS UniqueSources
            FROM read_parquet('{S3_PATH}', hive_partitioning=1)
            GROUP BY EventDate, year, month, day
            ORDER BY EventDate ASC
        ) TO '{output_path}' (HEADER, DELIMITER ',');
    """
    
    conn.execute(copy_query)
    conn.close()
    
    print(f"Success! Executive dataset generated at {output_path}.")

if __name__ == "__main__":
    export_executive_data()