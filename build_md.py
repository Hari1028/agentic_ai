import json
 
def create_validation_markdown(data: dict) -> str:
    md_parts = []
 
    def format_list(items_list, empty_msg="None"):
        if not items_list:
            return f"- {empty_msg}"
        return "\n".join(f"- `{item}`" for item in items_list)
 
    # --- Title ---
    file_name = data.get('User_file_name', 'N/A')
    md_parts.append(f"# Data Validation Report for `{file_name}`")
 
    # --- Summary ---
    summary = data.get('validation_summary', {})
    status = summary.get('status', 'N/A')
    md_parts.append(f"\n## Validation Status: **{status}**")
 
    overall_analysis = data.get('overall_analysis', 'N/A')
    md_parts.append(f"\n**Overall Analysis:** {overall_analysis}")
 
    # --- Glance Table ---
    md_parts.append("\n### At a Glance")
    md_parts.append("| Metric | Value |")
    md_parts.append("| :--- | :--- |")
    md_parts.append(f"| Inferred Table | `{data.get('inferred_target_table', 'N/A')}` |")
    md_parts.append(f"| High Severity Issues | {summary.get('high_severity_issues', 0)} |")
    md_parts.append(f"| Medium Severity Issues | {summary.get('medium_severity_issues', 0)} |")
    md_parts.append(f"| Low Severity Issues | {summary.get('low_severity_issues', 0)} |")
    md_parts.append(f"| Total Rows Checked | {data.get('total_rows_checked', 'N/A')} |")
    md_parts.append(f"| Processed At | {data.get('Processed_at', 'N/A')} |")
 
    # --- Schema Mismatch ---
    md_parts.append("\n## 1. Schema Mismatch Analysis")
    schema = data.get('schema_mismatch', {})
 
    if schema:
        md_parts.append(f"**Context:** {schema.get('analysis', {}).get('context', 'N/A')}")
 
        md_parts.append("\n#### Columns Missing From File:")
        md_parts.append(format_list(schema.get('columns_missing_from_file'), "None"))
 
        md_parts.append("\n#### Extra Columns Found in File:")
        md_parts.append(format_list(schema.get('columns_extra_in_file'), "None"))
 
        md_parts.append("\n#### Suggested Naming Mappings:")
        mappings = schema.get('naming_mismatches', {})
        if mappings:
            for file_col, db_col in mappings.items():
                md_parts.append(f"- Map `{file_col}` → `{db_col}`")
        else:
            md_parts.append("- None")
 
        md_parts.append("\n#### Recommendations:")
        md_parts.append(format_list(schema.get('analysis', {}).get('recommendation', []), "No recommendations."))
 
    else:
        md_parts.append("No schema mismatch data.")
 
    # --- Data Type Mismatch ---
    md_parts.append("\n## 2. Data Type Violations")
    type_mismatches = data.get('data_type_mismatch', [])
 
    if type_mismatches:
        for issue in type_mismatches:
            md_parts.append(f"\n- **Column:** `{issue.get('column')}`")
            md_parts.append(f"  - **Expected Type:** `{issue.get('expected_type')}`")
            md_parts.append(f"  - **Found Type:** `{issue.get('actual_type')}`")
            md_parts.append(f"  - **Severity:** {issue.get('severity', 'N/A').title()}")
            md_parts.append(f"  - **Suggested Fix Logic:** {issue.get('suggested_fix_logic', 'N/A')}")
    else:
        md_parts.append("No data type mismatches found.")
 
    # --- Data Quality Issues ---
    md_parts.append("\n## 3. Data Quality Violations")
    dq_issues = data.get('data_quality_issues', [])
 
    if dq_issues:
        for issue in dq_issues:
            md_parts.append(f"\n- **Column:** `{issue.get('column')}`")
            md_parts.append(f"  - **Issue:** {issue.get('issue')}")
            md_parts.append(f"  - **Severity:** {issue.get('severity').title()}")
            md_parts.append(f"  - **Business Impact:** {issue.get('business_impact')}")
            md_parts.append(f"  - **Suggested Fix:** {issue.get('suggested_fix_logic')}")
    else:
        md_parts.append("No data quality issues found.")
 
    # --- Schema Drift (Option 2: Comparison Table) ---
    md_parts.append("\n## 4. Schema Drift")
    drift = data.get('schema_drift', {})
 
    if drift and drift.get('differences'):
        md_parts.append("\n| Column | Expected Type | Current Type |")
        md_parts.append("| :--- | :--- | :--- |")
        for diff in drift.get('differences', []):
            md_parts.append(f"| `{diff.get('column')}` | `{diff.get('expected_type')}` | `{diff.get('current_type')}` |")
        md_parts.append(f"\n**Analysis:** {drift.get('analysis', 'N/A')}")
    else:
        md_parts.append("No schema drift detected.")
 
    # --- Load Strategy ---
    md_parts.append("\n## 5. Suggested Load Strategy")
    strategy = data.get('append_upsert_suggestion', {})
    if strategy:
        md_parts.append(f"- **Strategy:** `{strategy.get('strategy')}`")
        md_parts.append(f"- **Details:** {strategy.get('details', 'N/A')}")
    else:
        md_parts.append("No load strategy suggestion found.")
 
    # --- Dynamic Rules ---
    md_parts.append("\n## 6. Inferred Validation Rules")
    rules = data.get('dynamic_validation_rules', [])
 
    if rules:
        md_parts.append("| Column | Rule Type | Details | Inferred From |")
        md_parts.append("| :--- | :--- | :--- | :--- |")
        for rule in rules:
            md_parts.append(f"| `{rule.get('column')}` | `{rule.get('rule_type')}` | {rule.get('rule_details')} | `{rule.get('inferred_from_samples', [])}` |")
    else:
        md_parts.append("No dynamic rules inferred.")
 
    return "\n".join(md_parts)
