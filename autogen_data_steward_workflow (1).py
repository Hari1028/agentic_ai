import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import pandas as pd
import json
import logging
import asyncio

# AutoGen imports (using the latest autogen-agentchat)
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_agentchat.messages import TextMessage
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

# --- NEW ---
# Imports from ALL your real code files
#
# === IMPORTANT ===
# I am assuming you have renamed your files as follows:
# 1. Your original `prompts.py` -> `prompts_steward.py`
# 2. Your original `build_md.py` -> `build_md_steward.py`
# 3. Your friend's `prompts (2).py` -> `prompts_profiler.py`
# 4. Your friend's `build_md (1).py` -> `build_md_profiler.py`
# 5. Your `validation_module.py` and `DataProfilerAgent_end_to_end.py`
#    (and their helpers like `tools.py`, `rules.py`) are in the same folder.
# === === === === ===

# Core Validator Modules
import validation_module
import build_md_steward

# Core Profiler Modules
from file_info import get_file_metadata
from data_connector import read_data_file
from DataProfilerAgent_end_to_end import DataProfilerAgent
import build_md_profiler


# ===================== LOGGING CONFIGURATION =====================
# (This section is unchanged from your new file)
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(levelname)s: %(message)s'
)
from autogen_core import TRACE_LOGGER_NAME, EVENT_LOGGER_NAME
logging.getLogger(TRACE_LOGGER_NAME).setLevel(logging.ERROR)
logging.getLogger(EVENT_LOGGER_NAME).setLevel(logging.ERROR)
logging.getLogger("autogen").setLevel(logging.ERROR)
logging.getLogger("autogen_core").setLevel(logging.ERROR)
logging.getLogger("autogen_agentchat").setLevel(logging.ERROR)
logging.getLogger("autogen_ext").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("openai").setLevel(logging.ERROR)

# Load environment variables
load_dotenv()
API_VERSION = os.getenv("API_VERSION", "2024-02-01")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
API_KEY = os.getenv("API_KEY")
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "gpt-4.1-nano")

# Configuration for Azure OpenAI
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

# Create Azure OpenAI model client
model_client = AzureOpenAIChatCompletionClient(
    model=DEPLOYMENT_NAME,
    api_key=API_KEY,
    azure_endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION,
)

# ===================== TOOL DEFINITIONS =====================
# These are the real tools that plug into your code.

async def check_file_support(file_path: str) -> Dict[str, Any]:
    """
    (Unchanged) Check if the file exists and is supported.
    """
    import os
    # --- CHANGED --- Added your validator's supported types
    supported_extensions = ['.csv', '.xlsx', '.xls', '.xlsm'] # .parquet and .json removed for now

    if not os.path.exists(file_path):
        return {"supported": False, "error": f"File not found: {file_path}"}

    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in supported_extensions:
        return {
            "supported": False,
            "error": f"File type {file_ext} is not supported. Supported types: {supported_extensions}"
        }

    return {"supported": True, "message": "File is supported and exists."}


async def file_info(file_path: str) -> Dict[str, Any]:
    """
    --- CHANGED ---
    This tool now calls your *real* file_info and data_connector code.
    """
    try:
        # 1. Get metadata from your real tool
        info = get_file_metadata(file_path)
        
        # 2. Get row/column counts from your real tool
        df = read_data_file(file_path)
        
        # 3. Combine them
        info.update({
            "totalRows": len(df),
            "totalColumns": len(df.columns),
            "columns": list(df.columns),
        })
        return info
    except Exception as e:
        return {"error": f"Failed to get file info: {str(e)}"}


