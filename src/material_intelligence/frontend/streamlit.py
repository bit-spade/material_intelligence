import os
import streamlit as st
from dotenv import load_dotenv

from material_intelligence.frontend.ui_common import apply_theme

load_dotenv()

st.set_page_config(
    page_title="Material Intelligence · ECO-SCORE",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

# Define navigation pages using modern st.Page & st.navigation
single_page = st.Page(
    "views/single_assessment.py",
    title="Single Assessment",
    icon="🌿",
    default=True,
)

comparison_page = st.Page(
    "views/comparison.py",
    title="Product Comparison",
    icon="⚖️",
)

advisor_page = st.Page(
    "views/recommendation.py",
    title="Material Advisor",
    icon="💡",
)

nav = st.navigation(
    {
        "Evaluation": [single_page, comparison_page],
        "Intelligence": [advisor_page],
    }
)

nav.run()
