import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import requests
import boto3
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PRIVATE_S3_BUCKET = os.getenv("PRIVATE_S3_BUCKET")

GDELT_EVENT_COLUMNS = [
    "event_id", "sqldate", "month_year", "year", "fraction_date",
    "actor1_code", "actor1_name", "actor1_country", "actor1_known_group", "actor1_ethnic", "actor1_religion", "actor1_type1", "actor1_type2", "actor1_type3",
    "actor2_code", "actor2_name", "actor2_country", "actor2_known_group", "actor2_ethnic", "actor2_religion", "actor2_type1", "actor2_type2", "actor2_type3",
    "is_root_event", "event_code", "event_base_code", "event_root_code", "quad_class", "goldstein_scale", "num_mentions", "num_sources", "num_articles", "confidence",
    "tone", "actor1_geo_type", "actor1_geo_fullname", "actor1_geo_country_code", "actor1_geo_adm1", "actor1_geo_lat", "actor1_geo_long", "actor1_geo_feature_id",
    "actor2_geo_type", "actor2_geo_fullname", "actor2_geo_country_code", "actor2_geo_adm1", "actor2_geo_lat", "actor2_geo_long", "actor2_geo_feature_id",
    "action_geo_type", "action_geo_fullname", "action_geo_country_code", "action_geo_adm1", "action_geo_lat", "action_geo_long", "action_geo_feature_id",
    "date_added", "source_url"
]

def ingest_data():
    print("Connecting to private S3 bucket...")
    private_s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY, region_name=AWS_REGION)
    
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    
    # Define months to process: (Month Name, Month Number, Total Days)
    months_to_process = [
        ("08", 31), # August
        ("09", 30)  # September
    ]
    
    total_success = 0
    
    for month_str, days in months_to_process:
        print(f"\n--- Starting Ingestion for 2026-{month_str} ---")
        for day in range(1, days + 1):
            date_str = f"2026{month_str}{day:02d}"
            filename = f"{date_str}.export.CSV.zip"
            url = f"http://data.gdeltproject.org/events/{filename}"
            
            s3_dest_key = f"processed/events/year=2026/month={month_str}/day={day:02d}/{date_str}.parquet"
            local_zip = os.path.join("data/raw", filename)
            local_parquet = os.path.join("data/processed", f"{date_str}.parquet")
            
            try:
                print(f"[{day}/{days}] Downloading {filename} via HTTP...")
                response = requests.get(url, stream=True, timeout=60)
                
                if response.status_code == 200:
                    with open(local_zip, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    print(f"HTTP Status {response.status_code} for {filename}")
                    continue
                    
                print(f"  -> Converting to Parquet...")
                df = pd.read_csv(
                    local_zip, 
                    compression='zip', 
                    sep='\t', 
                    header=None, 
                    names=GDELT_EVENT_COLUMNS, 
                    on_bad_lines='skip'
                )
                df.to_parquet(local_parquet, index=False)
                
                print(f"  -> Uploading to s3://{PRIVATE_S3_BUCKET}/{s3_dest_key}...")
                private_s3.upload_file(local_parquet, PRIVATE_S3_BUCKET, s3_dest_key)
                total_success += 1
                
                if os.path.exists(local_zip): os.remove(local_zip)
                if os.path.exists(local_parquet): os.remove(local_parquet)
                print(f"Done.")
                
            except Exception as e:
                print(f"Error on {filename}: {e}")

    print(f"\nIngestion finished! Successfully uploaded {total_success} total partitions for August & September 2026.")

if __name__ == "__main__":
    ingest_data()