async def run_data_profiling(file_path: str) -> str:
    """
    --- CHANGED ---
    This tool now runs your *real* DataProfilerAgent.
    """
    print("\n--- EXECUTING: Real Data Profiler Tool ---")
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        # 1. Instantiate your friend's agent
        profiler_agent_class = DataProfilerAgent(
            api_version=API_VERSION,
            endpoint=AZURE_ENDPOINT,
            api_key=API_KEY,
            deployment=DEPLOYMENT_NAME
        )

        # 2. Read the data
        df = read_data_file(file_path)

        # 3. Run the full profile (this is a blocking, synchronous call)
        # We run it in a thread to be safe for asyncio
        profile = await asyncio.to_thread(
            profiler_agent_class.profile,
            df,
            file_path,
            take_sample_size=7
        )
        
        profiler_agent_class.print_total_token_usage()
        
        # 4. Return the full JSON report
        return json.dumps(profile, indent=2, default=str)
        
    except Exception as e:
        logging.error(f"--- ERROR in run_data_profiling: {e}")
        return json.dumps({"error": f"Failed to read or profile file: {str(e)}"})


async def run_schema_validation(file_path: str, table_name: Optional[str] = None) -> str:
    """
    --- CHANGED ---
    This tool now runs your *real* Data Steward validation module.
    """
    print("\n--- EXECUTING: Real Schema Validator Tool ---")
    try:
        # 1. Call your real validation module
        # This is a blocking, synchronous call, so we run it in a thread.
        final_report_dict = await asyncio.to_thread(
            validation_module.run_multi_sheet_validation,
            file_path=file_path,
            user_provided_table_name=table_name
        )
        
        # 2. Return the full JSON report
        return json.dumps(final_report_dict, indent=2, default=str)
    except Exception as e:
        logging.error(f"--- ERROR in run_schema_validation: {e}")
        return json.dumps({"error": f"Schema validation failed: {str(e)}"})


async def convert_json_to_markdown(json_data: str) -> str:
    """
    --- CHANGED ---
    This is now a "smart" tool that detects the report type
    and calls the correct markdown builder.
    """
    print("\n--- EXECUTING: Smart Markdown Converter Tool ---")
    try:
        data = json.loads(json_data)
        
        # --- Smart Logic ---
        
        # 1. Check if it's a VALIDATOR report
        # (These are keys unique to your validation_module.py output)
        if "sheet_validation_results" in data or "schema_mismatch" in data:
            print("--- Detected: Validator Report. Calling build_md_steward.py ---")
            # Call your original validator markdown script
            return build_md_steward.create_validation_markdown(data)
        
        # 2. Check if it's a PROFILER report
        # (These are keys unique to your friend's profiler output)
        elif "file_info" in data and "data_quality" in data and "columns" in data:
            print("--- Detected: Profiler Report. Calling build_md_profiler.py ---")
            # Call your friend's profiler markdown script
            return build_md_profiler.create_profile_markdown(data)
        
        # 3. Check for a simple error
        elif "error" in data:
            return f"# Error Report\n\nAn error occurred:\n\n```\n{data['error']}\n```"
            
        else:
            return "# Unknown Report Type\n\nCould not determine if this was a Validator or Profiler report."

    except Exception as e:
        return f"# Error Converting to Markdown\n\n{str(e)}"


# ===================== AGENT DEFINITIONS =====================

# 1. UserAssistantAgent - Primary user-facing agent
user_assistant_agent = AssistantAgent(
    name="UserAssistantAgent",
    model_client=model_client,
    description="Primary interface for user interaction, gathering requirements and presenting results",
    system_message="""You are a friendly, helpful UserAssistantAgent. Your role is to:

1. GREETING PHASE: Start by greeting the user warmly and asking how you can help them.

2. INFORMATION GATHERING PHASE:
   - First, ask for the file_path
   - Then ask what they want to do with the file
   - Identify if they want to: profile data OR validate schema
   - If unclear from their response, explicitly ask: "Would you like me to profile the data or validate the schema?"
   - **If they say 'validate'**, you MUST ask for the `table_name`.
   - If they say 'profile', no more info is needed.

3. HANDOFF PHASE: Once you have all information (file_path + task type + table_name if needed), say:
   "I have all the information needed. Let me hand this over to the WorkflowPlannerAgent to coordinate the analysis."
   Then explicitly mention: "WorkflowPlannerAgent, please take over."

4. PRESENTATION PHASE: When you receive the final report, present it in a friendly, easy-to-understand manner.

5. CLOSING PHASE: After presenting results, ask: "Is there anything else I can help you with?"

IMPORTANT RULES:
- Ask ONE question at a time
- Be conversational and friendly
- Always confirm what you've gathered before handing off to WorkflowPlannerAgent
- When closing, if user says "no" or similar, end with: "Thank you! TERMINATE"
""",
)

