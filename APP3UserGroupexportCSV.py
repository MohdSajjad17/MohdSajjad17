import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
from io import BytesIO
import base64

# ------------------------
# Custom CSS Styling
# ------------------------
def inject_css():
    st.markdown("""
    <style>
        /* Main styles */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Main header styling */
        .main-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 0;
            border-bottom: 1px solid #e6e6e6;
            margin-bottom: 2rem;
        }
        
        .title-section h1 {
            color: #2c3e50;
            margin-bottom: 0.25rem;
            font-weight: 700;
        }
        
        .subtitle {
            color: #7f8c8d;
            font-size: 1.1rem;
            margin-top: 0;
        }
        
        /* Colored headers */
        .colored-header {
            padding: 1rem 1.5rem;
            margin: 1.5rem 0 1.5rem 0;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            border-left: 4px solid #4B8BBE;
        }
        
        .colored-header h2 {
            margin: 0;
            color: #2c3e50;
            font-weight: 600;
        }
        
        .colored-header p {
            margin: 0.25rem 0 0 0;
            color: #7f8c8d;
            font-size: 0.95rem;
        }
        
        /* Card styling */
        .feature-card {
            padding: 1.5rem;
            border-radius: 8px;
            background: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            margin-bottom: 1.5rem;
            border: 1px solid #e6e6e6;
            transition: all 0.3s ease;
        }
        
        .feature-card:hover {
            box-shadow: 0 6px 16px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        
        .feature-card h3 {
            color: #2c3e50;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        /* Sidebar styling */
        .sidebar-header {
            padding: 1rem 0;
            margin-bottom: 1rem;
            border-bottom: 1px solid #eee;
        }
        
        .sidebar-header h2 {
            color: #2c3e50;
            margin: 0;
            font-weight: 600;
        }
        
        .sidebar-footer {
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
            font-size: 0.8rem;
            color: #7f8c8d;
        }
        
        /* Button styling */
        .stButton>button {
            border-radius: 6px;
            padding: 0.5rem 1rem;
            transition: all 0.3s;
            border: none;
            font-weight: 500;
        }
        
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }
        
        .stButton>button.primary {
            background: linear-gradient(135deg, #4B8BBE 0%, #306998 100%);
            color: white;
        }
        
        /* Input styling */
        .stTextInput>div>div>input, 
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select {
            border-radius: 6px;
            padding: 0.5rem 1rem;
            border: 1px solid #ddd;
        }
        
        /* File uploader styling */
        .stFileUploader>div>div>div>div {
            border: 2px dashed #3498db;
            border-radius: 8px;
            padding: 2rem;
            background-color: rgba(52, 152, 219, 0.05);
            transition: all 0.3s;
        }
        
        .stFileUploader>div>div>div>div:hover {
            background-color: rgba(52, 152, 219, 0.1);
        }
        
        /* Spinner styling */
        .stSpinner>div {
            margin: 0 auto;
        }
        
        /* Status indicators */
        .status-success {
            padding: 0.75rem 1rem;
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
            border-radius: 4px;
            margin: 1rem 0;
        }
        
        .status-warning {
            padding: 0.75rem 1rem;
            background-color: #fff8e1;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
            margin: 1rem 0;
        }
        
        .status-error {
            padding: 0.75rem 1rem;
            background-color: #ffebee;
            border-left: 4px solid #f44336;
            border-radius: 4px;
            margin: 1rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

# ------------------------
# App Configuration
# ------------------------
st.set_page_config(
    page_title="Tableau Migration Toolkit",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject CSS at the start
inject_css()

# ------------------------
# Helper Functions
# ------------------------
@st.cache_data
def to_csv_download(data: list, headers: list, filename: str):
    df = pd.DataFrame(data, columns=headers)
    return df.to_csv(index=False).encode('utf-8')

def connect_to_tableau(auth, server_url):
    server = TSC.Server(server_url, use_server_version=True)
    server.auth.sign_in(auth)
    return server

def show_connection_status(server, auth):
    with st.expander("🔌 Connection Status", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Server", server.server_address)
            st.metric("Site", auth.site_id or "Default")
        with col2:
            st.metric("API Version", server.version)
            st.metric("User", getattr(auth, 'username', 'PAT User'))

# ------------------------
# Export Functions
# ------------------------
def export_users(server):
    with st.spinner("Fetching users..."):
        users, _ = server.users.get()
        data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
        headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
        csv = to_csv_download(data, headers, "users.csv")
        st.download_button(
            label="⬇️ Download Users",
            data=csv,
            file_name="users.csv",
            mime="text/csv",
            key="dl_users"
        )

def export_groups(server):
    with st.spinner("Fetching groups..."):
        groups, _ = server.groups.get()
        data = [[g.name, g.id] for g in groups]
        headers = ["Group Name", "Group ID"]
        csv = to_csv_download(data, headers, "groups.csv")
        st.download_button(
            label="⬇️ Download Groups",
            data=csv,
            file_name="groups.csv",
            mime="text/csv",
            key="dl_groups"
        )

def export_projects(server):
    with st.spinner("Fetching projects..."):
        projects, _ = server.projects.get()
        data = [[p.name, p.description, p.content_permissions] for p in projects]
        headers = ["Name", "Description", "Content Permissions"]
        csv = to_csv_download(data, headers, "projects.csv")
        st.download_button(
            label="⬇️ Download Projects",
            data=csv,
            file_name="projects.csv",
            mime="text/csv",
            key="dl_projects"
        )

def export_workbooks(server):
    with st.spinner("Fetching workbooks..."):
        workbooks, _ = server.workbooks.get()
        data = [[w.name, w.owner_id, w.project_name, w.created_at, w.updated_at] for w in workbooks]
        headers = ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"]
        csv = to_csv_download(data, headers, "workbooks.csv")
        st.download_button(
            label="⬇️ Download Workbooks",
            data=csv,
            file_name="workbooks.csv",
            mime="text/csv",
            key="dl_workbooks"
        )

def export_datasources(server):
    with st.spinner("Fetching datasources..."):
        datasources, _ = server.datasources.get()
        data = [[d.name, d.owner_id, d.project_name, d.created_at, d.updated_at] for d in datasources]
        headers = ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"]
        csv = to_csv_download(data, headers, "datasources.csv")
        st.download_button(
            label="⬇️ Download Datasources",
            data=csv,
            file_name="datasources.csv",
            mime="text/csv",
            key="dl_datasources"
        )

# ------------------------
# Download Workbook Functions
# ------------------------
def download_workbooks(auth, server_url):
    try:
        with st.spinner("🔄 Establishing secure connection to Tableau Server..."):
            server = connect_to_tableau(auth, server_url)
            st.toast("✅ Connection established successfully!", icon="✅")
        
        show_connection_status(server, auth)

        st.markdown("""
        <div class="colored-header">
            <h2>📥 Download Options</h2>
            <p>Select how you want to download workbooks from Tableau Server</p>
        </div>
        """, unsafe_allow_html=True)
        
        download_option = st.radio(
            "Select download scope:",
            ["Download all workbooks from a project", 
             "Download specific workbook",
             "Search and download workbooks"],
            horizontal=True,
            key="download_option"
        )

        with st.spinner("🔍 Loading available projects..."):
            projects, _ = server.projects.get()
            if not projects:
                st.error("No projects found on this site!")
                return
            
            project_names = [p.name for p in projects]
            selected_project = st.selectbox(
                "Select project:",
                project_names,
                help="Select the project containing the workbooks you want to download",
                key="project_select"
            )

        if download_option == "Download all workbooks from a project":
            _download_all_workbooks(server, selected_project)
            
        elif download_option == "Download specific workbook":
            _download_single_workbook(server, selected_project)
            
        else:
            _search_and_download_workbooks(server, selected_project)

        server.auth.sign_out()
        st.toast("🔐 Session ended successfully", icon="🔒")

    except TSC.ServerResponseError as e:
        st.error(f"❌ Tableau Server error: {str(e)}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")

def _download_all_workbooks(server, project_name):
    with st.spinner(f"🔍 Scanning project '{project_name}' for workbooks..."):
        workbooks, _ = server.workbooks.get()
        project_workbooks = [w for w in workbooks if w.project_name == project_name]
        
        if not project_workbooks:
            st.warning(f"⚠️ No workbooks found in project '{project_name}'")
            return
        
        st.success(f"Found {len(project_workbooks)} workbooks in '{project_name}'")
        
        progress_bar = st.progress(0)
        total = len(project_workbooks)
        
        for i, wb in enumerate(project_workbooks):
            try:
                progress_bar.progress((i + 1) / total, text=f"Downloading {wb.name}...")
                
                with st.spinner(f"⏳ Downloading '{wb.name}'..."):
                    workbook_path = server.workbooks.download(wb.id)
                    
                    with open(workbook_path, 'rb') as f:
                        workbook_data = f.read()
                    
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"Project: {wb.project_name}")
                            st.caption(f"Last updated: {wb.updated_at}")
                        with col2:
                            st.download_button(
                                label="Download",
                                data=workbook_data,
                                file_name=f"{wb.name}.twbx",
                                mime="application/octet-stream",
                                key=f"dl_{wb.id}"
                            )
                    
                    os.remove(workbook_path)
                    
            except Exception as e:
                st.error(f"Failed to download '{wb.name}': {str(e)}")
                continue
        
        progress_bar.empty()
        st.toast(f"🎉 Downloaded {len(project_workbooks)} workbooks!", icon="🎉")

def _download_single_workbook(server, project_name):
    with st.spinner(f"🔍 Loading workbooks from '{project_name}'..."):
        workbooks, _ = server.workbooks.get()
        project_workbooks = [w for w in workbooks if w.project_name == project_name]
        
        if not project_workbooks:
            st.warning(f"⚠️ No workbooks found in project '{project_name}'")
            return
        
        workbook_names = [w.name for w in project_workbooks]
        selected_workbook = st.selectbox(
            "Select workbook to download:",
            workbook_names,
            help="Select the specific workbook you want to download",
            key="workbook_select"
        )
        
        workbook = next(w for w in project_workbooks if w.name == selected_workbook)
        
        with st.expander("📊 Workbook Details", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Name", workbook.name)
                st.metric("Owner", workbook.owner_id)
            with col2:
                st.metric("Created", workbook.created_at)
                st.metric("Last Updated", workbook.updated_at)
        
        if st.button("🚀 Download Workbook", type="primary", key="download_wb"):
            with st.spinner(f"⏳ Downloading '{selected_workbook}'..."):
                try:
                    workbook_path = server.workbooks.download(workbook.id)
                    
                    with open(workbook_path, 'rb') as f:
                        workbook_data = f.read()
                    
                    st.download_button(
                        label="⬇️ Download Now",
                        data=workbook_data,
                        file_name=f"{selected_workbook}.twbx",
                        mime="application/octet-stream",
                        key=f"dl_{workbook.id}_single"
                    )
                    os.remove(workbook_path)
                    st.toast(f"✅ Downloaded '{selected_workbook}' successfully!", icon="✅")
                    
                except Exception as e:
                    st.error(f"❌ Download failed: {str(e)}")

def _search_and_download_workbooks(server, project_name):
    st.markdown("""
    <div class="colored-header">
        <h2>🔍 Search Workbooks</h2>
        <p>Find and download specific workbooks by name</p>
    </div>
    """, unsafe_allow_html=True)
    
    search_query = st.text_input(
        "Search by workbook name:",
        help="Enter part of the workbook name to filter results",
        key="workbook_search"
    )
    
    with st.spinner(f"🔍 Searching workbooks in '{project_name}'..."):
        workbooks, _ = server.workbooks.get()
        project_workbooks = [w for w in workbooks if w.project_name == project_name]
        
        if search_query:
            project_workbooks = [
                w for w in project_workbooks 
                if search_query.lower() in w.name.lower()
            ]
        
        if not project_workbooks:
            st.warning("⚠️ No matching workbooks found")
            return
        
        st.success(f"Found {len(project_workbooks)} matching workbooks")
        
        selected_workbooks = []
        for wb in project_workbooks:
            col1, col2 = st.columns([1, 4])
            with col1:
                selected = st.checkbox("Select", key=f"cb_{wb.id}")
            with col2:
                with st.expander(f"{wb.name} (Updated: {wb.updated_at})"):
                    st.write(f"**Owner:** {wb.owner_id}")
                    st.write(f"**Project:** {wb.project_name}")
                    st.write(f"**Created:** {wb.created_at}")
            
            if selected:
                selected_workbooks.append(wb)
        
        if selected_workbooks and st.button(
            f"📥 Download {len(selected_workbooks)} Selected Workbooks",
            type="primary",
            key="download_selected"
        ):
            progress_bar = st.progress(0)
            total = len(selected_workbooks)
            
            for i, wb in enumerate(selected_workbooks):
                progress_bar.progress((i + 1) / total, text=f"Downloading {wb.name}...")
                
                try:
                    workbook_path = server.workbooks.download(wb.id)
                    with open(workbook_path, 'rb') as f:
                        workbook_data = f.read()
                    
                    st.download_button(
                        label=f"⬇️ {wb.name}",
                        data=workbook_data,
                        file_name=f"{wb.name}.twbx",
                        mime="application/octet-stream",
                        key=f"dl_{wb.id}_multi"
                    )
                    os.remove(workbook_path)
                    
                except Exception as e:
                    st.error(f"Failed to download '{wb.name}': {str(e)}")
            
            progress_bar.empty()
            st.toast(f"🎉 Downloaded {len(selected_workbooks)} workbooks!", icon="🎉")

# ------------------------
# Main App Logic
# ------------------------
def show_welcome():
    st.markdown("""
    <div class="main-header">
        <div class="title-section">
            <h1>Tableau Migration Toolkit</h1>
            <p class="subtitle">Streamline your Tableau content migration with powerful automation</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>📤 Export Content</h3>
            <p>Export users, groups, projects, workbooks, and datasources from your Tableau Server to CSV for analysis and migration planning.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="feature-card">
            <h3>🔄 Convert User Format</h3>
            <p>Convert Excel user exports from Tableau Server to the CSV format required for user imports.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>📥 Import Users/Groups</h3>
            <p>Upload CSV files to import users or groups to your Tableau Server, streamlining user management.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="feature-card">
            <h3>⬇️ Download Workbooks</h3>
            <p>Download workbooks from Tableau Server for backup, migration, or local analysis.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.info("💡 Select an operation from the sidebar to get started")

def main():
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>Tableau Migration Toolkit</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.image("https://www.tableau.com/sites/default/files/2021-06/tableau-logo.png", width=150)
        
        mode = st.radio(
            "Select Operation",
            ["🏠 Dashboard",
             "📤 Export Content", 
             "📥 Import Users/Groups", 
             "🔄 Convert User Format",
             "⬇️ Download Workbooks"],
            key="nav_mode"
        )
        
        st.markdown("---")
        
        st.markdown("""
        <div class="sidebar-footer">
            <p class="version">Version 2.1</p>
            <p class="author">Developed by MS</p>
        </div>
        """, unsafe_allow_html=True)

    if mode == "🏠 Dashboard":
        show_welcome()
        return

    if mode in ["📤 Export Content", "📥 Import Users/Groups", "⬇️ Download Workbooks"]:
        st.markdown("""
        <div class="colored-header">
            <h2>Tableau Server Connection</h2>
            <p>Provide your Tableau Server/Cloud credentials</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            server_url = st.text_input("Server URL", "https://prod-apsoutheast-b.online.tableau.com", 
                                     help="URL of your Tableau Server or Cloud instance",
                                     key="server_url")
            site_content_url = st.text_input("Site Content URL", "",
                                           help="Leave empty for Default site or enter site content URL",
                                           key="site_url")
        
        with col2:
            auth_method = st.selectbox("Authentication Method", 
                                     ["PAT (Personal Access Token)", "Username & Password"],
                                     help="Choose your preferred authentication method",
                                     key="auth_method")
            
            if auth_method == "PAT (Personal Access Token)":
                token_name = st.text_input("PAT Name", help="Name of your Personal Access Token", key="pat_name")
                token_value = st.text_input("PAT Secret", type="password", help="Secret value of your PAT", key="pat_value")
                auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
            else:
                username = st.text_input("Username", help="Your Tableau username", key="username")
                password = st.text_input("Password", type="password", help="Your Tableau password", key="password")
                auth = TSC.TableauAuth(username, password, site_id=site_content_url)
        
        st.markdown("---")

    if mode == "📤 Export Content":
        try:
            with st.spinner("🔐 Connecting to Tableau Server..."):
                server = connect_to_tableau(auth, server_url)
            st.success("✅ Connection established successfully")
            
            st.markdown("""
            <div class="colored-header">
                <h2>Export Options</h2>
                <p>Select what you want to export from Tableau Server</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                with st.container():
                    st.markdown("### 👥 Users")
                    st.write("Export all users with their roles and details")
                    if st.button("Export Users", key="export_users"):
                        export_users(server)
            
            with col2:
                with st.container():
                    st.markdown("### 👪 Groups")
                    st.write("Export all groups with their IDs")
                    if st.button("Export Groups", key="export_groups"):
                        export_groups(server)
            
            with col3:
                with st.container():
                    st.markdown("### 📂 Projects")
                    st.write("Export all projects with descriptions")
                    if st.button("Export Projects", key="export_projects"):
                        export_projects(server)
            
            col4, col5, col6 = st.columns(3)
            
            with col4:
                with st.container():
                    st.markdown("### 📊 Workbooks")
                    st.write("Export workbook metadata")
                    if st.button("Export Workbooks", key="export_workbooks"):
                        export_workbooks(server)
            
            with col5:
                with st.container():
                    st.markdown("### 📈 Datasources")
                    st.write("Export datasource metadata")
                    if st.button("Export Datasources", key="export_datasources"):
                        export_datasources(server)
            
            with col6:
                with st.container():
                    st.markdown("### 🔄 Connection")
                    st.write("Refresh the server connection")
                    if st.button("Refresh Connection", key="refresh_connection"):
                        server.auth.sign_out()
                        st.experimental_rerun()
            
            server.auth.sign_out()
            st.info("🔒 Connection closed successfully")
        
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")

    elif mode == "📥 Import Users/Groups":
        st.markdown("""
        <div class="colored-header">
            <h2>Import Content</h2>
            <p>Upload your CSV files to import users or groups to Tableau Server</p>
        </div>
        """, unsafe_allow_html=True)
        
        import_type = st.radio(
            "Select Import Type",
            ["👥 Users", "👪 Groups"],
            horizontal=True,
            key="import_type"
        )
        
        uploaded_file = st.file_uploader(
            f"Upload {import_type.lower()} CSV file",
            type="csv",
            help="Ensure your CSV matches the required format",
            key="import_file"
        )
        
        if uploaded_file:
            st.success("✅ File uploaded successfully")
            df = pd.read_csv(uploaded_file)
            
            with st.expander("📋 Preview Data", expanded=True):
                st.dataframe(df.head())
            
            if st.button(f"🚀 Import {import_type}", type="primary", key="import_button"):
                try:
                    with st.spinner("🔄 Connecting to Tableau..."):
                        server = connect_to_tableau(auth, server_url)
                    st.success("✅ Connected to Tableau")

                    if import_type == "👥 Users":
                        for _, row in df.iterrows():
                            try:
                                new_user = TSC.UserItem(
                                    name=row.get('name'),
                                    site_role=row.get('site_role'),
                                    full_name=row.get('full_name'),
                                    email=row.get('email')
                                )
                                server.users.add(new_user)
                            except Exception as e:
                                st.warning(f"⚠️ Could not add user {row.get('name', 'unknown')}: {e}")
                        st.success("✅ All users imported!")
                    
                    elif import_type == "👪 Groups":
                        for _, row in df.iterrows():
                            try:
                                group_name = row.iloc[0]
                                if pd.notna(group_name):
                                    new_group = TSC.GroupItem(name=str(group_name))
                                    server.groups.create(new_group)
                            except Exception as e:
                                st.warning(f"⚠️ Could not create group {group_name if 'group_name' in locals() else 'unknown'}: {e}")
                        st.success("✅ All groups imported!")
                    
                    server.auth.sign_out()
                    st.info("🔐 Signed out successfully.")
                
                except Exception as e:
                    st.error(f"❌ Import failed: {str(e)}")

    elif mode == "🔄 Convert User Format":
        st.markdown("""
        <div class="colored-header">
            <h2>User Format Converter</h2>
            <p>Convert Excel user exports to Tableau-compatible CSV</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.info("""
        This tool converts Excel files exported from Tableau Server to the CSV format required for user imports.
        Upload your Excel file below to convert it.
        """)
        
        uploaded_file = st.file_uploader(
            "Upload Excel File",
            type=["xlsx", "xls"],
            help="Upload an Excel file exported from Tableau Server",
            key="convert_file"
        )
        
        if uploaded_file:
            st.success("✅ File uploaded successfully")
            df = pd.read_excel(uploaded_file)
            
            with st.expander("📋 Preview Original Data", expanded=True):
                st.dataframe(df.head())
            
            if st.button("🔃 Convert to CSV", type="primary", key="convert_button"):
                try:
                    transformed_data = []
                    
                    for _, row in df.iterrows():
                        email = row.get('Email', '')
                        site_role = row.get('Site Role', '')
                        
                        simplified_role = ''
                        fifth_column = 'None'
                        sixth_column = 'False'
                        
                        if 'SiteAdministratorCreator' in site_role:
                            simplified_role = 'Creator'
                            fifth_column = 'site'
                            sixth_column = 'True'
                        elif 'ExplorerCanPublish' in site_role:
                            simplified_role = 'Explorer'
                            sixth_column = 'True'
                        elif 'Viewer' in site_role:
                            simplified_role = 'Viewer'
                        elif 'SiteAdministratorExplorer' in site_role:
                            simplified_role = 'Explorer'
                            fifth_column = 'site'
                            sixth_column = 'True'
                        else:
                            simplified_role = site_role
                        
                        transformed_data.append([
                            email, '', '', simplified_role, fifth_column, sixth_column
                        ])
                    
                    csv_data = pd.DataFrame(transformed_data).to_csv(index=False, header=False)
                    
                    st.download_button(
                        label="⬇️ Download Converted CSV",
                        data=csv_data,
                        file_name="converted_users.csv",
                        mime="text/csv",
                        key="download_converted"
                    )
                    
                    st.success("✅ Conversion complete!")
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
    
    elif mode == "⬇️ Download Workbooks":
        download_workbooks(auth, server_url)

# ------------------------
# Run the App
# ------------------------
if __name__ == "__main__":
    main()
