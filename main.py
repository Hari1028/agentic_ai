import logging
import os
import glob
import pandas as pd
import json
import sqlalchemy
import time # Added
import httpx # Added
import openai # Added
import tiktoken # Added
from dotenv import load_dotenv # Added
from openai import AzureOpenAI # Added
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import tools
import prompts

# --- 1. NEW: Load .env and Set Up Logging ---
load_dotenv() # Load environment variables from .env file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 2. NEW: Azure Credentials from your new code ---
# These are now loaded directly from your .env file
API_VERSION = os.getenv("API_VERSION", "2024-02-01") # Added default
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT") 
API_KEY = os.getenv("API_KEY") 
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "gpt-4.1-nano") # Added default/getter

# --- 3. NEW: Global Client with SSL verification disabled ---
# This REPLACES the old client and the need for config.py
# The `verify=False` is the likely fix for your previous connection error.
try:
    if not all([AZURE_ENDPOINT, API_KEY, DEPLOYMENT_NAME]):
        raise ValueError("AZURE_ENDPOINT, API_KEY, or DEPLOYMENT_NAME is not set in .env file.")
    
    # Create a re-usable httpx client with SSL verification disabled
    http_client = httpx.Client(verify=False)
    
    client = AzureOpenAI(
        api_version=API_VERSION,
        azure_endpoint=AZURE_ENDPOINT,
        api_key=API_KEY,
        http_client=http_client, # Pass the custom httpx client
    )
    logging.info(f"Successfully initialized AzureOpenAI client for endpoint: {AZURE_ENDPOINT}")
    logging.info(f"Using Deployment: {DEPLOYMENT_NAME}")
except Exception as e:
    logging.critical(f"Failed to initialize AzureOpenAI client: {e}. Check your .env file.")
    exit(1) # Exit if client fails to initialize


# --- 4. System Prompts (UPDATED) ---
SYSTEM_PROMPT_INSIGHT = """
You are the **Principal Data Steward**, a senior expert in data governance, quality, and pipeline architecture.
Your job is to provide authoritative, context-aware analysis to protect business operations.

You do **NOT** execute any Python functions. You only analyze.

Your tasks are to:
1.  **Connect Disparate Issues:** Do not just list problems. Find the *pattern* between them (e.g., "The null OrderIDs, 'object' type on 'Quantity', and invalid emails all point to a single failed ETL job or a manual data entry error").
2.  **Assess Business Risk:** For each violation, explain the *specific, real-world business impact* (e.g., "Invalid emails will break the customer notification system," "Null PKs will cause data corruption on upsert").
3.  **Form a Root Cause Hypothesis:** Based on the evidence, provide the *most likely real-world source* of the errors. Be specific (e.g., "Manual CSV upload from Sales," "Corrupted Parquet file from data lake," "API integration bug").
4.  **Provide Actionable, Prioritized Plans:** Give a 3-5 step plan ordered by *business criticality*.

You will format your analysis *only* in the specific JSON structure requested.
Do not chat. Provide *only* the requested JSON analysis.
"""

SYSTEM_PROMPT_INTERACTIVE = """
You are a helpful database expert. Your job is to analyze a file schema, compare it to database tables, and ask the user to select the correct one.
"""
def count_tokens(system_prompt, user_prompt, full_response):
    """
    Counts input, output, and total tokens for the API call using tiktoken.
    """
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        
        system_tokens = len(encoding.encode(system_prompt))
        user_tokens = len(encoding.encode(user_prompt))
        input_tokens = system_tokens + user_tokens
        
        output_tokens = len(encoding.encode(full_response))
        total_tokens = input_tokens + output_tokens
        
        # --- [FIX: Changed to print() to ensure visibility] ---
        print("\n" + "-"*30 + " TOKEN COUNT " + "-"*30)
        print(f"[AI-CALL] Input Tokens:  {input_tokens} (System: {system_tokens}, User: {user_tokens})")
        print(f"[AI-CALL] Output Tokens: {output_tokens}")
        print(f"[AI-CALL] Total Tokens:  {total_tokens}")
        print("-"*73 + "\n")
        # --- [END FIX] ---
        
        return input_tokens, output_tokens, total_tokens
        
    except Exception as e:
        print(f"An error occurred during token counting: {e}")
        return 0, 0, 0 # Return 0 if counting fails