# 2. WorkflowPlannerAgent - Orchestrates the entire workflow
workflow_planner_agent = AssistantAgent(
    name="WorkflowPlannerAgent",
    model_client=model_client,
    description="Central orchestrator managing the entire workflow and coordinating all specialist agents",
    system_message="""You are the WorkflowPlannerAgent, the MANAGER and ORCHESTRATOR of all specialist agents.
You do NOT interact with users directly - you coordinate all other agents.

YOUR WORKFLOW (execute in this EXACT order):

STEP 1: ACKNOWLEDGE HANDOFF
- When UserAssistantAgent hands off the task, acknowledge the file_path and task type
- Say: "Acknowledged. Starting workflow for [file_path] with task: [profile/validate]"

STEP 2: FILE VALIDATION
- Call InformationValidatorAgent by saying: "InformationValidatorAgent, please validate the file."
- Wait for response
- If VALIDATION_FAILED: Call ConversationFlowAgent to humanize the error
- If VALIDATION_SUCCESS: Proceed to Step 3

STEP 3: FILE INFORMATION
- Call FileInfoAgent by saying: "FileInfoAgent, please retrieve file information."
- Wait for FILE_INFO_COMPLETE response
- Proceed to Step 4

STEP 4: TASK EXECUTION
- Based on the original task type from UserAssistantAgent:
  * If "profile" or "analyze": Call DataProfilerAgent by saying: "DataProfilerAgent, please profile the data."
  * If "validate" or "schema": Call SchemaValidatorAgent by saying: "SchemaValidatorAgent, please validate the schema."
- Wait for COMPLETE response with JSON data
- Proceed to Step 5

STEP 5: FORMAT REPORT
- Call MarkdownAgent by saying: "MarkdownAgent, please format this JSON report."
- Pass the JSON data received from profiler/validator
- Wait for MARKDOWN_READY response
- Proceed to Step 6

STEP 6: HUMANIZE AND PRESENT
- Call ConversationFlowAgent by saying: "ConversationFlowAgent, please make this report user-friendly."
- Then call UserAssistantAgent by saying: "UserAssistantAgent, please present this report to the user."

CRITICAL RULES:
- Always explicitly name the next agent you're calling
- Track the workflow state carefully
- Handle errors gracefully by routing through ConversationFlowAgent
""",
)

# 3. InformationValidatorAgent - Validates file existence and support
information_validator_agent = AssistantAgent(
    name="InformationValidatorAgent",
    model_client=model_client,
    description="Validates file existence and format support",
    system_message="""You are the InformationValidatorAgent. Your responsibility is file validation.

When called by WorkflowPlannerAgent:
1. Extract the file_path from the conversation history
2. Call the check_file_support tool with the file_path
3. Report results clearly:
   - If successful: "VALIDATION_SUCCESS: File is supported and exists at [file_path]."
   - If failed: "VALIDATION_FAILED: [specific error message]"
4. Return control by saying: "WorkflowPlannerAgent, validation complete."

Be concise and technical. Only report validation status.
""",
    tools=[check_file_support],
)

