
import json

from app.services.resume_loader import load_resume_from_folder
from app.services.fact_extractor import extract_facts

resume = load_resume_from_folder()
result = extract_facts(resume["extracted_text"])

print(json.dumps(result, indent=2, ensure_ascii=False))
