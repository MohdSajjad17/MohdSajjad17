import streamlit as st
import openai
import pandas as pd
import json
from openai import OpenAI
import io
import time

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
    .sub-header {
        font-size: 1.5rem;
        color: #ff7f0e;
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

# Sidebar for user input
with st.sidebar:
    st.markdown('<h2 class="sub-header">⚙️ Configuration</h2>', unsafe_allow_html=True)
    
    # Example prompts for user selection
    example_prompts = {
        "E-commerce Sales": "Generate synthetic sales data for an e-commerce platform. Include fields for date, customer_id (Customer ###), product_id, product_name, quantity, order total (in $USD). For certain orders, the order total should be negative to represent returns.",
        "User Demographics": "Generate synthetic user demographic data. Include fields for user_id, age, gender, location, income_level, education, and signup_date.",
        "Website Analytics": "Generate synthetic website analytics data. Include fields for date, page_views, unique_visitors, bounce_rate, avg_session_duration, and conversions.",
        "Custom": "Enter your own custom prompt below"
    }
    
    selected_prompt = st.selectbox(
        "Select a prompt type:",
        options=list(example_prompts.keys())
    )
    
    # Text area for prompt input
    if selected_prompt == "Custom":
        user_prompt = st.text_area(
            "Enter your custom prompt:",
            height=150,
            help="Be specific about the data you want to generate. Include fields, formats, and any special requirements."
        )
    else:
        user_prompt = st.text_area(
            "Edit the prompt if needed:",
            value=example_prompts[selected_prompt],
            height=150,
            help="Be specific about the data you want to generate. Include fields, formats, and any special requirements."
        )
    
    # Number of rows input
    st.markdown("### Number of Rows")
    num_rows = st.number_input(
        "Enter the number of rows to generate:",
        min_value=1,
        max_value=5000,
        value=10,
        step=1,
        help="For large datasets (1000+ rows), generation may take longer."
    )
    
    # Batch size for large datasets
    if num_rows > 100:
        batch_size = st.slider(
            "Batch size for generation:",
            min_value=50,
            max_value=500,
            value=min(200, num_rows),
            step=50,
            help="For large datasets, generating in batches can be more reliable."
        )
    else:
        batch_size = num_rows
    
    # Format selection for download
    st.markdown("### Download Format")
    download_format = st.radio("Select download format:", ["CSV", "Excel"], horizontal=True)
    
    # Generate button
    generate_button = st.button("Generate Data", type="primary")

# Function to generate data in batches
def generate_data_in_batches(prompt, total_rows, batch_size):
    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Calculate number of batches
    num_batches = (total_rows + batch_size - 1) // batch_size
    
    for batch in range(num_batches):
        # Calculate rows for this batch
        rows_in_batch = min(batch_size, total_rows - batch * batch_size)
        
        # Update progress
        progress = (batch * batch_size) / total_rows
        progress_bar.progress(progress)
        status_text.text(f"Generating batch {batch+1} of {num_batches} ({rows_in_batch} rows)...")
        
        # Create batch prompt
        batch_prompt = f"{prompt} Generate data for {rows_in_batch} records. Output in JSON form."
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": batch_prompt}],
                response_format={"type": "json_object"}
            )
            
            # Parse the response
            generated_data = json.loads(response.choices[0].message.content)
            
            # Find the data key (OpenAI might return different structures)
            data_key = None
            for key in generated_data.keys():
                if isinstance(generated_data[key], list):
                    data_key = key
                    break
            
            if data_key:
                batch_data = generated_data[data_key]
            else:
                # If no obvious key found, use the first list we find
                for value in generated_data.values():
                    if isinstance(value, list):
                        batch_data = value
                        break
                else:
                    # If no list found, use the entire response as a single record
                    batch_data = [generated_data]
            
            # Add to all data
            all_data.extend(batch_data)
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            st.error(f"Error generating batch {batch+1}: {str(e)}")
            break
    
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
                # For large datasets, generate in batches
                if num_rows > 100:
                    data = generate_data_in_batches(user_prompt, num_rows, batch_size)
                else:
                    # For smaller datasets, generate in one go
                    final_prompt = f"{user_prompt} Generate data for {num_rows} records. Output in JSON form."
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": final_prompt}],
                        response_format={"type": "json_object"}
                    )
                    
                    # Parse the response
                    generated_data = json.loads(response.choices[0].message.content)
                    
                    # Find the data key (OpenAI might return different structures)
                    data_key = None
                    for key in generated_data.keys():
                        if isinstance(generated_data[key], list):
                            data_key = key
                            break
                    
                    if data_key:
                        data = generated_data[data_key]
                    else:
                        # If no obvious key found, use the first list we find
                        for value in generated_data.values():
                            if isinstance(value, list):
                                data = value
                                break
                        else:
                            # If no list found, use the entire response as a single record
                            data = [generated_data]
                
                # Convert to DataFrame
                df = pd.DataFrame(data)
                
                # If we got more rows than requested, trim the dataset
                if len(df) > num_rows:
                    df = df.head(num_rows)
                
                # Display success message
                st.success(f"Data generated successfully! Created {len(df)} rows.")
                
                # Display the data
                st.markdown('<h2 class="sub-header">📋 Generated Data</h2>', unsafe_allow_html=True)
                
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
                st.markdown('<h3 class="sub-header">💾 Download Data</h3>', unsafe_allow_html=True)
                
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
    2. **Specify the format** (e.g., "Output in JSON with 'users' as the main key")
    3. **Mention any constraints** (e.g., "Ages should be between 18 and 65", "Include some negative values for returns")
    4. **Define the scope** (e.g., "Generate data for the last 6 months")
    5. **Include examples** if you have specific formatting needs
    
    ### For large datasets (1000+ rows):
    - The app will generate data in batches to improve reliability
    - You can adjust the batch size in the sidebar
    - Generation may take several minutes for very large datasets
    
    ### Example prompts:
    - "Generate synthetic e-commerce data with fields for order_id, customer_id, product_id, quantity, price, and order_date. Include some returns (negative values)."
    - "Create synthetic user data with id, name, email, age, country, and subscription_date for users from various countries."
    - "Generate website analytics data with date, visitors, page_views, bounce_rate, and conversion_rate for a period."
    """)

# Footer
st.markdown("---")
st.markdown("### 🔒 Privacy Note")
st.markdown("Your API key is embedded in the code and not shared with anyone. The generated data is synthetic and doesn't contain real user information.")

# Instructions for running the app
with st.expander("ℹ️ How to run this app"):
    st.markdown("""
    This app is built with Streamlit and uses the OpenAI API to generate synthetic data.
    
    To run this app locally:
    1. Save this code to a Python file (e.g., `synthetic_data_app.py`)
    2. Install required packages: `pip install streamlit openai pandas openpyxl`
    3. Run the app: `streamlit run synthetic_data_app.py`
    
    The app will open in your default web browser.
    """)
