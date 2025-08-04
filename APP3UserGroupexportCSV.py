import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
from io import BytesIO
import base64

# ------------------------
# Custom CSS Styling
# ------------------------
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load custom CSS
local_css("style.css")

# ------------------------
# App Configuration
# ------------------------
st.set_page_config(
    page_title="Tableau Migration Toolkit",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------
# Custom Components
# ------------------------
def colored_header(label, description=None, color=None):
    st.markdown(
        f"""
        <div class="colored-header" style="border-left: 5px solid {color};">
            <h2>{label}</h2>
            {f'<p>{description}</p>' if description else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

def feature_card(title, description, icon):
    st.markdown(
        f"""
        <div class="feature-card">
            <div class="feature-icon">{icon}</div>
            <h3>{title}</h3>
            <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# ------------------------
# App Header
# ------------------------
def show_header():
    st.markdown("""
    <div class="main-header">
        <div class="title-section">
            <h1>Tableau Migration Toolkit</h1>
            <p class="subtitle">Streamline your Tableau content migration with powerful automation</p>
        </div>
        <div class="logo-section">
            <img src="https://www.tableau.com/sites/default/files/pages/tableau-logo.png" width="120">
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

# ------------------------
# Sidebar Navigation
# ------------------------
def sidebar_navigation():
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>Navigation</h2>
        </div>
        """, unsafe_allow_html=True)
        
        mode = st.radio(
            "Select Operation",
            [
                "📤 Export Content", 
                "📥 Import Users/Groups", 
                "🔄 Convert User Format",
                "⬇️ Download Workbooks",
                "⬆️ Upload Workbooks"
            ],
            key="nav_mode"
        )
        
        st.markdown("---")
        
        st.markdown("""
        <div class="sidebar-footer">
            <p class="version">Version 2.0</p>
            <p class="author">Developed by Data Ops Team</p>
        </div>
        """, unsafe_allow_html=True)
    
    return mode

# ------------------------
# Connection Manager
# ------------------------
def connection_manager():
    colored_header("Tableau Server Connection", "Provide your Tableau Server/Cloud credentials", "#4B8BBE")
    
    col1, col2 = st.columns(2)
    with col1:
        server_url = st.text_input("Server URL", "https://prod-apsoutheast-b.online.tableau.com", 
                                 help="URL of your Tableau Server or Cloud instance")
        site_content_url = st.text_input("Site Content URL", "",
                                       help="Leave empty for Default site or enter site content URL")
    
    with col2:
        auth_method = st.selectbox("Authentication Method", 
                                 ["PAT (Personal Access Token)", "Username & Password"],
                                 help="Choose your preferred authentication method")
        
        if auth_method == "PAT (Personal Access Token)":
            token_name = st.text_input("PAT Name", help="Name of your Personal Access Token")
            token_value = st.text_input("PAT Secret", type="password", help="Secret value of your PAT")
            auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
        else:
            username = st.text_input("Username", help="Your Tableau username")
            password = st.text_input("Password", type="password", help="Your Tableau password")
            auth = TSC.TableauAuth(username, password, site_id=site_content_url)
    
    st.markdown("---")
    return auth, server_url, site_content_url

# ------------------------
# Export Functions
# ------------------------
def export_content(auth):
    try:
        with st.spinner("🔐 Connecting to Tableau Server..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connection established successfully")
        
        colored_header("Export Options", "Select what you want to export", "#2e7d32")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("👥 Export Users", help="Export all users with their roles and details"):
                export_users(server)
        
        with col2:
            if st.button("👪 Export Groups", help="Export all groups with their IDs"):
                export_groups(server)
        
        with col3:
            if st.button("📂 Export Projects", help="Export all projects with descriptions"):
                export_projects(server)
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            if st.button("📊 Export Workbooks", help="Export workbook metadata"):
                export_workbooks(server)
        
        with col5:
            if st.button("📈 Export Datasources", help="Export datasource metadata"):
                export_datasources(server)
        
        with col6:
            if st.button("🔄 Refresh Connection", help="Reconnect to Tableau Server"):
                server.auth.sign_out()
                st.experimental_rerun()
        
        server.auth.sign_out()
        st.info("🔒 Connection closed successfully")
    
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")

def export_users(server):
    with st.spinner("Fetching users..."):
        users, _ = server.users.get()
        data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
        headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
        to_csv_download(data, headers, "users.csv", "⬇️ Download Users")

def export_groups(server):
    with st.spinner("Fetching groups..."):
        groups, _ = server.groups.get()
        data = [[g.name, g.id] for g in groups]
        headers = ["Group Name", "Group ID"]
        to_csv_download(data, headers, "groups.csv", "⬇️ Download Groups")

def export_projects(server):
    with st.spinner("Fetching projects..."):
        projects, _ = server.projects.get()
        data = [[p.name, p.description, p.content_permissions] for p in projects]
        headers = ["Name", "Description", "Content Permissions"]
        to_csv_download(data, headers, "projects.csv", "⬇️ Download Projects")

def export_workbooks(server):
    with st.spinner("Fetching workbooks..."):
        workbooks, _ = server.workbooks.get()
        data = [[w.name, w.owner_id, w.project_name, w.created_at, w.updated_at] for w in workbooks]
        headers = ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"]
        to_csv_download(data, headers, "workbooks.csv", "⬇️ Download Workbooks")

def export_datasources(server):
    with st.spinner("Fetching datasources..."):
        datasources, _ = server.datasources.get()
        data = [[d.name, d.owner_id, d.project_name, d.created_at, d.updated_at] for d in datasources]
        headers = ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"]
        to_csv_download(data, headers, "datasources.csv", "⬇️ Download Datasources")

# ------------------------
# Import Functions
# ------------------------
def import_content(auth):
    colored_header("Import Content", "Upload your CSV files to import users or groups", "#1565c0")
    
    import_type = st.radio(
        "Select Import Type",
        ["👥 Users", "👪 Groups"],
        horizontal=True
    )
    
    uploaded_file = st.file_uploader(
        f"Upload {import_type.lower()} CSV file",
        type="csv",
        help="Ensure your CSV matches the required format"
    )
    
    if uploaded_file:
        st.success("✅ File uploaded successfully")
        df = pd.read_csv(uploaded_file)
        
        with st.expander("📋 Preview Data"):
            st.dataframe(df.head())
        
        if st.button(f"🚀 Import {import_type}", type="primary"):
            run_import(import_type.strip(), uploaded_file, auth)

# ------------------------
# Converter Functions
# ------------------------
def convert_user_format():
    colored_header("User Format Converter", "Convert Excel user exports to Tableau-compatible CSV", "#6a1b9a")
    
    st.info("""
    This tool converts Excel files exported from Tableau Server to the CSV format required for user imports.
    Upload your Excel file below to convert it.
    """)
    
    uploaded_file = st.file_uploader(
        "Upload Excel File",
        type=["xlsx", "xls"],
        help="Upload an Excel file exported from Tableau Server"
    )
    
    if uploaded_file:
        st.success("✅ File uploaded successfully")
        df = pd.read_excel(uploaded_file)
        
        with st.expander("📋 Preview Original Data"):
            st.dataframe(df.head())
        
        if st.button("🔃 Convert to CSV", type="primary"):
            convert_excel_to_csv(uploaded_file)

# ------------------------
# Workbook Download Functions
# ------------------------
def download_workbooks_ui(auth):
    colored_header("Workbook Downloader", "Download workbooks from Tableau Server", "#00838f")
    
    col1, col2 = st.columns(2)
    
    with col1:
        project_filter = st.text_input(
            "Filter by Project Name",
            help="Leave empty to download from all projects"
        )
    
    with col2:
        workbook_filter = st.text_input(
            "Filter by Workbook Name",
            help="Leave empty to download all workbooks"
        )
    
    if st.button("🔍 Search Workbooks", type="primary"):
        with st.spinner("Searching for matching workbooks..."):
            download_workbooks(auth, project_filter, workbook_filter)

# ------------------------
# Workbook Upload Functions
# ------------------------
def upload_workbooks_ui(auth):
    colored_header("Workbook Uploader", "Upload workbooks to Tableau Server", "#2e7d32")
    
    project_option = st.radio(
        "Project Selection",
        ["Select existing project", "Create new project"],
        horizontal=True
    )
    
    project_name = None
    if project_option == "Create new project":
        project_name = st.text_input("New Project Name")
    else:
        with st.spinner("Fetching projects..."):
            try:
                server = connect_to_tableau(auth)
                projects, _ = server.projects.get()
                project_names = [p.name for p in projects]
                selected_project = st.selectbox("Select Project", project_names)
                project_id = next(p.id for p in projects if p.name == selected_project)
                server.auth.sign_out()
            except Exception as e:
                st.error(f"Failed to fetch projects: {str(e)}")
    
    uploaded_files = st.file_uploader(
        "Upload Workbook Files (.twbx or .twb)",
        type=["twbx", "twb"],
        accept_multiple_files=True,
        help="Select one or more workbook files to upload"
    )
    
    if uploaded_files and st.button("🚀 Upload Workbooks", type="primary"):
        upload_workbooks(auth, project_name if project_name else selected_project)

# ------------------------
# Helper Functions
# ------------------------
def to_csv_download(data: list, headers: list, filename: str, label: str):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv",
        help=f"Download {filename}"
    )

def connect_to_tableau(auth):
    server = TSC.Server(server_url, use_server_version=True)
    server.auth.sign_in(auth)
    return server

# ------------------------
# Main App Logic
# ------------------------
def main():
    # Create style.css if it doesn't exist
    if not os.path.exists("style.css"):
        with open("style.css", "w") as f:
            f.write("""
            /* Main header styling */
            .main-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem 0;
            }
            
            .title-section h1 {
                color: #2c3e50;
                margin-bottom: 0.5rem;
            }
            
            .subtitle {
                color: #7f8c8d;
                font-size: 1.1rem;
                margin-top: 0;
            }
            
            /* Colored headers */
            .colored-header {
                padding: 0.5rem 1rem;
                margin: 1.5rem 0 1rem 0;
                background-color: #f8f9fa;
                border-radius: 4px;
            }
            
            .colored-header h2 {
                margin: 0;
                color: #2c3e50;
            }
            
            .colored-header p {
                margin: 0.25rem 0 0 0;
                color: #7f8c8d;
                font-size: 0.9rem;
            }
            
            /* Sidebar styling */
            .sidebar-header {
                padding: 0.5rem 0;
                margin-bottom: 1rem;
                border-bottom: 1px solid #eee;
            }
            
            .sidebar-header h2 {
                color: #2c3e50;
                margin: 0;
            }
            
            .sidebar-footer {
                margin-top: 2rem;
                padding-top: 1rem;
                border-top: 1px solid #eee;
                font-size: 0.8rem;
                color: #7f8c8d;
            }
            
            /* Feature cards */
            .feature-card {
                background: white;
                border-radius: 8px;
                padding: 1.5rem;
                margin-bottom: 1rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                transition: transform 0.2s;
            }
            
            .feature-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }
            
            .feature-icon {
                font-size: 2rem;
                margin-bottom: 1rem;
                color: #3498db;
            }
            
            .feature-card h3 {
                margin-top: 0;
                color: #2c3e50;
            }
            
            .feature-card p {
                color: #7f8c8d;
                margin-bottom: 0;
            }
            
            /* Button styling */
            .stButton>button {
                border-radius: 4px;
                padding: 0.5rem 1rem;
                transition: all 0.3s;
            }
            
            .stButton>button:hover {
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            /* File uploader styling */
            .stFileUploader>div>div>div>div {
                border: 2px dashed #3498db;
                border-radius: 8px;
                padding: 2rem;
                background-color: #f8f9fa;
            }
            
            /* Spinner styling */
            .stSpinner>div {
                margin: 0 auto;
            }
            """)

    show_header()
    mode = sidebar_navigation()
    
    if mode in ["📤 Export Content", "📥 Import Users/Groups", "⬇️ Download Workbooks", "⬆️ Upload Workbooks"]:
        auth, server_url, site_content_url = connection_manager()
    
    if mode == "📤 Export Content":
        export_content(auth)
    
    elif mode == "📥 Import Users/Groups":
        import_content(auth)
    
    elif mode == "🔄 Convert User Format":
        convert_user_format()
    
    elif mode == "⬇️ Download Workbooks":
        download_workbooks_ui(auth)
    
    elif mode == "⬆️ Upload Workbooks":
        upload_workbooks_ui(auth)

# ------------------------
# Run the App
# ------------------------
if __name__ == "__main__":
    main()
