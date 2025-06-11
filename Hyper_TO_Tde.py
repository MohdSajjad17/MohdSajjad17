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

# [Rest of your existing functions remain the same...]

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
                    site = server.sites.get_by_id(st.session_state.auth['site_id'] or server.sites.get_by_id("")
                    st.info(f"Connected to: {site.content_url} (Server version: {server.version})")

# [Rest of your existing UI code remains the same...]

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
