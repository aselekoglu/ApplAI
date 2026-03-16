import os
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
# Uncomment the below and configure the specific LLM you wish to use.
# from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# LLM will be instantiated dynamically inside functions to use the selected model

# --- Pydantic Output Models ---

class JobRequirements(BaseModel):
    key_skills: list[str] = Field(description="List of required technical and soft skills")
    experience_level: str = Field(description="Required experience level (e.g., Senior, Junior, 5+ years)")
    company_values: list[str] = Field(description="Derived company values or tone")

class TailoredCV(BaseModel):
    profile_bullets: list[str] = Field(description="3-4 tailored profile/summary bullet points highlighting the most relevant experience for this job")
    experience_highlights: list[str] = Field(description="5-8 most relevant experience bullet points selected and rephrased from the candidate's existing experience to match the job requirements")
    skills_to_highlight: list[str] = Field(description="Key technical and soft skills to emphasise for this specific role")
    tailoring_notes: str = Field(description="Brief explanation of what was changed and why")

class QA_Report(BaseModel):
    matching_rate_score: int = Field(description="A score out of 100 on how well the tailored CV matches the job")
    key_pain_points: list[str] = Field(description="Areas where the applicant lacks required skills")
    strong_points: list[str] = Field(description="Areas where the applicant perfectly matches the requirements")
    feedback: str = Field(description="General feedback for improvement")

# --- Agents Definition ---

def create_job_analyzer(llm):
    return Agent(
        role='The Expert Tech Recruiter',
        goal='Analyze the job description to extract core requirements, skills, and company culture.',
        backstory='You are a seasoned Silicon Valley recruiter who knows exactly what hiring managers want. You read between the lines to find the true requirements of a role.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

def create_cv_tailorer(llm):
    return Agent(
        role='The Elite Career Coach',
        goal='Tailor a provided CV base to perfectly match the job requirements without inventing new facts.',
        backstory='You help top-tier candidates get hired by highlighting their most relevant experiences. You strictly adhere to the truth but frame it beautifully to match the target job.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

def create_cover_letter_writer(llm):
    return Agent(
        role='The Master Wordsmith',
        goal='Write a compelling, human-sounding cover letter that connects the candidate\'s tailored CV to the job description.',
        backstory='You are a professional copywriter specializing in career narratives. You write cover letters that are concise, impactful, and free from AI- sounding clichés.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

def create_qa_reviewer(llm):
    return Agent(
        role='The Strict QA Editor',
        goal='Review the tailored CV and Cover Letter against the job description to ensure high quality, no hallucinations, and provide a match score.',
        backstory='You are an eagle-eyed editor and compliance officer. You ensure no fake skills were added and that the final output is flawless. You score candidates objectively.',
        verbose=True,
        allow_delegation=False,
        llm=llm
    )

# --- Tasks Definition ---

def create_tasks(job_description, base_cv_json_text, agents):
    analyzer, tailorer, writer, reviewer = agents

    task1 = Task(
        description=f'Analyze this job description carefully:\n\n{job_description}\n\nExtract the core skills, required experience, and company tone.',
        expected_output='A structured JSON summarizing key skills, experience level, and company values.',
        output_pydantic=JobRequirements,
        agent=analyzer
    )

    task2 = Task(
        description=f'Here is the base CV in JSON format:\n\n{base_cv_json_text}\n\nUsing the extracted job requirements from the previous task, select and rephrase the most relevant bullet points. DO NOT invent skills the candidate does not have. Keep it to 2 pages maximum.',
        expected_output='Structured tailored CV with profile bullets, top experience highlights, and skills to emphasise.',
        output_pydantic=TailoredCV,
        agent=tailorer
    )

    task3 = Task(
        description='Using the original job description and the newly tailored CV, write a 3-paragraph cover letter targeting this specific employer.',
        expected_output='A markdown-formatted cover letter.',
        agent=writer
    )

    task4 = Task(
        description='Review the outputs of the previous tasks. Create a final QA report containing the match rate (0-100), pain points, and strong points.',
        expected_output='A structured JSON QA report.',
        output_pydantic=QA_Report,
        agent=reviewer
    )

    return [task1, task2, task3, task4]

# --- Workflow Execution ---
def run_application_workflow(job_description: str, base_cv_json_text: str, model_name: str = "gemini-2.5-flash"):
    llm = ChatGoogleGenerativeAI(model=model_name)
    agents = [create_job_analyzer(llm), create_cv_tailorer(llm), create_cover_letter_writer(llm), create_qa_reviewer(llm)]
    
    tasks = create_tasks(job_description, base_cv_json_text, agents)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=True
    )

    result = crew.kickoff()
    return result

def get_test_model():
    return ChatGoogleGenerativeAI(model="gemini-2.5-flash")

if __name__ == "__main__":
    print("Agent Pipeline configured successfully.")
