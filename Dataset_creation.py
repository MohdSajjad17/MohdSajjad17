import streamlit as st
import openai
import pandas as pd
import json
import io

from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key="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")  # 🔐 Replace with your key

# Streamlit page config
st.set_page_config(
    page_title="Synthetic Data Generator",
    page_icon="📊",
    layout="wide",
)

# CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# App title and description
st.markdown('<h1 class="main-header">📊 Synthetic Data Generator</h1>', unsafe_allow_html=True)
st.markdown("""
<div class="info-box">
    <p>Generate custom synthetic datasets using OpenAI's API. Enter a prompt describing the data,
    specify how many rows you need, and download your dataset in CSV or Excel format.</p>
</div>
""", unsafe_allow_html=True)

# User inputs
user_prompt = st.text_area(
    "📝 Describe the data you want to generate:",
    height=100,
    placeholder="e.g., Generate synthetic football player data with fields: date, player name, age, nationality, club, matches played, goals scored, assists.",
)

num_rows = st.number_input("🔢 Number of rows to generate:", min_value=1, max_value=1000, value=100)

download_format = st.radio("📁 Select download format:", ["CSV", "Excel"], horizontal=True)

generate_button = st.button("🚀 Generate Data")

# --------------------------
# Core function to call OpenAI
# --------------------------

def generate_data_directly(prompt, num_rows):
    """Generates data directly from OpenAI API based on the prompt."""
    generation_prompt = f"""
    Based on the following description:

    "{prompt}"

    Generate exactly {num_rows} synthetic records as a JSON object. 
    The output must include a "data" key whose value is a list of JSON objects. 
    Each record should match the fields described and follow consistent data formatting.

    Return only a valid JSON object.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": generation_prompt}],
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        return result.get("data", [])
    except Exception as e:
        st.error(f"❌ Error generating data: {str(e)}")
        return []

# --------------------------
# Main logic
# --------------------------

if generate_button:
    if not user_prompt.strip():
        st.warning("Please enter a prompt before generating data.")
    else:
        with st.spinner("Generating synthetic data... Please wait."):
            records = generate_data_directly(user_prompt, num_rows)
            if records:
                df = pd.DataFrame(records)

                st.success(f"✅ Generated {len(df)} rows of data.")
                st.markdown("### 📋 Data Preview")
                st.dataframe(df.head(100))

                # Download buttons
                st.markdown("### 💾 Download Your Data")
                if download_format == "CSV":
                    csv = df.to_csv(index=False)
                    st.download_button("Download CSV", csv, "synthetic_data.csv", "text/csv")
                else:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name="Synthetic Data")
                    st.download_button("Download Excel", output.getvalue(), "synthetic_data.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
