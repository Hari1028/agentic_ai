import streamlit as st
import os
import autogen
import json
import logging
import pandas as pd
from typing import Annotated, Dict, Any, Optional

# --- 1. IMPORT LOCAL MODULES & TOOLS --- 
# (Make sure these files are in the same directory or accessible)
from tools.shared.file_info import get_file_metadata
from connection_service.data_connector import read_data_file
from agents.DataProfilerAgent_end_to_end import *
from tools.schema_validator_tool.sv_tools import *
from agents.validation_module import *
from connection_service.databricks_tools import *
# import build_md

# --- 2. CONFIGURE LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 3. LOAD CONFIG ---
from dotenv import load_dotenv
load_dotenv()
API_VERSION = os.getenv("API_VERSION", "2024-02-01")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
API_KEY = os.getenv("API_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "gpt-4.1-nano")

config_list = [
    {
        "model": DEPLOYMENT_NAME,
        "api_key": API_KEY,
        "base_url": AZURE_ENDPOINT,
        "api_type": "azure",
        "api_version": API_VERSION,
    }
]

llm_config = {
    "config_list": config_list,
    "cache_seed": 42,
    "timeout": 300,
}

# --- 3.5. INITIALIZE DB CONNECTION (NEW) ---
logging.info("Initializing Databricks connection...")
DB_ENGINE, ALL_TABLE_SCHEMAS = get_db_objects()

if DB_ENGINE is None:
    logging.error("Failed to initialize Databricks engine. Schema validation tools will fail.")
else:
    logging.info(f"Databricks connection successful. Loaded {len(ALL_TABLE_SCHEMAS)} table schemas.")


# --- 4. TOOL DEFINITIONS ---
# (Your tool definitions are unchanged)

def check_file_support(
    file_path: Annotated[str, "The file path to the CSV, Excel, Parquet, or JSON file"]
) -> Annotated[str, "A JSON string with 'supported': true/false and an optional 'error'"]:
    """Check if the file exists and is a supported file type."""
    logging.info(f"... EXECUTING: check_file_support('{file_path}')...")
    supported_extensions = ['.csv', '.xlsx', '.parquet', '.json']
    result = {}

    if not os.path.exists(file_path):
        logging.warning(f"File not found: {file_path}. Creating dummy file for demo.")
        try:
            result = {"supported": False, "message": "File not found."}
        except Exception as e:
            result = {"supported": False, "error": f"File not found: {file_path}. Failed to create dummy file: {e}"}
    else:
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext not in supported_extensions:
            result = {"supported": False, "error": f"File type {file_ext} is not supported. Supported types: {supported_extensions}"}
        else:
            result = {"supported": True}
            
    return json.dumps(result)

def get_file_information(
    file_path: Annotated[str, "The file path to the data file"]
) -> Annotated[str, "A JSON string with file metadata (size, rows, columns, etc.)"]:
    """Get basic information (metadata, rows, columns) about the file."""
    logging.info(f"... EXECUTING: get_file_information('{file_path}')...")
    try:
        info = get_file_metadata(file_path)
        df = read_data_file(file_path)
        info.update({
            "encoding": "UTF-8", # Mocked
            "language": "Unknown", # Mocked
            "totalRows": len(df),
            "totalColumns": len(df.columns),
        })
        return json.dumps(info)
    except Exception as e:
        logging.error(f"... ERROR in get_file_information: {e}")
        return json.dumps({"error": str(e)})

def run_data_profiling(
    file_path: Annotated[str, "The file path to the data file"],
    sample_size: Annotated[Optional[int], "Number of sample rows to use (default 7)"] = 7
) -> Annotated[str, "A JSON string containing the full data profile report"]:
    """Run data profiling on the file."""
    logging.info(f"... EXECUTING: run_data_profiling('{file_path}')...")
    try:
        profiler_agent = DataProfilerAgent(
            api_version=API_VERSION,
            endpoint=AZURE_ENDPOINT,
            api_key=API_KEY,
            deployment=DEPLOYMENT_NAME
        )
        df = read_data_file(file_path)
        profile = profiler_agent.profile(df, file_path, take_sample_size=7)
        profiler_agent.print_total_token_usage()
        return profile # Assuming it's already a JSON string
    except Exception as e:
        logging.error(f"... ERROR in run_data_profiling: {e}")
        return json.dumps({"error": str(e)})

def get_sheets_name_now(
    file_path: Annotated[str, "The file path to the CSV or Excel file"]
) -> Annotated[str, "A JSON string of the list of sheet names."]:
    """Gets all sheet names from a given Excel file. For a CSV, returns ['csv_data']."""
    logging.info(f"... EXECUTING: get_sheets_name_now('{file_path}')...")
    try:
        sheet_names_list = get_sheet_names(file_path)
        return json.dumps({"sheet_names": sheet_names_list})
    except Exception as e:
        logging.error(f"... ERROR in get_sheets_name_now: {e}")
        return json.dumps({"error": str(e)})

def get_table_recommendations(
    file_path: Annotated[str, "The file path to the CSV or Excel file"],
    sheet_name: Annotated[str, "The specific sheet name to analyze (e.g., 'csv_data' or 'Sheet1')"]
) -> Annotated[str, "A JSON string with table recommendations for that sheet."]:
    """Compares a sheet's schema to all DB tables and returns the top matches."""
    logging.info(f"... EXECUTING: get_table_recommendations('{file_path}', '{sheet_name}')...")
    if DB_ENGINE is None or ALL_TABLE_SCHEMAS is None:
        return json.dumps({"error": "Databricks connection not initialized."})
    try:
        recommendations = get_recommendations_for_sheet(
            file_path=file_path,
            sheet_name=sheet_name,
            all_db_schemas=ALL_TABLE_SCHEMAS
        )
        return json.dumps(recommendations)
    except Exception as e:
        logging.error(f"... ERROR in get_table_recommendations: {e}")
        return json.dumps({"error": str(e)})

def run_full_schema_validation(
    file_path: Annotated[str, "The file path to the CSV or Excel file"],
    sheet_name: Annotated[str, "The specific sheet name to validate (e.g., 'csv_data' or 'Sheet1')"],
    table_name: Annotated[str, "The *exact* target database table name to validate against"]
) -> Annotated[str, "The FULL JSON string validation report."]:
    """Runs the complete validation pipeline for one sheet against one table."""
    logging.info(f"... EXECUTING: run_full_schema_validation('{file_path}', '{sheet_name}', '{table_name}')...")
    if DB_ENGINE is None:
        return json.dumps({"error": "Databricks connection not initialized."})
    try:
        report = run_validation_for_single_sheet(
            file_path=file_path,
            sheet_name=sheet_name,
            table_name=table_name,
            engine=DB_ENGINE
        )
        return json.dumps(report)
    except Exception as e:
        logging.error(f"... ERROR in run_full_schema_validation: {e}")
        return json.dumps({"error": str(e)})

# --- Markdown Conversion Tool (Commented out as in your original) ---
''' ... '''


# -----------------------------------------------------------------
# ------------------- PHASE 2: STREAMLIT APP --------------------
# -----------------------------------------------------------------

def initialize_agents():
    """
    This function creates all your agents and the manager 
    and saves them into st.session_state.
    This is where all the Phase 1 changes are implemented.
    """
    logging.info("--- INITIALIZING AGENTS ---")
    
    # --- 5. AGENT DEFINITIONS (WITH PHASE 1 MODIFICATIONS) ---

    # AGENT 1: The User (MODIFIED FOR STREAMLIT)
    user_proxy = autogen.UserProxyAgent(
        name="StreamlitUser",
        human_input_mode="NEVER",  # <-- PHASE 1 CHANGE
        system_message="A proxy for the human user in Streamlit. You send messages to the group.",
        llm_config=False,
        code_execution_config={"work_dir": "autogen_work_dir", "use_docker": False},
        max_consecutive_auto_reply=0,
    )

    # AGENT: The Executor (Unchanged)
    executor_agent = autogen.UserProxyAgent(
        name="Executor",
        human_input_mode="NEVER",  # Fully autonomous
        max_consecutive_auto_reply=5,
        system_message="""You are the code executor... (rest of your prompt)""",
        code_execution_config={"work_dir": "autogen_work_dir", "use_docker": False},
    )

    # AGENT 2: The Conductor (MODIFIED PROMPT)
    workflow_planner_agent = autogen.AssistantAgent(
        name="WorkflowPlannerAgent",
        llm_config=llm_config,
        system_message="""You are the **WorkflowPlanner**, the primary assistant.
        Your job is to manage the entire workflow, from greeting to final report.

        **YOUR GOAL (The Workflow):**
        1.  **Greet & Validate:** Greet the user. Receive the file path. Call `@InformationValidatorAgent` to check the file.
        2.  **Report Validation:**
            - If validation *fails*, you MUST report the error clearly to the user and stop. Say: "There was an error: [error message]. Please provide a new file. **TERMINATE_CHAT**"
            - If validation *succeeds*, proceed to step 3.
        3.  **Get File Info:** Call `@FileInfoAgent` to get basic file information.
        4.  **Confirm Task:** Present the file info to the user. Check the initial prompt.
            - If the user *already* specified "profile", state what you are doing and call `@DataProfilerAgent`.
            - If the user *already* specified "validate", state what you are doing and call `@SchemaValidatorAgent`.
            - If the user did *not* specify, you MUST ask the user directly: "The file is valid. Would you like to **profile** the data or **validate** its schema? **TERMINATE_CHAT**"
        5.  **Handle Task:**
            - **Profiling:** Call `@DataProfilerAgent`.
            - **Validation:** Call `@SchemaValidatorAgent`. This specialist will handle the multi-step validation. It may return with questions for you to ask the user (like choosing a table). You must act as the intermediary and ask the user: "I have the following table recommendations: [recommendations]. Which table would you like to use? **TERMINATE_CHAT**"
        6.  **Present JSON:** When a specialist (for eg `@DataProfilerAgent`) gives you a final JSON report, you MUST ALWAYS call `@ConversationAgent` to get the human-readable version.
        7.  **Present & Conclude:** Present the final HUMAN-READABLE report from `@ConversationAgent` to the User. Ask "Is there anything else I can help you with? **TERMINATE_CHAT**".

        **CRITICAL RULES:**
        - **ASK ONE QUESTION AT A TIME.**
        - When you need to ask the User a question, you must do it yourself and ALWAYS end your message with the **TERMINATE_CHAT** keyword.
        - ALWAYS format your messages like this:
            __________________________________________ WorkflowPlannerAgent Message __________________________________________
            
                                
                                [Your message here]
            
        """,
    is_termination_msg=lambda x: "TERMINATE_CHAT" in x.get("content", "").upper()
    )

    # AGENT 3: The Validator (Specialist)
    info_validator_agent = autogen.AssistantAgent(
        name="InformationValidatorAgent",
        llm_config=llm_config,
        system_message="""You are a silent specialist. Your only job is to call the `check_file_support` tool.
        Report the JSON result back to the `WorkflowPlannerAgent`."""
    )

    # AGENT 4: The File Info (Specialist)
    file_info_agent = autogen.AssistantAgent(
        name="FileInfoAgent",
        llm_config=llm_config,
        system_message="""You are a silent specialist. Your only job is to call the `get_file_information` tool.
        Report the JSON result back to the `WorkflowPlannerAgent`."""
    )

    # AGENT 5: The Profiler (Specialist)
    data_profiler_agent = autogen.AssistantAgent(
        name="DataProfilerAgent",
        llm_config=llm_config,
        system_message="""You are a silent specialist. Your only job is to call the `run_data_profiling` tool.
        Report the JSON result back to the `ConverstationAgent`."""
    )

    # AGENT 6: The Schema Validator (Specialist) (MODIFIED PROMPT)
    schema_validator_agent = autogen.AssistantAgent(
        name="SchemaValidatorAgent",
        llm_config=llm_config,
        system_message="""You are the **Schema Validation Specialist**.
        You are responsible for the multi-step schema validation workflow.
        You report back to the `ConversationAgent`.

        **YOUR WORKFLOW:**
        1.  You will be given a `file_path` from the WorkflowPlannerAgent.
        2.  First, you MUST call `get_sheets_name_now` to get the list of sheets.
        3.  **FOR EACH SHEET** in the list (e.g., 'csv_data' or 'Sheet1'), you MUST call `get_table_recommendations`.
        4.  After you have the recommendations for all sheets, you ALWAYS MUST report them back to the `ConversationAgent`.
            (e.g., "I have the following recommendations for 'csv_data': [table_a, table_b]. Please select amongst the diven tables to validate."Please select one. TERMINATE_CHAT")
        5.  'ConversationAgent' should ALWAYS ask the User and wait for their response.
        6.  It will automatically trigger 'WorkflowPlannerAgent'.
        7.  The `WorkflowPlannerAgent` will come back to you with the user's choice (a `sheet_name` and a `table_name`).
        8.  You MUST then call `run_full_schema_validation` with the `file_path`, `sheet_name`, and `table_name`.
        9.  Finally, you MUST return the complete, final JSON report to the `ConversationAgent`.
        """ # <-- PHASE 1 CHANGE: Removed '<3' from rule 4
    )

    # AGENT 7: The Report Formatter (Specialist) (MODIFIED PROMPT)
    conversation_agent = autogen.AssistantAgent(
        name="ConversationAgent",
        llm_config=llm_config,
        system_message="""You are a Formatter specialist. Your only job is to convert a JSON report string into a human-readable Markdown report.
        Report the. human-readable string result back to the `User`.
        """, # <-- PHASE 1 CHANGE: Removed '<3' rule
        is_termination_msg=lambda x: "TERMINATE_CHAT" in x.get("content", "").upper()
    ) 
    
    # AGENT 8: The QUESTION Asker (MODIFIED PROMPT)
    

    # --- 6. TOOL REGISTRATION ---
    autogen.register_function(check_file_support, caller=info_validator_agent, executor=executor_agent, name="check_file_support", description="Check if a file exists and is supported.")
    autogen.register_function(get_file_information, caller=file_info_agent, executor=executor_agent, name="get_file_information", description="Get basic file info (rows, cols, etc).")
    autogen.register_function(run_data_profiling, caller=data_profiler_agent, executor=executor_agent, name="run_data_profiling", description="Run the data profiler tool.")
    autogen.register_function(get_sheets_name_now, caller=schema_validator_agent, executor=executor_agent, name="get_sheets_name_now", description="Get all sheet names from an Excel/CSV file.")
    autogen.register_function(get_table_recommendations, caller=schema_validator_agent, executor=executor_agent, name="get_table_recommendations", description="Get DB table recommendations for a specific sheet.")
    autogen.register_function(run_full_schema_validation, caller=schema_validator_agent, executor=executor_agent, name="run_full_schema_validation", description="Run the full schema validation report for a sheet against a table.")
    # autogen.register_function(convert_json_to_markdown, ...) # Still commented out

    # --- 7. GROUP CHAT SETUP (WITH MODIFIED MANAGER) ---
    agents = [
        user_proxy, 
        executor_agent,
        workflow_planner_agent, 
        #user_question_asker_agent,
        info_validator_agent, 
        file_info_agent, 
        data_profiler_agent, 
        schema_validator_agent, 
        conversation_agent
    ]

    group_chat = autogen.GroupChat(
        agents=agents,
        messages=[],  # <-- This list will be our "single source of truth"
        max_round=100,
        speaker_selection_method="auto",
        allow_repeat_speaker=True,
        
    )

    # The manager will use the "auto" method based on the prompts
    manager = autogen.GroupChatManager(
        name="Orchestrator",
        groupchat=group_chat,
        llm_config=llm_config,
        system_message="""You are the Orchestrator. Your job is to select the next agent to speak.
        The `WorkflowPlannerAgent` is the central brain.
        The 'Executor' executes code when tools are called.
        All InitialSpecialists (`InformationValidatorAgent`, `FileInfoAgent`) report back to the `WorkflowPlannerAgent`.
        All Specialists (`DataProfilerAgent`, `SchemaValidatorAgent`, `ConversationAgent`) report back to the `ConversationAgent`.

        **THE FLOW (Follow this precisely):**
        1.  **After the `User` (human) speaks:** YOU MUST ALWAYS select the `WorkflowPlannerAgent`.
        2c. **After that `InitialSpecialist` (`InformationValidatorAgent` or `FileInfoAgent`) speaks:** YOU MUST ALWAYS select the `WorkflowPlannerAgent`.
        2b.  **After a `Specialist` (`DataProfilerAgent` or 'SchemaValidatorAgent') speaks:** YOU MUST ALWAYS select the `ConversationAgent`.
        3.  **After the `Executor` (as executor) posts a tool result (e.g., "***** Response from calling tool *****"):** YOU MUST ALWAYS select the `ConversationAgent`.
        4.  **After the `WorkflowPlannerAgent` speaks:**
            a) If it called a specialist (e.g., "@DataProfilerAgent"), select that specialist.
        
        """ 
    )

    # --- SAVE TO SESSION STATE ---
    st.session_state.user_proxy = user_proxy
    st.session_state.manager = manager
    logging.info("--- AGENTS INITIALIZED AND SAVED TO SESSION STATE ---")


# -----------------------------------------------------------------
# ----------------- PHASE 3: STREAMLIT APP LOGIC ----------------
# -----------------------------------------------------------------

st.title("Data Steward POC 🚀")

# We no longer need the separate "messages" list.
# `st.session_state.manager.groupchat.messages` is the source of truth.

# Initialize agents and manager in session state
if "manager" not in st.session_state:
    with st.spinner("Initializing Data Steward Agents... This may take a moment."):
        initialize_agents()

# --- CHANGE 1: Display chat messages from the manager's history ---
for msg in st.session_state.manager.groupchat.messages:
    # We need to map the agent names to Streamlit "roles"
    # Autogen's "name" is our "role" here.
    # We skip "function" (tool) messages to keep the chat clean
    if msg["role"] == "function":
        continue
    
    # Map the "StreamlitUser" agent to the "user" role
    role = "user" if msg["name"] == "StreamlitUser" else "assistant"
    
    with st.chat_message(role):
        st.markdown(msg["content"])


# --- CHANGE 2: Connect the chat input to the Autogen agents ---
if prompt := st.chat_input("Your turn:"):
    
    # We don't need to manually add the message or display it.
    # The .send() call will add it to the manager's list,
    # and the st.rerun() will cause the loop above to display it.

    with st.spinner("Agents are thinking..."):
        # This one line "sends" the user's message to the agents
        # and runs the *entire* agent conversation
        st.session_state.user_proxy.send(
            message=prompt,
            recipient=st.session_state.manager,
            request_reply=True,  # This tells the manager to run the group chat
            silent=True,         # Set to False if you want to see agent logs in terminal
        )

    # After the agents are done, we just rerun the Streamlit script
    # This will trigger the display loop above to show all new messages
    st.rerun()


# --- 8. RUN THE CHAT ---
# We NO LONGER need the user_proxy.initiate_chat(...) call.
# The `st.chat_input` above has replaced it.