# --- 6. NEW: API Calling Function (From your code, with fixes) ---
def get_llm_streaming_response(system_prompt: str, user_prompt: str, max_retries: int = 3) -> Optional[str]:
    """
    Calls the Azure OpenAI API with streaming and retries on RateLimitError.
    This uses the global 'client' and 'DEPLOYMENT_NAME'.
    """
    for attempt in range(max_retries):
        try:
            logging.info(f"Sending prompt to LLM (Attempt {attempt + 1}/{max_retries})...")
            response = client.chat.completions.create(
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=DEPLOYMENT_NAME,
            )

            full_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
            
            # Call the helper function to count and log tokens
            count_tokens(system_prompt, user_prompt, full_response)
                    
            return full_response
        
        except openai.RateLimitError as e:
            sleep_time = 60 * (attempt + 1)
            logging.warning(f"Rate limit hit. Retrying in 60s... ({attempt + 1}/{max_retries})")
            time.sleep(60)
            
        except Exception as e:
            # Log other errors and break the loop (no retry)
            logging.error(f"An error occurred during the AI call: {e}", exc_info=True)
            return None 

    logging.error("Max retries exceeded for RateLimitError. Giving up.")
    return None

# --- 7. Schema History Functions (Unchanged) ---
SCHEMA_HISTORY_DIR = "schema_history"
NUM_HISTORICAL_SCHEMAS_TO_LOAD = 3

