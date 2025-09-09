import streamlit as st
import openai
import pandas as pd
import json
from openai import OpenAI
import io

# Set up the Streamlit app
st.set_page_config(page_title="Synthetic Data Generator", page_icon="📊", layout="wide")

# Title and description
st.title("📊 Synthetic E-commerce Data Generator")
st.markdown("Generate synthetic sales data using OpenAI's GPT model. Customize your prompt and download the data in CSV or Excel format.")

# Initialize OpenAI client
@st.cache_resource
def get_openai_client():
    # Use Streamlit secrets for API key (safer than hardcoding)
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        api_key = st.text_input("Enter your OpenAI API key:", type="password")
        if not api_key:
            st.warning("Please enter your OpenAI API key to continue")
            st.stop()
    
    return OpenAI(api_key=api_key)

client = get_openai_client()

# Sidebar for user input
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # User-defined prompt
    default_prompt = "Generate synthetic sales data for an e-commerce platform. Include fields for date, customer_id (Customer ###), order total (in $USD). For certain orders, the order total should be negative. Create data for 10 customers. Output in JSON form."
    
    user_prompt = st.text_area(
        "Enter your prompt:",
        value=default_prompt,
        height=150,
        help="Customize the prompt to generate different types of synthetic data"
    )
    
    # Number of customers/records
    num_customers = st.slider(
        "Number of customers/records:",
        min_value=5,
        max_value=50,
        value=10,
        help="Adjust the number of data points to generate"
    )
    
    # Model selection
    model_name = st.selectbox(
        "Select OpenAI model:",
        ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
        help="Choose which OpenAI model to use for generation"
    )
    
    generate_button = st.button("🚀 Generate Data", type="primary")

# Main content area
if generate_button:
    if not user_prompt:
        st.error("Please enter a prompt to generate data.")
        st.stop()
    
    # Add number of customers to the prompt
    final_prompt = f"{user_prompt} Generate data for {num_customers} customers."
    
    with st.spinner("Generating synthetic data..."):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": final_prompt}],
                response_format={"type": "json_object"}
            )
            
            customer_data = json.loads(response.choices[0].message.content)
            
            # Display the raw JSON data
            with st.expander("📋 View Raw JSON Data"):
                st.json(customer_data)
            
            # Convert to DataFrame
            try:
                # Try to find the main data array in the JSON response
                data_key = None
                for key in customer_data.keys():
                    if isinstance(customer_data[key], list) and len(customer_data[key]) > 0:
                        data_key = key
                        break
                
                if data_key:
                    df = pd.DataFrame(customer_data[data_key])
                else:
                    # If no obvious array found, try to convert the first list found
                    for value in customer_data.values():
                        if isinstance(value, list):
                            df = pd.DataFrame(value)
                            break
                    else:
                        st.error("Could not find a suitable data array in the response.")
                        st.stop()
                
                # Display the data
                st.subheader("📊 Generated Data Preview")
                st.dataframe(df)
                
                # Show basic statistics
                st.subheader("📈 Data Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Records", len(df))
                
                with col2:
                    if 'order_total' in df.columns or 'order total' in df.columns:
                        total_col = 'order_total' if 'order_total' in df.columns else 'order total'
                        st.metric("Total Sales", f"${df[total_col].sum():,.2f}")
                
                with col3:
                    if 'customer_id' in df.columns or 'customer id' in df.columns:
                        cust_col = 'customer_id' if 'customer_id' in df.columns else 'customer id'
                        st.metric("Unique Customers", df[cust_col].nunique())
                
                # Download options
                st.subheader("💾 Download Options")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # CSV download
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download CSV",
                        data=csv,
                        file_name="synthetic_sales_data.csv",
                        mime="text/csv"
                    )
                
                with col2:
                    # Excel download
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sales Data')
                    excel_data = output.getvalue()
                    
                    st.download_button(
                        label="📥 Download Excel",
                        data=excel_data,
                        file_name="synthetic_sales_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                
            except Exception as e:
                st.error(f"Error processing data: {str(e)}")
                st.json(customer_data)  # Show the raw response for debugging
            
        except Exception as e:
            st.error(f"Error generating data: {str(e)}")
            st.info("Please check your API key and try again.")

# Instructions section
with st.expander("ℹ️ How to use this app"):
    st.markdown("""
    ### Usage Instructions:
    
    1. **Enter your OpenAI API key** (if not using Streamlit secrets)
    2. **Customize the prompt** in the sidebar to generate different types of data
    3. **Adjust the number of records** using the slider
    4. **Select the OpenAI model** you want to use
    5. **Click 'Generate Data'** to create synthetic data
    6. **Download** the data in CSV or Excel format
    
    ### Prompt Tips:
    - Be specific about the fields you want (e.g., "Include product category, quantity, and price")
    - Specify the format (e.g., "Output as JSON with sales_data as the main key")
    - Mention any special requirements (e.g., "Include some negative values for returns")
    """)

# Footer
st.markdown("---")
st.caption("Powered by OpenAI and Streamlit | Generate synthetic data for testing and development purposes")
