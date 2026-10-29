import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import duckdb
from dotenv import load_dotenv
from transformers import pipeline

load_dotenv()

AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
PRIVATE_S3_BUCKET = os.getenv("PRIVATE_S3_BUCKET")

S3_PATH = f"s3://{PRIVATE_S3_BUCKET}/processed/events/**/*.parquet"

class MediaGuardrailEngine:
    def __init__(self):
        print("Initializing Lightweight Guardrail Transformer Pipeline...")
        # Using DistilBERT-MNLI (~250MB) to permanently resolve Windows OpenBLAS memory allocation limits
        self.classifier = pipeline(
            "zero-shot-classification", 
            model="typeform/distilbert-base-uncased-mnli",
            device=-1
        )
        print("Guardrail Engine Ready.")

    def _get_lakehouse_telemetry(self, target_date: str):
        conn = duckdb.connect(database=":memory:")
        conn.execute("SET max_memory='512MB';")
        conn.execute("INSTALL httpfs;")
        conn.execute("LOAD httpfs;")
        conn.execute(f"SET s3_region='{AWS_REGION}';")
        conn.execute(f"SET s3_access_key_id='{AWS_ACCESS_KEY}';")
        conn.execute(f"SET s3_secret_access_key='{AWS_SECRET_KEY}';")

        query = f"""
            SELECT 
                COUNT(*) AS total_events,
                ROUND(CAST(AVG(tone) AS DOUBLE), 2) AS avg_tone
            FROM read_parquet('{S3_PATH}', hive_partitioning=1)
            WHERE CAST(year || '-' || LPAD(month, 2, '0') || '-' || LPAD(day, 2, '0') AS DATE) = DATE '{target_date}'
        """
        df = conn.execute(query).fetchdf()
        conn.close()

        if df.empty or df.iloc[0]['total_events'] == 0:
            return {"total_events": 0, "avg_tone": 0.0, "status": "NO_DATA"}
        
        return {
            "total_events": int(df.iloc[0]['total_events']),
            "avg_tone": float(df.iloc[0]['avg_tone']),
            "status": "SUCCESS"
        }

    def evaluate_claim(self, claim_text: str, target_date: str, confidence_threshold: float = 0.85):
        telemetry = self._get_lakehouse_telemetry(target_date)
        
        if telemetry["status"] == "NO_DATA":
            return {
                "claim": claim_text,
                "target_date": target_date,
                "confidence_score": 0.0,
                "routing": "HITL_REVIEW_QUEUE",
                "reason": "Zero event telemetry found for target date in lakehouse."
            }

        context = (
            f"On {target_date}, GDELT recorded {telemetry['total_events']:,} global media events "
            f"with an average sentiment tone of {telemetry['avg_tone']}."
        )

        candidate_labels = ["supported by data", "contradicts data", "unsupported hallucination"]
        result = self.classifier(claim_text, candidate_labels, hypothesis_template=f"This claim is {{}} based on the fact that: {context}")

        top_label = result['labels'][0]
        top_score = result['scores'][0]

        routing = "AUTO_PUBLISH" if (top_label == "supported by data" and top_score >= confidence_threshold) else "HITL_REVIEW_QUEUE"

        return {
            "claim": claim_text,
            "target_date": target_date,
            "lakehouse_telemetry": telemetry,
            "top_evaluation": top_label,
            "confidence_score": round(top_score, 4),
            "routing": routing,
            "reason": f"Evaluated as '{top_label}' with score {top_score:.2f} (Threshold: {confidence_threshold})"
        }

if __name__ == "__main__":
    engine = MediaGuardrailEngine()
    sample_claim = "Global media coverage experienced massive event volumes and negative sentiment spikes."
    evaluation = engine.evaluate_claim(sample_claim, "2026-08-05")
    
    print("\n--- Guardrail Evaluation Result ---")
    for k, v in evaluation.items():
        print(f"{k}: {v}")