def save_schema_to_history(table_name: str, file_schema: Dict[str, Any]):
    # ... (code is identical to previous version) ...
    try:
        safe_table_name = "".join(c if c.isalnum() else "_" for c in table_name)
        os.makedirs(SCHEMA_HISTORY_DIR, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%dT%H%M%SZ')
        filename = f"{safe_table_name}_schema_{timestamp}.json"
        filepath = os.path.join(SCHEMA_HISTORY_DIR, filename)
        schema_to_save = {"columns": file_schema.get("columns", {})}
        with open(filepath, 'w') as f:
            json.dump(schema_to_save, f, indent=2)
        logging.info(f"Saved current schema to history: {filepath}")
    except Exception as e:
        logging.error(f"Error saving schema to history for table '{table_name}': {e}")


def load_historical_schemas(table_name: str, num_history: int) -> List[Dict[str, Any]]:
    # ... (code is identical to previous version) ...
    historical_schemas = []
    try:
        safe_table_name = "".join(c if c.isalnum() else "_" for c in table_name)
        search_pattern = os.path.join(SCHEMA_HISTORY_DIR, f"{safe_table_name}_schema_*.json")
        history_files = sorted(glob.glob(search_pattern), reverse=True)
        files_to_load = history_files[:num_history]
        logging.info(f"Found {len(history_files)} historical schemas for '{table_name}'. Loading the latest {len(files_to_load)}.")
        for file in files_to_load:
            try:
                with open(file, 'r') as f:
                    schema_data = json.load(f)
                    historical_schemas.append(schema_data)
            except Exception as e:
                logging.warning(f"Error loading historical schema file '{file}': {e}")
    except Exception as e:
        logging.error(f"Error searching for historical schemas for table '{table_name}': {e}")
    return historical_schemas

# --- 8. Core Validation Logic (UPDATED) ---

# --- Constants (Unchanged) ---
FILE_PATH = "ironclad.xlsx" 
TABLE_NAME = None 
DB_URL = "sqlite:///database/sample_data.db"

def run_validation_for_sheet(
    df: pd.DataFrame,
    file_path: str,
    sheet_name: Optional[str],
    db_url: str,
    user_provided_table_name: Optional[str]
) -> (Dict[str, Any], Dict[str, Any], Optional[str]):
    """
    Runs the validation process for a single DataFrame (representing a sheet).
    This version now uses the new streaming API function.
    """
    sheet_report = {}
    target_table_name = user_provided_table_name
    schema_analysis_json = {}
    inferred_table_name_sheet = None

    try:
        sheet_display_name = sheet_name if sheet_name is not None else "CSV Data"
        logging.info(f"---  Starting Validation for Sheet: '{sheet_display_name}' ---")

        # --- Step 1 (Sheet): Extract Schema (Unchanged) ---
        file_schema = tools.extract_schema_from_df(df, file_path, sheet_name)
        if "error" in file_schema or not file_schema.get("columns"):
            raise ValueError(f"Schema extraction failed for sheet '{sheet_display_name}'")

        # --- Step 2 (Sheet): Determine Table Name (UPDATED) ---
        if target_table_name is not None:
            logging.info(f"Using user-provided table name: '{target_table_name}'")
        # --- [THIS IS THE NEW CODE BLOCK TO INSERT] ---

        else:
            logging.warning(f"No table name provided. Fetching all table names for user selection...")
            engine = sqlalchemy.create_engine(db_url)
            
            # We still need all_schemas to get the table names
            all_schemas = tools.get_all_table_schemas(engine)
            if not all_schemas:
             raise ValueError("No tables found in database to choose from.")

            # Get the list of available table names
            table_names = list(all_schemas.keys())

            # --- This block replaces the LLM call ---
            logging.info("--- WAITING FOR USER INPUT ---")
            
            print("\n" + "="*80)
            print(f"File: {file_path}" + (f" (Sheet: {sheet_display_name})" if sheet_display_name else ""))
            print("\nNo target table was provided. Please choose a table from the list below:")
            
            # Print the list of tables for the user
            for name in table_names:
                print(f"- {name}")
            
            # Wait for user's response
            user_selection = input("\n> Please type the full name of the table or 'None': ").strip()
            print("="*80)
            # --- End of replacement block ---

            if not user_selection or user_selection.lower() == 'none':
                raise ValueError(f"Process stopped: User confirmed no matching table.")

            # NEW: Add validation to make sure the user's choice is valid
            if user_selection not in table_names:
                logging.error(f"Invalid table name: '{user_selection}' is not in the database.")
                raise ValueError(f"Invalid table: '{user_selection}' is not in the database. Aborting.")

            target_table_name = user_selection
            inferred_table_name_sheet = target_table_name
            logging.info(f"User selected table: '{target_table_name}'")

        # --- Step 3 (Sheet): LLM Schema Analysis (UPDATED) ---
        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 2: LLM Schema Analysis ---")
        engine = sqlalchemy.create_engine(db_url)
        db_schema = tools.get_db_schema(engine, target_table_name)
        if db_schema is None:
            raise ValueError(f"Database table '{target_table_name}' does not exist.")

        raw_comparison = tools.compare_schemas(file_schema, db_schema)
        schema_prompt = prompts.get_schema_analysis_prompt(
            db_schema=db_schema, file_schema=file_schema, raw_comparison=raw_comparison,
            target_table_name=target_table_name, source_file_name=os.path.basename(file_path)
        )
        
        schema_response_str = get_llm_streaming_response(SYSTEM_PROMPT_INSIGHT, schema_prompt)
        if schema_response_str is None:
            raise ValueError("Failed to get schema analysis from LLM.")
        
        try:
            schema_analysis_json = json.loads(schema_response_str)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from schema analysis: {e}\nRaw response: {schema_response_str}")
            raise ValueError("LLM did not return valid JSON for schema analysis.")
            
        logging.info(f"LLM Schema Analysis: Complete")

        # --- Step 4 (Sheet): Deep Validation (Unchanged) ---
        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 3: Deep Validation ---")
        naming_mismatches = schema_analysis_json.get("naming_mismatches", {})
        mapped_df = df.rename(columns=naming_mismatches)
        type_violations = tools.validate_data_types(mapped_df, db_schema)
        dq_violations = tools.run_data_quality_checks(mapped_df, db_schema, engine, target_table_name)
        logging.info(f"Deep validation: Complete")

        # --- Step 4.5 (Sheet): Infer Dynamic Rules (UPDATED) ---
        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 4.5: Inferring Dynamic Rules ---")
        dynamic_rules = []
        try:
            dynamic_rules_prompt = prompts.get_dynamic_rules_prompt(file_schema)
            dynamic_rules_str = get_llm_streaming_response(SYSTEM_PROMPT_INSIGHT, dynamic_rules_prompt)
            if dynamic_rules_str:
                dynamic_rules = json.loads(dynamic_rules_str)
            logging.info(f"LLM Dynamic Rules: Complete")
        except Exception as e:
            logging.warning(f"Could not generate dynamic rules: {e}")
            dynamic_rules = [{"error": "Failed to generate dynamic rules"}]

        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 5: Assembling Violation Summary ---")
        def _create_violation_summary(types, dq):
            summary = {
                "type_mismatch_summary": [
                    {"column": v["column"], "expected": v["expected_db_type"], "found": v["found_file_type"]}
                        for v in types
                    ],
                "data_quality_issue_summary": [
                    {"column": v["column"], "check": v["check"], "count": v["count"], "severity": v.get("severity", "medium")}
                        for v in dq
                    ]
            }
            return summary

        violations_summary = _create_violation_summary(type_violations, dq_violations)

# --- [NEW] Step 6: Build Base Report (Python) ---
        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 6: Building Base Report ---")
        file_metadata = {"file_name": os.path.basename(file_path), "sheet_name": sheet_name, "total_rows": file_schema.get("total_rows")}

        # This is our final JSON object, assembled in Python for free
        base_report = {
            "file_name": file_metadata.get("file_name"),
            "sheet_name": file_metadata.get("sheet_name"),
            "total_rows_checked": file_metadata.get("total_rows"),
            "validated_at": datetime.now(timezone.utc).isoformat(),

            # Dump the raw, detailed violation lists directly
            "data_type_mismatch": type_violations,
            "data_quality_issues": dq_violations,
            "dynamic_validation_rules": dynamic_rules,

            # These keys are placeholders. The LLM will fill them.
            "validation_summary": {},
            "data_quality_score": {},
            "triage_plan": [],
            "append_upsert_suggestion": {},
            "schema_drift": {},
            "root_cause_analysis": {},
            "overall_analysis": {}
        }

 # --- [NEW] Step 7: LLM Final Analysis (Cheap) ---
        logging.info(f"--- [Sheet '{sheet_display_name}'] Step 7: Calling LLM for Final Analysis ---")
        historical_schemas = load_historical_schemas(target_table_name, NUM_HISTORICAL_SCHEMAS_TO_LOAD)

# Use the NEW prompt function
        analysis_prompt = prompts.get_analysis_prompt(
        schema_analysis=schema_analysis_json,
        violations_summary=violations_summary,
        historical_schemas=historical_schemas
        )

        analysis_response_str = get_llm_streaming_response(SYSTEM_PROMPT_INSIGHT, analysis_prompt)
        if analysis_response_str is None:
            raise ValueError("Failed to get final analysis from LLM.")

        try:
 # This is the SMALL JSON from the LLM
            llm_analysis_json = json.loads(analysis_response_str)
            base_report.update(llm_analysis_json)

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON from final analysis: {e}\nRaw response: {analysis_response_str}")
            # If it fails, we still have the base report with raw data
            base_report["validation_summary"] = {"status": "Error", "details": "LLM analysis parsing failed."}

 # Save schema history (this is unchanged)
        if target_table_name:
            save_schema_to_history(target_table_name, file_schema)

        logging.info(f"--- Sheet '{sheet_display_name}' Validation Complete ---")

 # IMPORTANT: Make sure to return the base_report
        sheet_report = base_report
    except Exception as e:
        logging.error(f"---  ERROR during validation for Sheet '{sheet_display_name}': {e} ---", exc_info=True)
        sheet_report = {
            "file_name": file_path, "sheet_name": sheet_name,
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "validation_summary": { "status": "Error", "details": str(e) },
            "error": str(e)
        }
    
    return sheet_report, schema_analysis_json, inferred_table_name_sheet


# --- 9. Main Runner Function (Unchanged from last version) ---
def run_multi_sheet_validation(file_path: str, db_url=DB_URL, user_provided_table_name: Optional[str] = None):
    """
    Handles CSV or multi-sheet Excel validation by iterating through sheets.
    """
    logging.info(f"---  STARTING VALIDATION FOR FILE: {file_path} ---")
    if user_provided_table_name:
        logging.info(f"User provided target table: '{user_provided_table_name}'")
    else:
        logging.info("User did not provide target table. Will infer table per sheet.")

    try:
        sheet_names: List[Optional[str]] = []
        is_excel = file_path.endswith(('.xls', '.xlsx'))

        if is_excel:
            xls = pd.ExcelFile(file_path)
            sheet_names = xls.sheet_names
            logging.info(f"Detected Excel file with sheets: {sheet_names}")
            if not sheet_names:
                logging.warning(f"Excel file '{file_path}' contains no sheets.")
                return
        else:
            sheet_names = [None] # Placeholder for CSV
            logging.info(f"Detected CSV file: {file_path}")

        all_sheet_reports: Dict[str, Dict] = {}
        first_schema_mismatch = {}
        inferred_target_table = None
        
        for sheet_name in sheet_names:
            current_df = None
            sheet_display_name = sheet_name if sheet_name is not None else "CSV Data"
            try:
                logging.info(f"--- Loading data for sheet: '{sheet_display_name}' ---")
                current_df = pd.read_excel(file_path, sheet_name=sheet_name) if is_excel else pd.read_csv(file_path)
                
                sheet_report, schema_analysis_json, inferred_table = run_validation_for_sheet(
                    df=current_df, file_path=file_path, sheet_name=sheet_name,
                    db_url=db_url, user_provided_table_name=user_provided_table_name
                )
                report_key = sheet_name if sheet_name is not None else "csv_data"
                if report_key != "csv_data":
                    ordered_sheet_report = {}

                    if "file_name" in sheet_report:
                        ordered_sheet_report["file_name"] = sheet_report.pop("file_name")
                    if "sheet_name" in sheet_report:
                        ordered_sheet_report["sheet_name"] = sheet_report.pop("sheet_name")
                    ordered_sheet_report["schema_mismatch"] = schema_analysis_json
                    ordered_sheet_report.update(sheet_report)                    
                    all_sheet_reports[report_key] = ordered_sheet_report
                else:
                    all_sheet_reports[report_key] = sheet_report
                if not first_schema_mismatch: first_schema_mismatch = schema_analysis_json
                if not inferred_target_table and inferred_table: inferred_target_table = inferred_table
                
            except Exception as e:
                logging.error(f"Failed to process sheet '{sheet_display_name}': {e}", exc_info=True)
                # ... (error handling) ...

        # --- Final Output Assembly (Unchanged) ---
        base_file_name = os.path.basename(file_path)
        if is_excel:
            final_output = {
                "User_file_name": base_file_name,
                "Processed_at": datetime.now(timezone.utc).isoformat(),
                "user_provided_target_table": user_provided_table_name,
                "inferred_target_table": inferred_target_table,
                "sheet_validation_results": all_sheet_reports
            }
        else:
            csv_report_data = all_sheet_reports.get("csv_data", {})
            schema_mismatch_data = first_schema_mismatch
            final_output = {
                "User_file_name": base_file_name,
                "Processed_at": datetime.now(timezone.utc).isoformat(),
                "user_provided_target_table": user_provided_table_name,
                "inferred_target_table": inferred_target_table,
                "schema_mismatch": schema_mismatch_data
            }
            final_output.update(csv_report_data)
        
        logging.info("--- [Step 5: Complete Validation Report] ---")
        print("="*80)
        print(" SCHEMA VALIDATOR POC - FINAL REPORT - [CONVERTED VERSION]")
        print("="*80)
        final_report_str_pretty = json.dumps(final_output, indent=2)
        print(final_report_str_pretty)

        with open("validation_report_converted.json", "w") as f:
            f.write(final_report_str_pretty) 
        logging.info("Combined report saved to validation_report_converted.json")
        return final_output

    except Exception as e:
        logging.error(f"A critical error occurred: {e}", exc_info=True)

# --- 10. Main Entry Point (Unchanged) ---
if __name__ == "__main__":
    # This runs our main validation logic, NOT the test joke
    run_multi_sheet_validation(file_path=FILE_PATH, user_provided_table_name=TABLE_NAME)
