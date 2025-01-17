import streamlit as st
import google.generativeai as genai
import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()



# Configure Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("Please set the GEMINI_API_KEY environment variable.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

def reset_application_state():
    """
    Resets the application state to its default values.
    This function clears all session state variables and returns the app to its initial state.
    """
    # Clear specific session state variables
    if 'active_project' in st.session_state:
        del st.session_state['active_project']
    
    # Add any other session state variables that need to be cleared
    # For example, if you have other states like 'uploaded_files', 'evaluation_results', etc.
    for key in list(st.session_state.keys()):
        if key.startswith('_') is False:  # Don't remove Streamlit's internal states
            del st.session_state[key]
    
    # Set default values
    st.session_state['active_project'] = "Untitled Project"

def upload_to_gemini(path, mime_type=None):
    """
    Uploads the given file to Gemini API.
    
    Args:
        path (str): Path to the file to upload
        mime_type (str, optional): MIME type of the file
    
    Returns:
        File object or None if upload fails
    """
    try:
        file = genai.upload_file(path, mime_type=mime_type)
        print(f"Uploaded file '{file.display_name}' as: {file.uri}")
        return file
    except Exception as e:
        st.error(f"Error uploading file to Gemini: {e}")
        return None

def wait_for_files_active(files):
    """
    Waits for uploaded files to be processed by Gemini API.
    Shows a progress bar during processing.
    
    Args:
        files (list): List of uploaded file objects
    """
    if not files:
        return
    
    st.info("Waiting for file processing...")
    progress_bar = st.progress(0)
    
    for i, file_obj in enumerate(files):
        file = genai.get_file(file_obj.name)
        while file.state.name == "PROCESSING":
            time.sleep(2)  # Reduced sleep time for better responsiveness
            file = genai.get_file(file_obj.name)
            
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file_obj.name} failed to process")
        
        progress_bar.progress((i + 1) / len(files))
    
    st.success("File processing complete.")

def get_model(model_name="gemini-2.0-flash-exp"):
    """
    Creates and configures a Gemini generative model with specific settings.
    
    Args:
        model_name (str): Name of the Gemini model to use
    
    Returns:
        GenerativeModel: Configured Gemini model instance
    """
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }
    
    system_instruction = (
        "You are a student assignment helper and your job is to understand "
        "the uploaded assignment brief, analyze it, check details like deliverables, "
        "grading scheme, assignment requirements and any special instructions and "
        "finally prepare a road map (step by step guideline) for the students "
        "which they can follow to complete the assignment."
    )
    
    return genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
        system_instruction=system_instruction
    )