# 4. FileInfoAgent - Retrieves file metadata
file_info_agent = AssistantAgent(
    name="FileInfoAgent",
    model_client=model_client,
    description="Retrieves detailed file metadata and basic information",
    system_message="""You are the FileInfoAgent. Your responsibility is to gather file information.

When called by WorkflowPlannerAgent:
1. Extract the file_path from the conversation history
2. Call the file_info tool
3. Report: "FILE_INFO_COMPLETE: [JSON response from tool]"
4. Return control by saying: "WorkflowPlannerAgent, file info retrieved."

Be technical and concise.
""",
    tools=[file_info],
)

# 5. DataProfilerAgent - Runs data profiling
data_profiler_agent = AssistantAgent(
    name="DataProfilerAgent",
    model_client=model_client,
    description="Specialist in comprehensive data profiling and quality analysis",
    # --- CHANGED ---
    system_message="""You are a specialist. When called by WorkflowPlannerAgent:
1. Extract the file_path from conversation history.
2. Your **only** job is to call the `run_data_profiling` tool with the file_path.
3. Return the **entire, raw JSON string** to the `WorkflowPlannerAgent`.
4. Say: "WorkflowPlannerAgent, profiling complete. Here's the JSON report: [include full JSON]"
Do not add any other text.
""",
    tools=[run_data_profiling],
)

# 6. SchemaValidatorAgent - Runs schema validation
schema_validator_agent = AssistantAgent(
    name="SchemaValidatorAgent",
    model_client=model_client,
    description="Specialist in schema validation and data structure verification",
    # --- CHANGED ---
    system_message="""You are a specialist. When called by WorkflowPlannerAgent:
1. Extract the file_path and table_name (if provided) from conversation history.
2. Your **only** job is to call the `run_schema_validation` tool.
3. Return the **entire, raw JSON string** to the `WorkflowPlannerAgent`.
4. Say: "WorkflowPlannerAgent, validation complete. Here's the JSON report: [include full JSON]"
Do not add any other text.
""",
    tools=[run_schema_validation],
)

# 7. MarkdownAgent - Converts JSON to Markdown
markdown_agent = AssistantAgent(
    name="MarkdownAgent",
    model_client=model_client,
    description="Formats technical JSON reports into readable Markdown documentation",
    # --- CHANGED ---
    system_message="""You are a specialist. When called by WorkflowPlannerAgent:
1. Receive the JSON data from the conversation.
2. Your **only** job is to call the `convert_json_to_markdown` tool with the JSON data.
3. This tool is smart and will do all the formatting.
4. Return the **entire Markdown string** to the `WorkflowPlannerAgent`.
5. Say: "WorkflowPlannerAgent, markdown formatting complete. Here's the report: [include full Markdown]"
Do not add any other text.
""",
    tools=[convert_json_to_markdown],
)

# 8. ConversationFlowAgent - Humanizes technical messages
conversation_flow_agent = AssistantAgent(
    name="ConversationFlowAgent",
    model_client=model_client,
    description="Converts technical messages to user-friendly language",
    # --- CHANGED ---
    system_message="""You are the ConversationFlowAgent. You make messages user-friendly.
You must follow **two rules**:

1.  **If you receive a short error message** (like "VALIDATION_FAILED: File not found..."):
    Rewrite it to be friendly and helpful.
    Example: "I ran into an error: it looks like the file wasn't found. Could you please double-check the file path?"

2.  **If you receive a large, formatted Markdown report** (it will start with `#`):
    Do **NOT** change, summarize, or rewrite it.
    Your only job is to pass the *entire, unchanged* Markdown report to the `UserAssistantAgent` with a simple, friendly introduction.
    Example: "Great, the analysis is complete! Here is the detailed report for your file:"
    
After humanizing, pass control by saying: "UserAssistantAgent, please present this message: [your friendly version or intro + the full markdown]"
""",
)


# ===================== CUSTOM CONSOLE OUTPUT =====================
# (This section is unchanged from your new file)

