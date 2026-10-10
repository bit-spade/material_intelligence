import os
from dotenv import load_dotenv

import streamlit as st
import textwrap

from src.material_intelligence.api.chat import llm_response


load_dotenv()
st.title("Material Intelligence")

# Initialize session state for current rating and chat messages
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_level" not in st.session_state:
    st.session_state.current_level = None
if "current_index" not in st.session_state:
    st.session_state.current_index = None

EU_GRADES = [
    ("A", "#008037", 85),
    ("B", "#54B848", 100),
    ("C", "#BED630", 115),
    ("D", "#FFF200", 130),
    ("E", "#F7A600", 145),
    ("F", "#EE6A1A", 160),
    ("G", "#E30613", 175),
]


def render_eu_scale(selected_grade: str | None, green_index: int | None = None):
    """Renders an EU appliance-style energy rating scale (A to G)."""
    selected = selected_grade.strip().upper() if selected_grade else None

    bars_html = []
    for grade, color, width in EU_GRADES:
        is_active = (grade == selected)
        active_class = "eu-bar-active" if is_active else "eu-bar-inactive"
        pointer = f'<span class="eu-pointer">◀ <b>{grade}</b></span>' if is_active else ""
        text_color = "#000000" if grade == "D" else "#FFFFFF"

        bars_html.append(
            f'<div class="eu-bar-row">'
            f'<div class="eu-bar {active_class}" style="background-color: {color}; width: {width}px; color: {text_color};">'
            f'<span>{grade}</span>'
            f'</div>'
            f'{pointer}'
            f'</div>'
        )

    score_badge = ""
    if selected:
        idx_text = f" (Index: {green_index}/10)" if green_index is not None else ""
        score_badge = f'<div class="eu-current-badge">Rating: <b>{selected}</b>{idx_text}</div>'
    else:
        score_badge = '<div class="eu-current-badge" style="color: #666;">No assessment yet</div>'

    html_content = textwrap.dedent(f"""
    <style>
    .eu-container {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        padding: 12px;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        color: #222222;
    }}
    .eu-bar-row {{
        display: flex;
        align-items: center;
        margin: 4px 0;
        height: 24px;
    }}
    .eu-bar {{
        display: flex;
        align-items: center;
        padding-left: 10px;
        font-weight: 700;
        font-size: 13px;
        height: 100%;
        clip-path: polygon(0% 0%, calc(100% - 10px) 0%, 100% 50%, calc(100% - 10px) 100%, 0% 100%);
        box-sizing: border-box;
        transition: transform 0.2s, opacity 0.2s;
    }}
    .eu-bar-inactive {{
        opacity: 0.35;
    }}
    .eu-bar-active {{
        opacity: 1.0;
        transform: scale(1.03);
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
    .eu-pointer {{
        margin-left: 8px;
        font-size: 13px;
        color: #111;
        font-weight: 600;
    }}
    .eu-current-badge {{
        font-size: 14px;
        margin-bottom: 8px;
        font-weight: 600;
    }}
    </style>
    <div class="eu-container">
        {score_badge}
        {''.join(bars_html)}
    </div>
    """).strip()

    st.markdown(html_content, unsafe_allow_html=True)


# Sidebar for scale & file uploads
with st.sidebar:
    st.header("Green Assessment")
    render_eu_scale(st.session_state.current_level, st.session_state.current_index)

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

    # Call LLM assessment
    green_index, green_level, incorrect_input, suggestion = llm_response(prompt, os.getenv("GEMINI_API_KEY"))

    if incorrect_input:
        assistant_msg = f"{suggestion}"
        st.session_state.current_level = None
        st.session_state.current_index = None
    else:
        # Update session state with the new rating
        st.session_state.current_level = green_level
        st.session_state.current_index = green_index

        # Chat feedback message
        assistant_msg = f"Assessed material: **{prompt}**\n\n- **Green Level:** `{green_level}`\n- **Green Index:** `{green_index}/10`"
        if uploaded_files:
            assistant_msg += f"\n\n*(Files considered: {len(uploaded_files)})*"

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(assistant_msg)

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": assistant_msg})

    # Rerun so sidebar immediately reflects the updated state
    st.rerun()