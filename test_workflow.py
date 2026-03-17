import agent_workflow
import json

def test():
    job_desc = "Looking for a Python developer with 3 years of experience and knowledge of Streamlit."
    base_cv_json = json.dumps({
        "name": "John Doe", 
        "experience": [
            {"title": "Data Analyst", "description": "Worked with Python and pandas for 2 years."}
        ], 
        "skills": ["Python", "Data Analysis", "SQL"], 
        "summary": "Data Analyst with Python experience."
    })
    
    print("Starting workflow test...")
    try:
        res = agent_workflow.run_application_workflow(job_desc, base_cv_json, "gemini-2.5-flash")
        print("Workflow completed successfully.")
        print(res)
    except Exception as e:
        print(f"Workflow failed with error: {e}")

if __name__ == "__main__":
    test()
