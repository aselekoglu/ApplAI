import os
import json
import pdfplumber

def parse_pdf_to_json(pdf_path):
    """
    Extracts text from a given PDF and structures it into a basic JSON format.
    Eventually, this can use an LLM or specific regex to better structure the data.
    """
    extracted_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
                    
        # Basic structuring. In Phase 2, an LLM agent might do the deep structuring.
        cv_data = {
            "source_file": os.path.basename(pdf_path),
            "raw_text": extracted_text.strip()
        }
        return cv_data
    except Exception as e:
        print(f"Error parsing {pdf_path}: {e}")
        return None

def process_all_pdfs(docs_dir="docs", output_dir="docs/json_exports"):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for filename in os.listdir(docs_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(docs_dir, filename)
            print(f"Processing {filename}...")
            data = parse_pdf_to_json(pdf_path)
            if data:
                output_filename = filename.replace(".pdf", ".json")
                output_path = os.path.join(output_dir, output_filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                print(f"Saved JSON to {output_path}")

if __name__ == "__main__":
    process_all_pdfs()
