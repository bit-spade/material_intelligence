import os
import textwrap
from dotenv import load_dotenv
import streamlit as st

from material_intelligence.api.chat import ask_llm
from material_intelligence.api.utils import load_questionnaire
from material_intelligence.engine.calculator import (
    calculate_score_and_level,
    get_product_config,
)

load_dotenv()

st.set_page_config(
    page_title="Material Intelligence - ECO-SCORE Assessment",
    page_icon="🌿",
    layout="wide",
)

st.title("🌿 Material Intelligence")
st.caption("ECO-SCORE questionnaire-based product sustainability assessment")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_level" not in st.session_state:
    st.session_state.current_level = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None
if "current_max_score" not in st.session_state:
    st.session_state.current_max_score = None
if "current_percentage" not in st.session_state:
    st.session_state.current_percentage = None
if "current_category" not in st.session_state:
    st.session_state.current_category = None

# Sustainability levels configuration (High, Medium, Low)
SUSTAINABILITY_LEVELS = [
    ("High", "#008037", 160, "≥ 75%"),
    ("Medium", "#F7A600", 125, "40% - 74%"),
    ("Low", "#E30613", 90, "< 40%"),
]

CATEGORY_MAP = {
    "Textile product": "Textile_product",
    "Acoustic product": "Acoustic_product",
    "Lighting product": "Lighting_product",
}


def render_sustainability_scale(
    selected_level: str | None,
    points: int | None = None,
    max_points: int | None = None,
    percentage: float | None = None,
):
    """Renders the 3-tier sustainability level scale (High, Medium, Low)."""
    selected = selected_level.strip().capitalize() if selected_level else None

    bars_html = []
    for level, color, width, range_label in SUSTAINABILITY_LEVELS:
        is_active = (level == selected)
        active_class = "level-bar-active" if is_active else "level-bar-inactive"
        pointer = f'<span class="level-pointer">◀ <b>{level}</b> ({range_label})</span>' if is_active else f'<span class="level-hint">({range_label})</span>'

        bars_html.append(
            f'<div class="level-bar-row">'
            f'<div class="level-bar {active_class}" style="background-color: {color}; width: {width}px; color: #FFFFFF;">'
            f'<span>{level}</span>'
            f'</div>'
            f'{pointer}'
            f'</div>'
        )

    if selected:
        score_text = ""
        if points is not None and max_points is not None and percentage is not None:
            score_text = f" &mdash; <b>{points}/{max_points}</b> pts ({percentage:.1f}%)"
        score_badge = f'<div class="level-current-badge">Level: <b style="color: {"#008037" if selected == "High" else "#D97706" if selected == "Medium" else "#DC2626"};">{selected}</b>{score_text}</div>'
    else:
        score_badge = '<div class="level-current-badge" style="color: #666;">No assessment yet</div>'

    html_content = textwrap.dedent(f"""
    <style>
    .level-container {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        padding: 14px;
        background: #ffffff;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        color: #222222;
        margin-bottom: 12px;
    }}
    .level-bar-row {{
        display: flex;
        align-items: center;
        margin: 6px 0;
        height: 26px;
    }}
    .level-bar {{
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
    .level-bar-inactive {{
        opacity: 0.35;
    }}
    .level-bar-active {{
        opacity: 1.0;
        transform: scale(1.03);
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }}
    .level-pointer {{
        margin-left: 10px;
        font-size: 12px;
        color: #111;
        font-weight: 600;
    }}
    .level-hint {{
        margin-left: 10px;
        font-size: 11px;
        color: #888;
    }}
    .level-current-badge {{
        font-size: 14px;
        margin-bottom: 10px;
        font-weight: 600;
    }}
    </style>
    <div class="level-container">
        {score_badge}
        {''.join(bars_html)}
    </div>
    """).strip()

    st.markdown(html_content, unsafe_allow_html=True)