class AssignmentManager:
    def __init__(self):
        self.projects_dir = "projects"
        os.makedirs(self.projects_dir, exist_ok=True)
    
    def get_project_path(self, project_name):
        """Returns the path to the project's JSON file"""
        return os.path.join(self.projects_dir, f"{project_name}.json")
    
    def save_project(self, project_name, brief_content, file_name):
        """Saves or updates project information"""
        project_data = {
            "name": project_name,
            "brief_content": brief_content,
            "original_file": file_name,
            "created_date": datetime.now().isoformat(),
            "submissions": [],
            "status": "In Progress"
        }
        
        with open(self.get_project_path(project_name), 'w') as f:
            json.dump(project_data, f, indent=4)
        
        self.update_projects_list(project_name)
    
    def update_projects_list(self, project_name):
        """Updates the master list of projects"""
        projects_list_path = os.path.join(self.projects_dir, "projects_list.txt")
        projects = set()
        
        if os.path.exists(projects_list_path):
            with open(projects_list_path, 'r') as f:
                projects = set(line.strip() for line in f)
        
        projects.add(project_name)
        
        with open(projects_list_path, 'w') as f:
            for project in sorted(projects):
                f.write(f"{project}\n")
    
    def load_project(self, project_name):
        """Loads project data from JSON file"""
        try:
            with open(self.get_project_path(project_name), 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
    
    # def add_submission(self, project_name, file_path, comments):
    #     """Adds a new submission to the project"""
    #     project_data = self.load_project(project_name)
    #     if project_data:
    #         submission = {
    #             "date": datetime.now().isoformat(),
    #             "file_path": file_path,
    #             "comments": comments,
    #             "status": "Submitted"
    #         }
    #         project_data["submissions"].append(submission)
    #         project_data["status"] = "Submitted"
            
    #         with open(self.get_project_path(project_name), 'w') as f:
    #             json.dump(project_data, f, indent=4)
    #         return True
    #     return False

    def add_submission(self, project_name, file_path, comments, evaluation=None):
        """Adds a new submission to the project with evaluation data"""
        project_data = self.load_project(project_name)
        if project_data:
            submission = {
                "date": datetime.now().isoformat(),
                "file_path": file_path,
                "comments": comments,
                "status": "Evaluated" if evaluation else "Submitted",
                "evaluation": evaluation,  # Add the evaluation data
                "grade": self._extract_grade(evaluation) if evaluation else None  # Optional: Extract numerical grade
            }
            project_data["submissions"].append(submission)
            project_data["status"] = "Evaluated" if evaluation else "Submitted"
            
            with open(self.get_project_path(project_name), 'w') as f:
                json.dump(project_data, f, indent=4)
            return True
        return False

def display_active_project(assignment_manager):
    """Displays the contents of the active project"""
    if "active_project" not in st.session_state:
        st.warning("No active project selected.")
        return
    
    project_data = assignment_manager.load_project(st.session_state["active_project"])
    if not project_data:
        st.warning("Project data not found.")
        return
    
    # Display project information
    st.subheader("Project Details")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Project Name:** {project_data['name']}")
        st.write(f"**Status:** {project_data['status']}")
    with col2:
        st.write(f"**Created:** {datetime.fromisoformat(project_data['created_date']).strftime('%Y-%m-%d %H:%M')}")
        st.write(f"**Original File:** {project_data['original_file']}")
    
    # Display assignment brief
    with st.expander("Assignment Brief", expanded=True):
        st.markdown(project_data['brief_content'])
    
    # Display submission history
    if project_data['submissions']:
        with st.expander("Submission History", expanded=True):
            for idx, submission in enumerate(project_data['submissions'], 1):
                st.write(f"**Submission #{idx}**")
                st.write(f"Date: {datetime.fromisoformat(submission['date']).strftime('%Y-%m-%d %H:%M')}")
                st.write(f"File: {submission['file_path']}")
                if submission['comments']:
                    st.write(f"Comments: {submission['comments']}")
                st.divider()

# def handle_submission(assignment_manager):
    # """Handles the assignment submission process"""
    # if "active_project" not in st.session_state:
    #     st.warning("Please select a project before submitting.")
    #     return
    
    # project_data = assignment_manager.load_project(st.session_state["active_project"])
    # if not project_data:
    #     st.warning("Project data not found.")
    #     return
    
    # st.subheader("Submit Assignment")
    
    # # Display current project info
    # st.write(f"Submitting for project: **{st.session_state['active_project']}**")
    
    # # File upload
    # uploaded_file = st.file_uploader("Upload Assignment (PDF)", type=["pdf"])
    
    # # Submission comments
    # submission_comments = st.text_area("Submission Comments", 
    #                                  placeholder="Add any comments about your submission...")
    
    # if uploaded_file and st.button("Submit Assignment"):
    #     # Save the uploaded file
    #     save_path = os.path.join(assignment_manager.projects_dir, 
    #                            f"{st.session_state['active_project']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
    #     with open(save_path, "wb") as f:
    #         f.write(uploaded_file.getbuffer())
        
    #     # Add submission to project
    #     if assignment_manager.add_submission(st.session_state["active_project"], 
    #                                       uploaded_file.name, 
    #                                       submission_comments):
    #         st.success("Assignment submitted successfully!")
    #         st.balloons()
    #     else:
    #         st.error("Failed to submit assignment. Please try again.")

def handle_submission(assignment_manager):
    """
    Handles the assignment submission process and provides LLM-based evaluation.
    Includes automated grading and feedback based on the original assignment guide.
    """
    if "active_project" not in st.session_state:
        st.warning("Please select a project before submitting.")
        return
    
    project_data = assignment_manager.load_project(st.session_state["active_project"])
    if not project_data:
        st.warning("Project data not found.")
        return
    
    st.subheader("Submit Assignment")
    
    # Display current project info
    st.write(f"Submitting for project: **{st.session_state['active_project']}**")
    
    # File upload
    uploaded_file = st.file_uploader("Upload Assignment (PDF)", type=["pdf"])
    
    # Submission comments
    submission_comments = st.text_area(
        "Submission Comments", 
        placeholder="Add any comments about your submission..."
    )
    
    if uploaded_file and st.button("Submit Assignment"):
        with st.spinner("Processing your submission..."):
            # First, save the uploaded file
            save_path = os.path.join(
                assignment_manager.projects_dir, 
                f"{st.session_state['active_project']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                # Upload the submission to Gemini for analysis
                uploaded_file_gemini = upload_to_gemini(save_path, mime_type="application/pdf")
                wait_for_files_active([uploaded_file_gemini])
                
                if uploaded_file_gemini:
                    # Get the original assignment guide from project data
                    original_guide = project_data['brief_content']
                    
                    # Create evaluation prompt that includes original guide
                    evaluation_prompt = f"""
                    Original Assignment Guide:
                    {original_guide}

                    Task: Analyze the submitted PDF file based on the above criteria and:
                    1. Propose a grade/marks for this submission
                    2. Provide detailed feedback explaining the grade
                    3. Identify specific strengths and areas for improvement
                    4. Give constructive suggestions for enhancement
                    5. Compare the submission against the key requirements outlined in the original guide
                    """
                    
                    # Get the model and create chat session for evaluation
                    model = get_model()
                    chat_session = model.start_chat(
                        history=[{
                            "role": "user",
                            "parts": [uploaded_file_gemini, evaluation_prompt],
                        }]
                    )
                    
                    # Get evaluation response
                    evaluation_response = chat_session.send_message(
                        "Please provide a comprehensive evaluation of this submission."
                    )
                    
                    # Create submission record with evaluation
                    submission = {
                        "date": datetime.now().isoformat(),
                        "file_path": save_path,
                        "comments": submission_comments,
                        "status": "Evaluated",
                        "evaluation": evaluation_response.text
                    }
                    
                    # Update project data with submission
                    if assignment_manager.add_submission(
                        st.session_state["active_project"], 
                        uploaded_file.name, 
                        submission_comments
                    ):
                        st.success("Assignment submitted and evaluated successfully!")
                        
                        # Display evaluation results in an organized manner
                        st.subheader("Assignment Evaluation")
                        with st.expander("View Detailed Evaluation", expanded=True):
                            st.markdown(evaluation_response.text)
                            
                        # Add download button for evaluation report
                        evaluation_report = f"""
                        # Assignment Evaluation Report
                        ## {st.session_state['active_project']}
                        Submission Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
                        
                        {evaluation_response.text}
                        """
                        st.download_button(
                            "Download Evaluation Report",
                            evaluation_report,
                            file_name=f"evaluation_{st.session_state['active_project']}.md",
                            mime="text/markdown"
                        )
                        
                        st.balloons()
                    else:
                        st.error("Failed to save submission. Please try again.")
                
            except Exception as e:
                st.error(f"Error during submission evaluation: {str(e)}")
                st.info("Your submission was saved but couldn't be evaluated. Please contact support.")
            
            finally:
                # Clean up temporary files
                if os.path.exists(save_path):
                    try:
                        os.remove(uploaded_file.name)
                    except:
                        pass

# Main Streamlit App
st.sidebar.title("Agentic Assignment Evaluator")

# Initialize AssignmentManager
assignment_manager = AssignmentManager()

# Initialize session state for active project
if "active_project" not in st.session_state:
    st.session_state["active_project"] = "Untitled Project"

# Display active project name
st.sidebar.write(f"**Active Project:** {st.session_state['active_project']}")

# Projects list in sidebar
with st.sidebar.expander("Projects", expanded=False):
    try:
        projects_list_path = os.path.join(assignment_manager.projects_dir, "projects_list.txt")
        if os.path.exists(projects_list_path):
            with open(projects_list_path, "r") as f:
                projects = [line.strip() for line in f]
                if projects:
                    for project in projects:
                        if st.button(f"{project}"):
                            st.session_state["active_project"] = project
                            st.rerun()
                else:
                    st.write("No saved projects yet.")
        else:
            st.write("No saved projects yet.")
    except Exception as e:
        st.error(f"Error loading projects: {e}")

# Navigation Menu
menu = st.sidebar.radio("Navigation", ["Upload Brief", "View Assignment", "Submit Assignment"])

# Add a divider in the sidebar for visual separation
st.sidebar.divider()

# Add Refresh button at the bottom of the sidebar
if st.sidebar.button("🔄 Refresh", help="Reset the application to its initial state", type="primary"):
    reset_application_state()
    st.rerun()  # Rerun the app to apply the changes

# Main Content
if menu == "Upload Brief":
    st.title("Upload Assignment Brief")
    project_name = st.text_input("Enter a name for this project:", st.session_state["active_project"])
    st.session_state["active_project"] = project_name
    
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_file:
        st.success(f"File '{uploaded_file.name}' uploaded successfully!")
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("Analyzing the brief..."):
            uploaded_file_gemini = upload_to_gemini(uploaded_file.name, mime_type="application/pdf")
            wait_for_files_active([uploaded_file_gemini])
            
            if uploaded_file_gemini:
                model = get_model()
                chat_session = model.start_chat(
                    history=[{
                        "role": "user",
                        "parts": [uploaded_file_gemini, "Please help me with this assignment"],
                    }]
                )
                response = chat_session.send_message("Generate step by step guide for the completion of this assignment")
                st.write(response.text)
                
                if st.button("Save Assignment"):
                    assignment_manager.save_project(project_name, response.text, uploaded_file.name)
                    st.success("Assignment saved successfully!")
        
        os.remove(uploaded_file.name)

elif menu == "View Assignment":
    st.title("View Assignment")
    display_active_project(assignment_manager)

elif menu == "Submit Assignment":
    st.title("Submit Assignment")
    handle_submission(assignment_manager)