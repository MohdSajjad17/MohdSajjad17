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
if 'server_connection' not in st.session_state:
    st.session_state.server_connection = None

# Global variables
TEMP_DIR = tempfile.mkdtemp()
HYPER_CONVERSION_TIMEOUT = 300  # 5 minutes

def cleanup_temp_files():
    """Clean up temporary files"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def validate_server_url(url):
    """Validate the Tableau Server URL format"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not url.endswith('/'):
        url += '/'
    return url

def get_server_connection():
    """Establish connection to Tableau Server with better error handling"""
    try:
        # Validate and clean the server URL
        server_url = validate_server_url(st.session_state.auth['server_url'])
        
        auth = PersonalAccessTokenAuth(
            st.session_state.auth['token_name'],
            st.session_state.auth['token_value'],
            site_id=st.session_state.auth['site_id']
        )
        
        # Configure server with timeout and SSL verification
        server = Server(server_url, use_server_version=True)
        server.add_http_options({
            'verify': True,
            'timeout': 30
        })
        
        # Test the connection
        server.auth.sign_in(auth)
        
        # Simple API call to verify connection
        server.sites.get()
        
        st.session_state.server_connection = server
        return server
        
    except Exception as e:
        error_msg = str(e)
        if "SSL" in error_msg:
            st.error("SSL Certificate verification failed. Try using http:// or contact your server admin.")
        elif "timed out" in error_msg:
            st.error("Connection timed out. Check your server URL and network connection.")
        elif "404" in error_msg or "Page Not Found" in error_msg:
            st.error("Invalid Tableau Server URL. Make sure to include the correct base URL (e.g., https://server.tableau.com/)")
        else:
            st.error(f"Failed to connect to Tableau Server: {error_msg}")
        
        if st.session_state.server_connection:
            try:
                st.session_state.server_connection.auth.sign_out()
            except:
                pass
        st.session_state.server_connection = None
        return None

def load_projects(server):
    """Load available projects from Tableau Server with error handling"""
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

def authentication_form():
    """Improved authentication form with URL validation"""
    with st.form("auth_form"):
        st.subheader("Tableau Server Authentication")
        
        col1, col2 = st.columns(2)
        
        server_url = col1.text_input(
            "Server URL*", 
            value=st.session_state.auth['server_url'],
            placeholder="https://your-server.tableau.com"
        )
        
        site_id = col2.text_input(
            "Site ID (leave empty for default site)", 
            value=st.session_state.auth['site_id'],
            placeholder="Default site is usually empty"
        )
        
        token_name = col1.text_input(
            "Personal Access Token Name*", 
            value=st.session_state.auth['token_name'],
            placeholder="e.g., TDEConverter"
        )
        
        token_value = col2.text_input(
            "Personal Access Token Value*", 
            value=st.session_state.auth['token_value'],
            type="password",
            placeholder="Paste your token here"
        )
        
        submitted = st.form_submit_button("Connect to Tableau Server")
        
        if submitted:
            if not all([server_url, token_name, token_value]):
                st.error("Please fill all required fields (marked with *)")
                return
                
            st.session_state.auth.update({
                'server_url': server_url,
                'token_name': token_name,
                'token_value': token_value,
                'site_id': site_id if site_id else "",
                'project_id': ""
            })
            
            with st.spinner("Connecting to Tableau Server..."):
                server = get_server_connection()
                if server:
                    st.session_state.projects = load_projects(server)
                    st.success("Connected successfully!")
                    
                    # Display server info
                    site = server.sites.get_by_id(st.session_state.auth['site_id']) or server.sites.get_by_id("")
                    st.info(f"Connected to: {site.content_url} (Server version: {server.version})")

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

def main():
    # Show authentication form
    authentication_form()
    
    # Only proceed if we have a valid connection
    if st.session_state.server_connection:
        project_selection_form()
        
        if st.session_state.auth.get('project_id'):
            workbook_processing()
    
    st.sidebar.markdown("""
    ### Connection Troubleshooting:
    1. Ensure your server URL is correct (e.g., https://server.tableau.com)
    2. Verify your PAT has proper permissions
    3. Check if your server requires VPN connection
    4. Try both http:// and https:// if unsure
    5. Contact your Tableau admin if issues persist
    
    ### Requirements:
    - Tableau Server 2019.2+ (for PAT support)
    - PAT with "Publish" and "Read" permissions
    - Network access to your Tableau Server
    """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {str(e)}")
    finally:
        cleanup_temp_files()
