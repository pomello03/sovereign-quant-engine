# generate_all_manuals.py
import os
import sys

# Ensure reportlab is installed
try:
    import reportlab
except ImportError:
    import subprocess
    print("Installing reportlab...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])

from generate_easy_pdf import create_easy_manual
from generate_deploy_pdf import create_deploy_manual
from generate_pdf import create_manual
from generate_pipeline_pdf import create_pipeline_manual
from generate_effectiveness_pdf import generate_report

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(base_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    print("=== Sovereign Quant Engine - Generating All Manuals ===")
    
    # 1. Easy Manual
    easy_path = os.path.join(docs_dir, "Guida_Semplicissima_Sovereign_Quant_Engine.pdf")
    print(f">> Generating Easy Manual...")
    create_easy_manual(easy_path)
    
    # 2. Deploy IRL Manual
    deploy_path = os.path.join(docs_dir, "Guida_Deploy_IRL_Sicuro.pdf")
    print(f">> Generating Deploy IRL Manual...")
    create_deploy_manual(deploy_path)
    
    # 3. Main Operational Manual
    main_path = os.path.join(docs_dir, "Sovereign_Quant_Engine_Manual.pdf")
    print(f">> Generating Main Operational Manual...")
    create_manual(main_path)
    
    # 4. Pipeline Deploy Manual
    pipeline_path = os.path.join(docs_dir, "Pipeline_Deploy_IRL_Bybit_Hetzner.pdf")
    print(f">> Generating Pipeline Deploy Manual...")
    create_pipeline_manual(pipeline_path)

    # 5. Effectiveness Analysis Report
    effectiveness_path = os.path.join(docs_dir, "Analisi_Efficacia_Sovereign_Quant_Engine.pdf")
    print(f">> Generating Effectiveness Analysis Report...")
    generate_report(effectiveness_path)

    print("\n=== All Manuals Generated Successfully in 'docs/' ===")

if __name__ == "__main__":
    main()
