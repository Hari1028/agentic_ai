import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta


# ==============================================================
# 1️⃣ SCHEMA ANALYSIS PROMPT
# ==============================================================

SCHEMA_ANALYSIS_PROMPT = """
You are an expert Data Validation Agent. Your task is to analyze a schema mismatch report and provide intelligent, context-aware recommendations.

You will be given:
1.  **Target Table**: The database table we are validating against ({target_table_name}).
2.  **Source File**: The file being validated ({source_file_name}).
3.  **DB Schema**: The target database table schema (columns, types, constraints).
4.  **File Schema**: The schema extracted from the user's file (columns, inferred types, sample values).
5.  **Raw Comparison**: A simple list of columns that are 'missing' or 'extra' based on an exact name match.

Your Job:
1.  **Semantic Mapping**: Go beyond exact matches. Identify columns in the File Schema that are semantically similar to columns in the DB Schema (e.g., 'cust' -> 'CustomerID', 'qty' -> 'Quantity').
2.  **Analyze Mismatches**: Re-evaluate the 'missing' and 'extra' columns after accounting for your semantic mapping.
3.  **Generate Insights**: For each mismatch, provide clear reasoning for the problem and actionable recommendations.
4.  **Format Output**: Return *ONLY* a single JSON object (no extra text or markdown) matching the structure below.

---
[INPUT DATA]

**Target Table**: {target_table_name}
**Source File**: {source_file_name}

**Database Schema (Target):**
{db_schema_json}

**File Schema (Source):**
{file_schema_json}

**Raw Comparison (Exact Match):**
{raw_comparison_json}

---
[YOUR ANALYSIS]

Produce a single JSON object in this *exact* format.
**CRITICAL:** For 'naming_mismatches', the key MUST be the column from the File Schema and the value MUST be the column from the Database Schema.

Format: {{"file_column_name": "db_column_name"}}
Example: {{"cust": "CustomerID", "qty": "Quantity"}}

{{
  "target_table": "{target_table_name}",
  "source_file": "{source_file_name}",
  "columns_missing_from_file": [
    "List_of_DB_columns_TRULY_missing_after_mapping"
  ],
  "columns_extra_in_file": [
    "List_of_File_columns_TRULY_extra_after_mapping"
  ],
  "naming_mismatches": {{
    "file_col_1_name": "db_col_1_name",
    "file_col_2_name": "db_col_2_name"
  }},
  "analysis": {{
    "context": "Brief summary of the findings (e.g., 'File is missing X, has extra Y, and 2 columns were semantically mapped.')",
    "reasoning": "Explain the *impact* of these mismatches (e.g., 'Missing 'DiscountCode' may cause incomplete data. Extra 'ShippingMethod' is not in the DB.')",
    "recommendation": [
      "Actionable step 1 (e.g., 'Map 'cust' to 'CustomerID' for loading.')",
      "Actionable step 2 (e.g., 'Add 'DiscountCode' to the source file or set a default value.')",
      "Actionable step 3 (e.g., 'Verify if 'ShippingMethod' should be added to the database table.')"
    ]
  }}
}}
"""

def get_schema_analysis_prompt(
    db_schema: Dict[str, Any],
    file_schema: Dict[str, Any],
    raw_comparison: Dict[str, List[str]],
    target_table_name: str,
    source_file_name: str
) -> str:
    """Helper function to format the schema analysis prompt."""

    file_schema_columns = file_schema.get('columns', {})
    try:
        return SCHEMA_ANALYSIS_PROMPT.format(
            target_table_name=target_table_name,
            source_file_name=source_file_name,
            db_schema_json=json.dumps(db_schema, indent=2, default=str),
            file_schema_json=json.dumps(file_schema_columns, indent=2, default=str),
            raw_comparison_json=json.dumps(raw_comparison, indent=2, default=str)
        )
    except KeyError as e:
        logging.error(f"Missing key in SCHEMA_ANALYSIS_PROMPT format string: {e}")
        return "ERROR: Prompt formatting failed. Check schema analysis prompt template keys."
    except Exception as e:
        logging.error(f"Error formatting SCHEMA_ANALYSIS_PROMPT: {e}")
        return "ERROR: Could not format schema analysis prompt."


# ==============================================================
# 2️⃣ DYNAMIC RULES PROMPT
# ==============================================================

DYNAMIC_RULES_PROMPT = """
You are a Data Analyst. Your only task is to infer potential validation rules by analyzing sample data from a file.

You will be given:
1.  **Current File Schema**: A JSON object showing columns, inferred types, and sample data.

Your Job:
1.  Analyze the `sample_values` for each column.
2.  Infer potential new validation rules (format checks, enum lists, range checks).
3.  Return *ONLY* a single JSON list of rule objects. Do not add any other text, markdown, or explanations.

---
[INPUT DATA]

**Current File Schema (Source):**
{current_file_schema_json}

---
[YOUR ANALYSIS]

Produce a single JSON list in this *exact* format:

[
  {{
    "column": "ColumnName",
    "rule_type": "[format_check | enum_check | range_check]",
    "inferred_from_samples": ["sample1", "sample2"],
    "rule_details": "Explain the inferred rule. E.g., 'Based on X/Y samples, this column appears to follow a regex format: ^[A-Z]{{3}}\\d{{4}}$' OR 'Column appears to be categorical. All samples were from the list: [\"ValueA\", \"ValueB\"]'"
  }}
]
"""