# Sidebar controls
with st.sidebar:
    st.header("Product Configuration")

    category_label = st.selectbox(
        "Select Product Category",
        options=list(CATEGORY_MAP.keys()),
        index=0,
    )
    selected_category = CATEGORY_MAP[category_label]

    st.header("Sustainability Level")
    render_sustainability_scale(
        st.session_state.current_level,
        st.session_state.current_score,
        st.session_state.current_max_score,
        st.session_state.current_percentage,
    )

    with st.expander("📊 Benchmark References", expanded=False):
        st.markdown("""
        **Reference levels:**
        - **Textile:**
          - *SIDDE LIV sofa*: 84% (430/510) &rarr; **High**
          - *IKEA MAJGULL curtain*: 65% (330/510) &rarr; **Medium**
        - **Acoustic:**
          - *Ecophon Fade One Smooth*: 89% (550/620) &rarr; **High**
          - *Addictive Sound panels*: 47% (290/620) &rarr; **Medium**
        - **Lighting:**
          - *Disano 1774 Amalfi*: 70% (455/650) &rarr; **Medium**
          - *300 W LED street light*: 9.23% (60/650) &rarr; **Low**
        """)

    st.header("Product Documentation")
    uploaded_files = st.file_uploader(
        "Upload documentation (datasheets, certificates, EPD, images)",
        accept_multiple_files=True,
        type=["pdf", "png", "jpg", "jpeg", "txt", "csv"],
    )

    if uploaded_files:
        st.caption(f"Attached files ({len(uploaded_files)}):")
        for f in uploaded_files:
            st.caption(f"• `{f.name}`")

    st.divider()
    if st.button("Reset Assessment & History"):
        st.session_state.messages = []
        st.session_state.current_level = None
        st.session_state.current_score = None
        st.session_state.current_max_score = None
        st.session_state.current_percentage = None
        st.session_state.current_category = None
        st.rerun()

# Display prior chat messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input via chat input box
if prompt := st.chat_input("Enter product name or extra notes to assess..."):
    if not os.getenv("GEMINI_API_KEY"):
        st.error("Please ensure `GEMINI_API_KEY` is set in your environment or `.env` file.")
        st.stop()

    user_message = prompt
    if uploaded_files:
        user_message += f"\n\n*(Attached {len(uploaded_files)} document(s): {', '.join(f.name for f in uploaded_files)})*"

    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(user_message)

    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": user_message})

    # Call LLM assessment
    with st.spinner(f"Assessing {category_label} using ECO-SCORE questionnaire..."):
        try:
            answers = ask_llm(
                category=selected_category,
                files=uploaded_files if uploaded_files else [],
                extra_notes=prompt,
            )

            # Calculate score and level
            score_data = calculate_score_and_level(selected_category, answers)
            questionnaire = load_questionnaire(selected_category)
            product_config = get_product_config(selected_category)

            # Update session state
            st.session_state.current_level = score_data["level"]
            st.session_state.current_score = score_data["points"]
            st.session_state.current_max_score = score_data["max_points"]
            st.session_state.current_percentage = score_data["percentage"]
            st.session_state.current_category = selected_category

            # Count answer types
            supported_count = sum(1 for a in answers if a is True)
            contradicted_count = sum(1 for a in answers if a is False)
            unknown_count = sum(1 for a in answers if a is None)

            # Build detailed question-by-question breakdown
            breakdown_lines = []
            breakdown_lines.append("| ID | Criteria Question | Answer | Points |")
            breakdown_lines.append("|---|---|---|---|")

            for q, criterion, ans in zip(
                questionnaire["questions"], product_config.criteria, answers
            ):
                if ans is True:
                    ans_badge = "✅ Supported"
                    pts_badge = f"+{criterion.points}"
                elif ans is False:
                    ans_badge = "❌ Contradicted"
                    pts_badge = "0"
                else:
                    ans_badge = "⚪ Unknown / NA"
                    pts_badge = "0"

                q_text = q.get("text", "").replace("|", "-")
                breakdown_lines.append(
                    f"| `{q.get('id', '')}` | {q_text} | {ans_badge} | **{pts_badge}** |"
                )

            breakdown_table = "\n".join(breakdown_lines)

            # Level badge color
            level_color = (
                "green" if score_data["level"] == "High"
                else "orange" if score_data["level"] == "Medium"
                else "red"
            )

            assistant_msg = (
                f"### Assessment Result for **{prompt}**\n\n"
                f"- **Category:** `{category_label}`\n"
                f"- **Sustainability Level:** :{level_color}[**{score_data['level']}**]\n"
                f"- **Score:** **{score_data['points']} / {score_data['max_points']}** points "
                f"(`{score_data['percentage']}%`)\n"
                f"- **Summary:** `{supported_count}` supported, `{contradicted_count}` contradicted, "
                f"`{unknown_count}` unknown\n\n"
                f"<details>\n<summary><b>Click to view detailed questionnaire breakdown ({len(answers)} questions)</b></summary>\n\n"
                f"{breakdown_table}\n\n"
                f"</details>"
            )

        except Exception as e:
            assistant_msg = f"⚠️ **Error during assessment:** {str(e)}"

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        st.markdown(assistant_msg, unsafe_allow_html=True)

    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": assistant_msg})

    # Rerun so sidebar immediately reflects updated level
    st.rerun()