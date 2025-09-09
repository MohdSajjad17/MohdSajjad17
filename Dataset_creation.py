import streamlit as st
import openai
import pandas as pd
import json
from openai import OpenAI
import io
import time
import random

# Set up the page
st.set_page_config(
    page_title="Synthetic Data Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
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
    .download-section {
        background-color: #e8f4f8;
        padding: 15px;
        border-radius: 10px;
        margin-top: 20px;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 10px 24px;
    }
    .stButton>button:hover {
        background-color: #45a049;
    }
    .progress-bar {
        margin-top: 20px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# App title and description
st.markdown('<h1 class="main-header">📊 Synthetic Data Generator</h1>', unsafe_allow_html=True)
st.markdown("""
<div class="info-box">
    <p>This app generates synthetic data using OpenAI's API. Enter your requirements in the prompt field, 
    specify the number of rows you need, and the AI will create customized synthetic data for you. 
    You can then download the data in CSV or Excel format.</p>
</div>
""", unsafe_allow_html=True)

# Initialize OpenAI client with the provided API key
client = OpenAI(api_key='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')

# Main input area
st.markdown("### 📝 Enter Your Data Requirements")
user_prompt = st.text_area(
    "Describe the data you want to generate:",
    height=100,
    placeholder="e.g., Generate synthetic sales data with fields for date, customer_id, product_id, quantity, and order total. Include some negative values for returns.",
    help="Be specific about the fields, formats, and any special requirements."
)

# Number of rows input
st.markdown("### 🔢 Number of Rows")
num_rows = st.number_input(
    "Enter the number of rows to generate:",
    min_value=1,
    max_value=10000,
    value=100,
    step=1,
    help="For large datasets (1000+ rows), generation may take longer."
)

# Format selection for download
st.markdown("### 📥 Download Format")
download_format = st.radio("Select download format:", ["CSV", "Excel"], horizontal=True)

# Generate button
generate_button = st.button("Generate Data", type="primary")

# Function to generate a template with structure
def generate_data_structure(prompt):
    """Generate a data structure template from the prompt"""
    structure_prompt = f"""
    Based on the following prompt: "{prompt}"
    
    Please respond with ONLY a JSON object that defines the structure of the data. 
    The JSON should have a "fields" key with an array of field names and their types.
    Example:
    {{
      "fields": [
        {{"name": "date", "type": "date"}},
        {{"name": "customer_id", "type": "string"}},
        {{"name": "order_total", "type": "number"}}
      ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": structure_prompt}],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    except:
        # Fallback structure if API call fails
        return {
            "fields": [
                {"name": "id", "type": "number"},
                {"name": "value", "type": "number"}
            ]
        }

# Function to generate sample data based on structure
def generate_sample_data(structure, num_samples=10):
    """Generate a small sample of data based on the structure"""
    sample_prompt = f"""
    Based on this data structure: {json.dumps(structure)}
    
    Generate {num_samples} sample records that match this structure.
    Return ONLY a JSON object with a "data" key containing an array of records.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": sample_prompt}],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return result.get("data", [])
    except:
        # Fallback data if API call fails
        return [{"id": i, "value": i * 10} for i in range(1, num_samples + 1)]

# Function to generate large dataset efficiently
def generate_large_dataset(structure, sample_data, num_rows):
    """Generate a large dataset by extrapolating from sample data"""
    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Use the sample data as a template
    for i in range(num_rows):
        if i < len(sample_data):
            # Use the actual sample data for first rows
            record = sample_data[i]
        else:
            # Create new records based on sample data patterns
            template_idx = i % len(sample_data)
            record = {}
            
            for field in structure["fields"]:
                field_name = field["name"]
                field_type = field.get("type", "string")
                
                if field_name in sample_data[template_idx]:
                    # Use the sample value as a base
                    base_value = sample_data[template_idx][field_name]
                    
                    if field_type == "number":
                        # Vary numeric values
                        if isinstance(base_value, (int, float)):
                            variation = random.uniform(-0.5, 0.5) * base_value
                            record[field_name] = base_value + variation
                        else:
                            record[field_name] = i
                    elif field_type == "date":
                        # Vary dates
                        record[field_name] = f"2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
                    else:
                        # Vary string values
                        record[field_name] = f"{base_value}_{i}"
                else:
                    # Create new field value
                    if field_type == "number":
                        record[field_name] = i
                    elif field_type == "date":
                        record[field_name] = f"2023-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
                    else:
                        record[field_name] = f"value_{i}"
        
        all_data.append(record)
        
        # Update progress every 100 rows
        if i % 100 == 0:
            progress = i / num_rows
            progress_bar.progress(progress)
            status_text.text(f"Generating row {i} of {num_rows}...")
    
    # Complete progress bar
    progress_bar.progress(1.0)
    status_text.text("Data generation complete!")
    
    return all_data

# Main content area
if generate_button:
    if not user_prompt:
        st.error("Please enter a prompt to generate data.")
    else:
        with st.spinner("Generating synthetic data... This may take a moment."):
            try:
                # Step 1: Generate data structure
                st.info("Step 1: Analyzing your data requirements...")
                structure = generate_data_structure(user_prompt)
                
                # Step 2: Generate sample data
                st.info("Step 2: Creating sample data pattern...")
                sample_size = min(50, num_rows)  # Generate up to 50 samples
                sample_data = generate_sample_data(structure, sample_size)
                
                # Step 3: Generate full dataset
                st.info(f"Step 3: Generating {num_rows} rows of data...")
                data = generate_large_dataset(structure, sample_data, num_rows)
                
                # Convert to DataFrame
                df = pd.DataFrame(data)
                
                # Display success message
                st.success(f"Data generated successfully! Created {len(df)} rows.")
                
                # Display the data
                st.markdown('### 📋 Generated Data Preview')
                
                # For large datasets, show a sample instead of the full dataset
                if len(df) > 100:
                    st.info(f"Showing first 100 rows of {len(df)} total rows. Use the download button to get the full dataset.")
                    st.dataframe(df.head(100))
                else:
                    st.dataframe(df)
                
                # Display data info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", len(df))
                with col2:
                    st.metric("Total Columns", len(df.columns))
                with col3:
                    numeric_cols = df.select_dtypes(include=['number']).columns
                    if len(numeric_cols) > 0:
                        st.metric("Sample Value", f"{df[numeric_cols[0]].iloc[0]:.2f}")
                
                # Download section
                st.markdown('<div class="download-section">', unsafe_allow_html=True)
                st.markdown('### 💾 Download Data')
                
                if download_format == "CSV":
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="synthetic_data.csv",
                        mime="text/csv",
                        key="csv_download"
                    )
                else:
                    # For Excel download
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Synthetic Data')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="Download Excel",
                        data=excel_data,
                        file_name="synthetic_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="excel_download"
                    )
                st.markdown('</div>', unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.info("Please try again with a more specific prompt.")

# Add some examples and instructions
with st.expander("💡 How to get the best results"):
    st.markdown("""
    ### Tips for effective prompts:
    
    1. **Be specific** about the data fields you want (e.g., "Include customer_id, name, email, and purchase_history")
    2. **Specify the format** (e.g., "Dates should be in YYYY-MM-DD format")
    3. **Mention any constraints** (e.g., "Ages should be between 18 and 65", "Include some negative values for returns")
    4. **Define the scope** (e.g., "Generate data for the last 6 months")
    
    ### Example prompts:
    - "Generate synthetic e-commerce data with fields for order_id, customer_id, product_id, quantity, price, and order_date. Include some returns (negative values)."
    - "Create synthetic user data with id, name, email, age, country, and subscription_date."
    - "Generate website analytics data with date, visitors, page_views, bounce_rate, and conversion_rate."
    """)

# Footer
st.markdown("---")
st.markdown("### 🔒 Privacy Note")
st.markdown("Your API key is embedded in the code and not shared with anyone. The generated data is synthetic and doesn't contain real user information.")
