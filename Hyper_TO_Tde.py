import os
import zipfile
import tempfile
import shutil
import time
import streamlit as st
from tableauserverclient import Server, TableauAuth

# Streamlit app configuration
st.set_page_config(page_title="TDE to HYPER Converter", layout="wide")
st.title("Tableau TWBX TDE to HYPER Converter")

# Session state to maintain credentials
if 'credentials' not in st.session_state:
    st.session_state.credentials = {
        'server_url': '',
        'username': '',
        'password': '',
        'site_id': ''
    }

# Global variables
TEMP_DIR = tempfile.mkdtemp()
HYPER_CONVERSION_TIMEOUT = 300  # 5 minutes

def cleanup_temp_files():
    """Clean up temporary files"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def extract_twbx(twbx_path, extract_dir):
    """Extract a .twbx file to directory"""
    with zipfile.ZipFile(twbx_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    return extract_dir

def find_tde_files(directory):
    """Find all .tde files in directory structure"""
    tde_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.tde'):
                tde_files.append(os.path.join(root, file))
    return tde_files

def convert_tde_to_hyper(tde_path, hyper_path, server_url, username, password, site_id=""):
    """
    Convert TDE to HYPER using Tableau Server API
    """
    try:
        with st.spinner(f"Converting {os.path.basename(tde_path)} to HYPER..."):
            # Initialize Tableau Server connection
            server = Server(server_url)
            auth = TableauAuth(username, password, site_id=site_id)
            
            with server.auth.sign_in(auth):
                # Create temp project if needed
                temp_project = "TDE Conversion Temp Project"
                projects = {p.name: p for p in server.projects.get()}
                if temp_project not in projects:
                    server.projects.create(temp_project)
                    projects = {p.name: p for p in server.projects.get()}  # Refresh list
                
                # Publish the TDE
                datasource_name = os.path.basename(tde_path).replace('.tde', '.hyper')
                datasource_item = server.datasources.publish(
                    projects[temp_project].id, 
                    tde_path, 
                    datasource_name, 
                    mode="Overwrite"
                )
                
                # Wait for conversion to complete
                time.sleep(5)  # Initial wait
                
                # Download as HYPER
                server.datasources.download(datasource_item.id, hyper_path)
                
                # Clean up
                server.datasources.delete(datasource_item.id)
                
        return True
    except Exception as e:
        st.error(f"Failed to convert {tde_path}: {str(e)}")
        return False

def update_workbook_connections(extracted_dir, old_ds_name, new_ds_name):
    """
    Update workbook connections to point to the new HYPER file
    """
    workbook_files = [f for f in os.listdir(extracted_dir) if f.endswith('.twb')]
    
    for wb_file in workbook_files:
        wb_path = os.path.join(extracted_dir, wb_file)
        try:
            with open(wb_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace TDE references with HYPER
            updated_content = content.replace(old_ds_name, new_ds_name)
            
            with open(wb_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
        except Exception as e:
            st.warning(f"Couldn't update connections in {wb_file}: {str(e)}")

def repackage_twbx(extracted_dir, output_path):
    """Create new .twbx file from directory contents"""
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(extracted_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, extracted_dir)
                zipf.write(file_path, arcname)

def process_uploaded_file(uploaded_file, server_url, username, password, site_id):
    """Main processing function for uploaded files"""
    try:
        # Setup directories
        os.makedirs(TEMP_DIR, exist_ok=True)
        uploaded_path = os.path.join(TEMP_DIR, uploaded_file.name)
        
        # Save uploaded file
        with open(uploaded_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Extract the workbook
        extracted_dir = os.path.join(TEMP_DIR, "extracted")
        os.makedirs(extracted_dir, exist_ok=True)
        extract_twbx(uploaded_path, extracted_dir)
        
        # Find and convert TDE files
        tde_files = find_tde_files(extracted_dir)
        
        if not tde_files:
            st.warning("No TDE files found in the workbook")
            return None
        
        st.info(f"Found {len(tde_files)} TDE file(s) to convert")
        
        success_count = 0
        for tde_file in tde_files:
            hyper_file = tde_file.replace('.tde', '.hyper')
            if convert_tde_to_hyper(tde_file, hyper_file, server_url, username, password, site_id):
                # Update workbook connections
                update_workbook_connections(
                    extracted_dir,
                    os.path.basename(tde_file),
                    os.path.basename(hyper_file)
                )
                # Remove old TDE file
                os.remove(tde_file)
                success_count += 1
        
        if success_count == 0:
            st.error("Failed to convert any TDE files")
            return None
        
        # Repackage the workbook
        output_path = os.path.join(TEMP_DIR, "converted_" + uploaded_file.name)
        repackage_twbx(extracted_dir, output_path)
        
        return output_path
        
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

# Credentials form
def credentials_form():
    """Form for entering Tableau Server credentials"""
    with st.form("credentials_form"):
        st.subheader("Tableau Server Credentials")
        
        server_url = st.text_input(
            "Server URL", 
            value=st.session_state.credentials['server_url'],
            placeholder="https://your-tableau-server.com"
        )
        username = st.text_input(
            "Username", 
            value=st.session_state.credentials['username']
        )
        password = st.text_input(
            "Password", 
            value=st.session_state.credentials['password'],
            type="password"
        )
        site_id = st.text_input(
            "Site ID (leave empty for default site)", 
            value=st.session_state.credentials['site_id']
        )
        
        submitted = st.form_submit_button("Save Credentials")
        
        if submitted:
            st.session_state.credentials = {
                'server_url': server_url,
                'username': username,
                'password': password,
                'site_id': site_id
            }
            st.success("Credentials saved!")

# Main app interface
def main():
    # Show credentials form
    credentials_form()
    
    # Only proceed if credentials are provided
    if not all(st.session_state.credentials.values()):
        st.warning("Please provide Tableau Server credentials first")
        return
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload a Tableau Workbook (.twbx)", 
        type=["twbx"],
        accept_multiple_files=False
    )
    
    if uploaded_file:
        st.info(f"File uploaded: {uploaded_file.name}")
        
        if st.button("Convert TDE to HYPER"):
            with st.spinner("Processing workbook..."):
                output_path = process_uploaded_file(
                    uploaded_file,
                    st.session_state.credentials['server_url'],
                    st.session_state.credentials['username'],
                    st.session_state.credentials['password'],
                    st.session_state.credentials['site_id']
                )
                
                if output_path:
                    st.success("Conversion completed successfully!")
                    
                    # Offer download
                    with open(output_path, "rb") as f:
                        st.download_button(
                            label="Download Converted Workbook",
                            data=f,
                            file_name=os.path.basename(output_path),
                            mime="application/octet-stream"
                        )
    
    st.sidebar.markdown("""
    ### Instructions:
    1. Enter your Tableau Server credentials
    2. Upload a Tableau packaged workbook (.twbx)
    3. Click "Convert TDE to HYPER"
    4. Download the converted workbook
    
    ### Requirements:
    - Valid Tableau Server credentials
    - Internet connection to your Tableau Server
    - Workbooks must be under 200MB (Streamlit file upload limit)
    """)

# Run the app
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
    finally:
        cleanup_temp_files()
