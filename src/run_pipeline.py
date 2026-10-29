import os
import sys
from dotenv import load_dotenv

# Set thread environment limits
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

load_dotenv()

# Ensure src directory is in path for module imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from guardrail import MediaGuardrailEngine

def run_end_to_end_pipeline():
    print("==================================================")
    print("      GDELT MEDIA LAKEHOUSE PIPELINE RUNNER       ")
    print("==================================================")

    # Step 1: Initialize Guardrail & Verify S3 Lakehouse Telemetry
    print("\n[1/3] Initializing Semantic Guardrail Engine...")
    engine = MediaGuardrailEngine()

    # Step 2: Evaluate Sample Production Claims
    print("\n[2/3] Executing Guardrail Validation Against S3 Parquet...")
    test_claims = [
        ("Global media coverage experienced massive event volumes and negative sentiment spikes.", "2026-08-05"),
        ("Geopolitical stability reached record highs with zero negative news reporting.", "2026-09-01")
    ]

    for claim, target_date in test_claims:
        print(f"\nEvaluating Claim: '{claim}' (Target Date: {target_date})")
        result = engine.evaluate_claim(claim, target_date)
        print(f" -> Telemetry: {result['lakehouse_telemetry']}")
        print(f" -> Evaluation: {result['top_evaluation']} (Score: {result['confidence_score']})")
        print(f" -> Routing: {result['routing']}")

    # Step 3: Trigger Executive Export Refresh
    print("\n[3/3] Triggering Power BI Executive Dataset Refresh...")
    import export_powerbi
    export_powerbi.export_executive_data()

    print("\n==================================================")
    print("     PIPELINE EXECUTION COMPLETED SUCCESSFULLY    ")
    print("==================================================")

if __name__ == "__main__":
    run_end_to_end_pipeline()