import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
from io import BytesIO

# ------------------------
# Custom CSS Styling
# ------------------------
def inject_css():
    st.markdown("""
    <style>
        /* Main header styling */
        .main-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
        }
        
        .title-section h1 {
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            color: #7f8c8d;
            font-size: 1.1rem;
            margin-top: 0;
        }
        
        /* Colored headers */
        .colored-header {
            padding: 0.5rem 1rem;
            margin: 1.5rem 0 1rem 0;
            background-color: #f8f9fa;
            border-radius: 4px;
            border-left: 5px solid #4B8BBE;
        }
        
        .colored-header h2 {
            margin: 0;
            color: #2c3e50;
        }
        
        .colored-header p {
            margin: 0.25rem 0 0 0;
            color: #7f8c8d;
            font-size: 0.9rem;
        }
        
        /* Sidebar styling */
        .sidebar-header {
            padding: 0.5rem 0;
            margin-bottom: 1rem;
            border-bottom: 1px solid #eee;
        }
        
        .sidebar-header h2 {
            color: #2c3e50;
            margin: 0;
        }
        
        .sidebar-footer {
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
            font-size: 0.8rem;
            color: #7f8c8d;
        }
        
        /* Feature cards */
        .feature-card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }
        
        .feature-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .feature-icon {
            font-size: 2rem;
            margin-bottom: 1rem;
            color: #3498db;
        }
        
        .feature-card h3 {
            margin-top: 0;
            color: #2c3e50;
        }
        
        .feature-card p {
            color: #7f8c8d;
            margin-bottom: 0;
        }
        
        /* Button styling */
        .stButton>button {
            border-radius: 4px;
            padding: 0.5rem 1rem;
            transition: all 0.3s;
        }
        
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        /* File uploader styling */
        .stFileUploader>div>div>div>div {
            border: 2px dashed #3498db;
            border-radius: 8px;
            padding: 2rem;
            background-color: #f8f9fa;
        }
        
        /* Spinner styling */
        .stSpinner>div {
            margin: 0 auto;
        }
    </style>
    """, unsafe_allow_html=True)

# ------------------------
# App Configuration
# ------------------------
st.set_page_config(
    page_title="Tableau Migration Toolkit",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS at the start
inject_css()

# ------------------------
# Custom Components
# ------------------------
def colored_header(label, description=None, color=None):
    st.markdown(
        f"""
        <div class="colored-header" style="border-left: 5px solid {color or '#4B8BBE'};">
            <h2>{label}</h2>
            {f'<p>{description}</p>' if description else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

# ------------------------
# App Header
# ------------------------
def show_header():
    st.markdown("""
    <div class="main-header">
        <div class="title-section">
            <h1>Tableau Migration Toolkit</h1>
            <p class="subtitle">Streamline your Tableau content migration with powerful automation</p>
        </div>
        <div class="logo-section">
            <img src="https://www.tableau.com/sites/default/files/pages/tableau-logo.png" width="120">
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

# [Rest of your existing code continues here...]
# Include all your other functions and main logic exactly as they were

# ------------------------
# Run the App
# ------------------------
if __name__ == "__main__":
    main()
