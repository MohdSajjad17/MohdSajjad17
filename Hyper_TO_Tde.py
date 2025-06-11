import os
import zipfile
import tempfile
import shutil
import time
import streamlit as st
from tableauserverclient import Server, TableauAuth
from tableauhyperapi import HyperProcess, Connection, Telemetry

# Streamlit app configuration
st.set_page_config(page_title="TDE to HYPER Converter", layout="wide")
st.title("Tableau TWBX TDE to HYPER Converter")

# Constants
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

def convert_tde_to_hyper(tde_path, hyper_path):
    """
    Convert TDE to HYPER using Tableau Server API
    """
    try:
        with st.spinner(f"Converting {os.path.basename(tde_path)} to HYPER..."):
            # Initialize Tableau Server connection
            server = Server(st.secrets["tableau"]["server_url"])
            auth = TableauAuth(
                st.secrets["tableau"]["username"],
                st.secrets["tableau"]["password"],
                site_id=st.secrets["tableau"].get("site_id", "")
            )
            
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

def process_uploaded_file(uploaded_file):
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
            if convert_tde_to_hyper(tde_file, hyper_file):
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

# Main app interface
def main():
    st.sidebar.header("Configuration")
    
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
                output_path = process_uploaded_file(uploaded_file)
                
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
    1. Upload a Tableau packaged workbook (.twbx)
    2. Click "Convert TDE to HYPER"
    3. Download the converted workbook
    
    ### Requirements:
    - Tableau Server credentials (configure in secrets.toml)
    - Internet connection to your Tableau Server
    """)

# Run the app
if __name__ == "__main__":
    # Check for required secrets
    try:
        if not all(key in st.secrets["tableau"] for key in ["server_url", "username", "password"]):
            st.error("Missing Tableau Server configuration in secrets.toml")
            st.stop()
        
        main()
    except Exception as e:
        st.error(f"Initialization error: {str(e)}")
    finally:
        cleanup_temp_files()
