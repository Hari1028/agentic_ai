import streamlit as st
import tempfile
import os
import json # Added to parse JSON strings

# Import the functions from your project
# We use mock functions here for demonstration
from main import run_multi_sheet_validation
from build_md import create_validation_markdown

# --- Page Configuration ---
st.set_page_config(page_title="SchemaValidator", layout="wide")
st.title("🤖 SchemaValidator UI")
st.markdown("Upload an Excel file, enter a table name, and get a validation report.")

# --- Chat History Management ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Welcome! Please upload your Excel file and enter the table name you'd like to validate."}]

# Display chat messages from history
chat_container = st.container(height=500, border=False)
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"], unsafe_allow_html=True)


# --- User Input Area (Fixed at bottom) ---
# This CSS makes the input_container stick to the bottom
st.markdown("""
<style>
.st-emotion-cache-16txtl3 {
    position: fixed;
    bottom: 0;
    width: 100%;
    background: white;
    padding: 1rem 0;
    z-index: 100;
}
</style>
""", unsafe_allow_html=True)

input_container = st.container()
with input_container:
    col1, col2, col3 = st.columns([3, 8, 1])  # Adjust column ratios as needed

    with col1:
        uploaded_file = st.file_uploader(
            "Upload Excel File",
            type=['xlsx', 'xls','csv'],
            label_visibility="collapsed"
        )
        # Store uploaded file in session state immediately
        if uploaded_file:
            st.session_state.uploaded_file = uploaded_file

    with col2:
        prompt = st.text_input(
            "Enter table name to validate",
            placeholder="Enter table name...",
            label_visibility="collapsed",
            key="prompt_input"
        )

    with col3:
        send_button = st.button("➤", help="Send")

# --- Logic to handle submission ---
if send_button and prompt:
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Check for file
    file_to_process = st.session_state.get('uploaded_file')

    if not file_to_process:
        st.session_state.messages.append({"role": "assistant", "content": "Please upload an Excel file first."})
    else:
        # Process the file
        with st.spinner(f"Validating table `{prompt}`..."):
            temp_file_path = ""
            try:
                # 1. Save the uploaded file to a temporary path
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_to_process.name) as tmp:
                    tmp.write(file_to_process.getvalue())
                    temp_file_path = tmp.name

                # 2. Call your validation function
                validation_output = run_multi_sheet_validation(
                    file_path=temp_file_path,
                    user_provided_table_name=prompt
                )

                # 2a. Parse the output if it's a string (to fix the error)
                validation_data = {}
                if isinstance(validation_output, str):
                    try:
                        validation_data = json.loads(validation_output)
                    except json.JSONDecodeError:
                        st.session_state.messages.append({"role": "assistant", "content": "Error: The validation function returned an invalid JSON string."})
                        st.rerun() # Stop processing
                elif isinstance(validation_output, dict):
                    validation_data = validation_output
                else:
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: The validation function returned an unexpected data type: {type(validation_output)}"})
                    st.rerun() # Stop processing


                # 3. Call your markdown creation function
                md_report = create_validation_markdown(validation_data)

                # 4. Add report to chat
                st.session_state.messages.append({"role": "assistant", "content": md_report})

            except Exception as e:
                st.session_state.messages.append({"role": "assistant", "content": f"An error occurred: {e}"})
            finally:
                # 5. Clean up the temporary file
                if temp_file_path and os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

    # Clear the text input by rerunning
    st.rerun()

elif send_button and not prompt:
    st.toast("Please enter a table name.")

