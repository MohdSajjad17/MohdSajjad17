import os
import zipfile
import shutil
import tempfile
import requests
import streamlit as st
from tableauserverclient import Server, TableauAuth
from tableauhyperapi import HyperProcess, Connection, CreateMode, TableDefinition, SqlType, TableName

# Set page config
st.set_page_config(page_title="TWBX Converter", page_icon="📊", layout="wide")

# Custom CSS for better appearance
st.markdown("""
<style>
    .stProgress > div > div > div > div {
        background-color: #1f77b4;
    }
    .stButton>button {
        width: 100%;
    }
    .stFileUploader>div>div>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

def download_twbx(url, save_path, auth=None):
    """Download a .twbx file from a URL"""
    try:
        if auth:
            response = requests.get(url, auth=auth)
        else:
            response = requests.get(url)
        
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return save_path
    except Exception as e:
        st.error(f"Failed to download file: {str(e)}")
        return None

def convert_tde_to_hyper(tde_path, hyper_path, server_url, username, password, site_id):
    """Convert a .tde file to .hyper format using Tableau Server Client"""
    try:
        tableau_auth = TableauAuth(username, password, site_id=site_id)
        server = Server(server_url, use_server_version=True)
        
        with server.auth.sign_in(tableau_auth):
            # Create a temporary project for uploads
            temp_project_name = "Temporary Conversion Project"
            project_item = None
            
            # Check if project already exists
            for proj in server.projects.get():
                if proj.name == temp_project_name:
                    project_item = proj
                    break
            
            # Create project if it doesn't exist
            if not project_item:
                project_item = Server.PublishableProject(temp_project_name)
                project_item = server.projects.create(project_item)
            
            # Publish the .tde temporarily
            datasource_item = Server.DatasourceItem(project_item.id)
            datasource_item = server.datasources.publish(datasource_item, tde_path, 'Overwrite')
            
            # Download as .hyper
            server.datasources.download(datasource_item.id, filepath=hyper_path)
            
            # Delete the temporary datasource
            server.datasources.delete(datasource_item.id)
            
            return True
    except Exception as e:
        st.error(f"Conversion failed: {str(e)}")
        return False

def process_twbx(twbx_path, output_path, server_url, username, password, site_id):
    """Process a .twbx file to convert all .tde to .hyper"""
    temp_dir = tempfile.mkdtemp()
    success = True
    
    try:
        # Unzip the .twbx file
        with zipfile.ZipFile(twbx_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find all .tde files in the extracted directory
        tde_files = []
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.lower().endswith('.tde'):
                    tde_files.append(os.path.join(root, file))
        
        if not tde_files:
            st.warning("No TDE files found in the workbook. Nothing to convert.")
            return False
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, tde_path in enumerate(tde_files):
            hyper_path = os.path.splitext(tde_path)[0] + '.hyper'
            
            status_text.text(f"Converting {os.path.basename(tde_path)} to HYPER format ({i+1}/{len(tde_files)})")
            progress_bar.progress((i + 1) / len(tde_files))
            
            if not convert_tde_to_hyper(tde_path, hyper_path, server_url, username, password, site_id):
                success = False
                break
            
            # Remove the original .tde file
            os.remove(tde_path)
        
        if success:
            # Create a new .twbx file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            return True
        
    except Exception as e:
        st.error(f"Error processing workbook: {str(e)}")
        return False
    finally:
        # Clean up temporary directory
        shutil.rmtree(temp_dir, ignore_errors=True)

def main():
    st.title("📊 TWBX TDE to HYPER Converter")
    st.markdown("""
    This tool converts TDE (Tableau Data Extract) files within a TWBX workbook to the newer HYPER format.
    You'll need Tableau Server/Online credentials with publishing rights.
    """)
    
    with st.expander("⚙️ Connection Settings", expanded=True):
        col1, col2 = st.columns(2)
        server_url = col1.text_input("Tableau Server URL", "https://your-tableau-server.com")
        site_id = col2.text_input("Site ID (leave empty for default)", "")
        username = col1.text_input("Username")
        password = col2.text_input("Password", type="password")
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["📤 Upload Workbook", "🔗 Download from URL"])
    
    with tab1:
        uploaded_file = st.file_uploader("Choose a TWBX file", type=["twbx"])
        
        if uploaded_file is not None:
            temp_dir = tempfile.mkdtemp()
            input_path = os.path.join(temp_dir, uploaded_file.name)
            
            with open(input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            output_path = os.path.splitext(uploaded_file.name)[0] + "_converted.twbx"
            
            if st.button("Convert Workbook"):
                with st.spinner("Processing..."):
                    if process_twbx(input_path, output_path, server_url, username, password, site_id):
                        st.success("Conversion completed successfully!")
                        
                        with open(output_path, "rb") as f:
                            st.download_button(
                                label="Download Converted Workbook",
                                data=f,
                                file_name=output_path,
                                mime="application/octet-stream"
                            )
            
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    with tab2:
        twbx_url = st.text_input("Enter TWBX URL")
        
        if twbx_url:
            if st.button("Download and Convert"):
                temp_dir = tempfile.mkdtemp()
                downloaded_twbx = os.path.join(temp_dir, "downloaded_workbook.twbx")
                output_twbx = os.path.join(temp_dir, "converted_workbook.twbx")
                
                with st.spinner("Downloading workbook..."):
                    if download_twbx(twbx_url, downloaded_twbx):
                        with st.spinner("Converting..."):
                            if process_twbx(downloaded_twbx, output_twbx, server_url, username, password, site_id):
                                st.success("Conversion completed successfully!")
                                
                                with open(output_twbx, "rb") as f:
                                    st.download_button(
                                        label="Download Converted Workbook",
                                        data=f,
                                        file_name="converted_workbook.twbx",
                                        mime="application/octet-stream"
                                    )
                
                shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
