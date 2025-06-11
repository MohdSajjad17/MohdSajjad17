import os
import zipfile
import tempfile
import shutil
import time
import streamlit as st
from tableauserverclient import Server, PersonalAccessTokenAuth

# Streamlit app configuration
st.set_page_config(page_title="TDE to HYPER Converter", layout="wide")
st.title("Tableau TWBX TDE to HYPER Converter")

# Session state to maintain credentials and selections
if 'auth' not in st.session_state:
    st.session_state.auth = {
        'server_url': '',
        'token_name': '',
        'token_value': '',
        'site_id': '',
        'project_id': ''
    }
if 'projects' not in st.session_state:
    st.session_state.projects = []

# Global variables
TEMP_DIR = tempfile.mkdtemp()
HYPER_CONVERSION_TIMEOUT = 300  # 5 minutes

def cleanup_temp_files():
    """Clean up temporary files"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def get_server_connection():
    """Establish connection to Tableau Server"""
    try:
        auth = PersonalAccessTokenAuth(
            st.session_state.auth['token_name'],
            st.session_state.auth['token_value'],
            site_id=st.session_state.auth['site_id']
        )
        server = Server(st.session_state.auth['server_url'])
        server.auth.sign_in(auth)
        return server
    except Exception as e:
        st.error(f"Failed to connect to Tableau Server: {str(e)}")
        return None

def load_projects(server):
    """Load available projects from Tableau Server"""
    try:
        all_projects = list(server.projects.get())
        return [(p.id, p.name) for p in all_projects]
    except Exception as e:
        st.error(f"Failed to load projects: {str(e)}")
        return []

def get_workbooks_in_project(server, project_id):
    """Get list of workbooks in the selected project"""
    try:
        workbooks = list(server.workbooks.get())
        return [wb for wb in workbooks if wb.project_id == project_id]
    except Exception as e:
        st.error(f"Failed to load workbooks: {str(e)}")
        return []

def download_workbook(server, workbook_id, download_path):
    """Download a specific workbook"""
    try:
        server.workbooks.download(workbook_id, filepath=download_path)
        return True
    except Exception as e:
        st.error(f"Failed to download workbook: {str(e)}")
        return False

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

def convert_tde_to_hyper(tde_path, hyper_path, server):
    """
    Convert TDE to HYPER using Tableau Server API
    """
    try:
        with st.spinner(f"Converting {os.path.basename(tde_path)} to HYPER..."):
            # Publish the TDE
            datasource_name = os.path.basename(tde_path).replace('.tde', '.hyper')
            datasource_item = server.datasources.publish(
                st.session_state.auth['project_id'],
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

def process_workbook(server, workbook_id):
    """Main processing function for workbooks"""
    try:
        # Setup directories
        os.makedirs(TEMP_DIR, exist_ok=True)
        temp_workbook_path = os.path.join(TEMP_DIR, "temp_workbook.twbx")
        
        # Download the workbook
        if not download_workbook(server, workbook_id, temp_workbook_path):
            return None
        
        # Extract the workbook
        extracted_dir = os.path.join(TEMP_DIR, "extracted")
        os.makedirs(extracted_dir, exist_ok=True)
        extract_twbx(temp_workbook_path, extracted_dir)
        
        # Find and convert TDE files
        tde_files = find_tde_files(extracted_dir)
        
        if not tde_files:
            st.warning("No TDE files found in the workbook")
            return None
        
        st.info(f"Found {len(tde_files)} TDE file(s) to convert")
        
        success_count = 0
        for tde_file in tde_files:
            hyper_file = tde_file.replace('.tde', '.hyper')
            if convert_tde_to_hyper(tde_file, hyper_file, server):
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
        output_path = os.path.join(TEMP_DIR, "converted_workbook.twbx")
        repackage_twbx(extracted_dir, output_path)
        
        return output_path
        
    except Exception as e:
        st.error(f"Error processing workbook: {str(e)}")
        return None

# Authentication form
def authentication_form():
    """Form for authenticating with Tableau Server"""
    with st.form("auth_form"):
        st.subheader("Tableau Server Authentication")
        
        server_url = st.text_input(
            "Server URL", 
            value=st.session_state.auth['server_url'],
            placeholder="https://your-tableau-server.com"
        )
        token_name = st.text_input(
            "Personal Access Token Name", 
            value=st.session_state.auth['token_name']
        )
        token_value = st.text_input(
            "Personal Access Token Value", 
            value=st.session_state.auth['token_value'],
            type="password"
        )
        site_id = st.text_input(
            "Site ID (leave empty for default site)", 
            value=st.session_state.auth['site_id']
        )
        
        submitted = st.form_submit_button("Connect to Tableau Server")
        
        if submitted:
            st.session_state.auth.update({
                'server_url': server_url,
                'token_name': token_name,
                'token_value': token_value,
                'site_id': site_id
            })
            
            # Test connection and load projects
            server = get_server_connection()
            if server:
                st.session_state.projects = load_projects(server)
                st.success("Connected to Tableau Server successfully!")

# Project selection form
def project_selection_form():
    """Form for selecting a project"""
    if not st.session_state.projects:
        return
    
    with st.form("project_form"):
        st.subheader("Project Selection")
        
        project_options = {name: id for id, name in st.session_state.projects}
        selected_project = st.selectbox(
            "Select a Project",
            options=list(project_options.keys()),
            index=0
        )
        
        submitted = st.form_submit_button("Load Workbooks")
        
        if submitted:
            st.session_state.auth['project_id'] = project_options[selected_project]
            st.success(f"Selected project: {selected_project}")

# Workbook selection and processing
def workbook_processing():
    """Handle workbook selection and processing"""
    if not st.session_state.auth.get('project_id'):
        return
    
    server = get_server_connection()
    if not server:
        return
    
    workbooks = get_workbooks_in_project(server, st.session_state.auth['project_id'])
    if not workbooks:
        st.warning("No workbooks found in the selected project")
        return
    
    workbook_options = {wb.name: wb.id for wb in workbooks}
    selected_workbook = st.selectbox(
        "Select a Workbook to Convert",
        options=list(workbook_options.keys()),
        index=0
    )
    
    if st.button("Convert TDE to HYPER in Selected Workbook"):
        with st.spinner(f"Processing {selected_workbook}..."):
            output_path = process_workbook(server, workbook_options[selected_workbook])
            
            if output_path:
                st.success("Conversion completed successfully!")
                
                # Offer download
                with open(output_path, "rb") as f:
                    st.download_button(
                        label="Download Converted Workbook",
                        data=f,
                        file_name=f"converted_{selected_workbook}.twbx",
                        mime="application/octet-stream"
                    )

# Main app interface
def main():
    # Show authentication form
    authentication_form()
    
    # Show project selection if authenticated
    if st.session_state.auth.get('server_url') and st.session_state.auth.get('token_value'):
        project_selection_form()
        
        # Show workbook processing if project selected
        if st.session_state.auth.get('project_id'):
            workbook_processing()
    
    st.sidebar.markdown("""
    ### Instructions:
    1. Connect to Tableau Server using PAT
    2. Select a project
    3. Select a workbook to convert
    4. Click "Convert TDE to HYPER"
    5. Download the converted workbook
    
    ### Requirements:
    - Tableau Server with API access
    - Personal Access Token with publish rights
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