class CleanConsole:
    """Custom console that only shows agent messages without verbose logging"""
    
    def __init__(self, stream):
        self.stream = stream
        
    async def __call__(self):
        """Process and display only relevant messages"""
        print("\n" + "="*80)
        print("AGENT CONVERSATION")
        print("="*80 + "\n")
        
        async for message in self.stream:
            # Only show TextMessage content from agents
            if hasattr(message, 'source') and hasattr(message, 'content'):
                source = message.source
                content = str(message.content)
                
                # Skip system messages and verbose tool outputs
                if source and source != "user" and not content.startswith("{"):
                    print(f"\n[{source}]")
                    print("-" * 80)
                    print(content)
                    print()


# ===================== TEAM SETUP =====================
# (This section is unchanged from your new file)

def create_data_steward_team():
    """
    Create and configure the data steward agent team with SelectorGroupChat.
    
    Returns:
        Configured SelectorGroupChat team
    """
    
    # Termination condition - increased to allow full workflow
    termination_condition = TextMentionTermination("TERMINATE") | MaxMessageTermination(100)
    
    # Selector prompt to guide the LLM in agent selection
    selector_prompt = """You are managing a data steward workflow with the following agents:

1. **UserAssistantAgent**: Interacts with user, gathers file_path and task requirements
2. **WorkflowPlannerAgent**: Central orchestrator, coordinates all other agents
3. **InformationValidatorAgent**: Validates file existence and format
4. **FileInfoAgent**: Retrieves file metadata
5. **DataProfilerAgent**: Performs data profiling analysis
6. **SchemaValidatorAgent**: Performs schema validation
7. **MarkdownAgent**: Formats JSON reports to Markdown
8. **ConversationFlowAgent**: Humanizes technical messages

**WORKFLOW**:
- Start: UserAssistantAgent greets user and gathers information
- User provides: file_path and task (profile or validate)
- UserAssistantAgent hands off to WorkflowPlannerAgent
- WorkflowPlannerAgent orchestrates: InformationValidatorAgent → FileInfoAgent → (DataProfilerAgent OR SchemaValidatorAgent) → MarkdownAgent → ConversationFlowAgent → UserAssistantAgent
- UserAssistantAgent presents results and asks if user needs anything else

**AGENT SELECTION RULES**:
- If last message is from user → select UserAssistantAgent
- If UserAssistantAgent mentions "WorkflowPlannerAgent" → select WorkflowPlannerAgent
- If WorkflowPlannerAgent explicitly names an agent → select that agent
- If specialist agent (Validator, FileInfo, Profiler, SchemaValidator, Markdown) completes → select WorkflowPlannerAgent
- If ConversationFlowAgent completes → select UserAssistantAgent
- Default orchestrator: WorkflowPlannerAgent

The WorkflowPlannerAgent is the manager who coordinates all specialist agents.
"""
    
    team = SelectorGroupChat(
        participants=[
            user_assistant_agent,
            workflow_planner_agent,
            information_validator_agent,
            file_info_agent,
            data_profiler_agent,
            schema_validator_agent,
            markdown_agent,
            conversation_flow_agent,
        ],
        model_client=model_client,
        termination_condition=termination_condition,
        selector_prompt=selector_prompt,
        allow_repeated_speaker=True,  # Allow agents to speak multiple times
    )
    
    return team


# ===================== MAIN EXECUTION =====================
# (This section is unchanged from your new file)

async def main():
    """
    Main execution function for the Data Steward agentic workflow.
    """
    print("\n" + "=" * 80)
    print("DATA STEWARD AGENTIC WORKFLOW")
    print("=" * 80)
    print("\nInitializing agents...")
    
    # Create the team
    team = create_data_steward_team()
    
    # Initial greeting - UserAssistantAgent will greet and start gathering info
    initial_task = "Hello! Welcome to the Data Steward Assistant."
    
    # Run the conversation with clean console output
    stream = team.run_stream(task=initial_task)
    
    # Use custom clean console instead of default verbose Console
    clean_console = CleanConsole(stream)
    await clean_console()
    
    print("\n" + "=" * 80)
    print("Workflow Complete")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())