def get_dynamic_rules_prompt(
    current_file_schema: Dict[str, Any]
) -> str:
    """Helper function to format the dynamic rules prompt."""

    current_file_schema_cols = current_file_schema.get('columns', {})
    try:
        return DYNAMIC_RULES_PROMPT.format(
            current_file_schema_json=json.dumps(current_file_schema_cols, indent=2, default=str)
        )
    except KeyError as e:
        logging.error(f"Missing key in DYNAMIC_RULES_PROMPT format string: {e}")
        return "ERROR: Prompt formatting failed."
    except Exception as e:
        logging.error(f"Error formatting DYNAMIC_RULES_PROMPT: {e}")
        return "ERROR: Could not format dynamic rules prompt."


# ==============================================================
# 3️⃣ FINAL REPORT PROMPT
# ==============================================================

FINAL_REPORT_PROMPT = """
You are an expert Data Validation Analyst. Your task is to consolidate all validation findings into a single, comprehensive JSON report, including severity levels, a summary block, and schema drift analysis.

You will be given:
1.  File Metadata
2.  Schema Analysis (vs DB)
3.  Type Mismatches (with severity added by you)
4.  Data Quality Violations (found by script)
5.  Current File Schema
6.  Historical Schemas (optional, may be empty)
7.  Dynamic Validation Rules (Pre-generated)

Your Job:
1.  **Consolidate**: Combine all inputs.
2.  **Analyze & Add Severity/Summary**:
    * Assign/confirm `"severity": "high" | "medium" | "low"` for each 'Type Mismatch' and 'Data Quality Violation'.
    * **Add Business Impact**: For each 'Data Quality Violation', add a new field called `"business_impact"`.
    * **Add Fix-it Logic**: For *each* issue, add `"suggested_fix_logic"` and `"root_cause_hypothesis"`.
    * **Generate Validation Summary**.
    * **Generate Data Quality Score**.
    * **Suggest Append/Upsert Strategy**.
    * **Perform Schema Drift Analysis**.
    * **Generate Narrative Summary**.

---
[INPUT DATA]
... (schemas, mismatches, rules, etc.) ...

**[NEW] Dynamic Validation Rules (Pre-generated):**
{dynamic_rules_json}

---
[YOUR ANALYSIS]

Produce a single JSON report in this exact format:
{{
  "file_name": "{file_name}",
  "total_rows_checked": {total_rows},
  "validated_at": "{validation_timestamp}",
  "validation_summary": {{
    "status": "[Passed | Passed with Warnings | Failed]",
    "high_severity_issues": <count>,
    "medium_severity_issues": <count>,
    "low_severity_issues": <count>
  }},
  "data_quality_score": {{
    "score": <0-100>,
    "grade": "[A | B | C | D | F]",
    "reasoning": "Explain reasoning"
  }},
  "triage_plan": [
    {{
      "priority": 1,
      "action": "Fix null OrderID values",
      "reasoning": "Top priority as it blocks processing"
    }}
  ],
  "data_type_mismatch": [],
  "data_quality_issues": [],
  "append_upsert_suggestion": {{}},
  "schema_drift": {{}},
  "dynamic_validation_rules": {dynamic_rules_json},
  "root_cause_analysis": {{}},
  "overall_analysis": {{}}
}}
"""

def get_final_report_prompt(
    file_metadata: Dict[str, Any],
    schema_analysis: Dict[str, Any],
    type_mismatches: List[Dict[str, Any]],
    dq_violations: List[Dict[str, Any]],
    current_file_schema: Dict[str, Any],
    historical_schemas: List[Dict[str, Any]],
    dynamic_rules: List[Dict[str, Any]]
) -> str:
    """Helper function to format the final report prompt including schema drift."""

    current_file_schema_cols = current_file_schema.get('columns', {})
    validation_ts = datetime.now(timezone.utc).isoformat()

    try:
        dq_violations_json_str = json.dumps(dq_violations, indent=2, default=str)
    except Exception as e:
        logging.warning(f"Could not serialize dq_violations: {e}")
        dq_violations_json_str = "[]"

    try:
        type_mismatches_json_str = json.dumps(type_mismatches, indent=2, default=str)
    except Exception as e:
        logging.warning(f"Could not serialize type_mismatches: {e}")
        type_mismatches_json_str = "[]"

    try:
        dynamic_rules_json_str = json.dumps(dynamic_rules, default=str)
    except Exception as e:
        logging.warning(f"Could not serialize dynamic_rules: {e}")
        dynamic_rules_json_str = "[]"

    try:
        return FINAL_REPORT_PROMPT.format(
            file_metadata_json=json.dumps(file_metadata, indent=2, default=str),
            schema_analysis_json=json.dumps(schema_analysis, indent=2, default=str),
            type_mismatches_json=type_mismatches_json_str,
            dq_violations_json=dq_violations_json_str,
            current_file_schema_json=json.dumps(current_file_schema_cols, indent=2, default=str),
            historical_schemas_json=json.dumps(historical_schemas, indent=2, default=str),
            file_name=file_metadata.get("file_name", "unknown_file"),
            total_rows=file_metadata.get("total_rows", 0),
            validation_timestamp=validation_ts,
            dynamic_rules_json=dynamic_rules_json_str
        )
    except KeyError as e:
        logging.error(f"Missing key in FINAL_REPORT_PROMPT: {e}")
        return "ERROR: Prompt formatting failed."
    except Exception as e:
        logging.error(f"Error formatting FINAL_REPORT_PROMPT: {e}")
        return "ERROR: Could not format final report prompt."
