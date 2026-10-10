import os
from dotenv import load_dotenv

import streamlit as st
from src.material_intelligence.api.chat import llm_response


load_dotenv()
st.title("Material Intelligence")

# Initialize chat history in session state if it doesn't exist
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sidebar for file uploads
with st.sidebar:
    st.header("Attachments")
    uploaded_files = st.file_uploader(
        "Upload file/files to your prompt",
        accept_multiple_files=True,
        type=["png", "jpg", "jpeg", "pdf", "txt", "xlsx", ".docx", "csv"]
    )

    if uploaded_files:
        st.write(f"Attached ({len(uploaded_files)}):")
        for file in uploaded_files:
            st.caption(f"- {file.name}")

# Display prior chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input via the chat input box
if prompt := st.chat_input("Type your message here..."):
    # Build context if files were uploaded
    file_info = ""
    if uploaded_files:
        file_names = ", ".join([f.name for f in uploaded_files])
        file_info = f"\n\n*(Attached files: {file_names})*"

    full_user_message = prompt + file_info

    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(full_user_message)

    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": full_user_message})

    # Simulate assistant response (replace this with your LLM call)
    response = llm_response(prompt, os.getenv("GEMINI_API_KEY"))
    if uploaded_files:
        response += f" along with {len(uploaded_files)} file(s)."

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(response)

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response})