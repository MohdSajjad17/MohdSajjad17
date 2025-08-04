import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
from io import BytesIO

# ------------------------
# Custom CSS Styling
# ------------------------
def inject_css():
    st.markdown("""
    <style>
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
            border-left: 5px solid #4B8BBE;
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

def connect_to_tableau(auth, server_url):
    server = TSC.Server(server_url, use_server_version=True)
    server.auth.sign_in(auth)
    return server

# ------------------------
# Export Functions
# ------------------------
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
# Download Workbook Functions
# ------------------------
def download_workbooks(auth, server_url):
    """Enhanced workbook download function with better UX and error handling"""
    try:
        # Connection section
        with st.spinner("🔄 Establishing secure connection to Tableau Server..."):
            server = connect_to_tableau(auth, server_url)
            st.toast("✅ Connection established successfully!", icon="✅")
        
        # Display connection info in expander
        with st.expander("ℹ️ Connection Details", expanded=False):
            st.write(f"Connected to: {server.server_address}")
            st.write(f"Site: {auth.site_id or 'Default'}")
            st.write(f"User: {getattr(auth, 'username', 'PAT User')}")

        # Download options section
        st.markdown("### 📥 Download Options")
        download_option = st.radio(
            "Select download scope:",
            ["Download all workbooks from a project", 
             "Download specific workbook",
             "Search and download workbooks"],
            horizontal=True,
            help="Choose whether to download all workbooks from a project or select specific ones"
        )

        # Get projects with progress indicator
        with st.spinner("🔍 Loading available projects..."):
            projects, _ = server.projects.get()
            if not projects:
                st.error("No projects found on this site!")
                return
            
            project_names = [p.name for p in projects]
            selected_project = st.selectbox(
                "Select project:",
                project_names,
                help="Select the project containing the workbooks you want to download"
            )

        # Main download logic
        if download_option == "Download all workbooks from a project":
            _download_all_workbooks(server, selected_project)
            
        elif download_option == "Download specific workbook":
            _download_single_workbook(server, selected_project)
            
        else:  # Search and download workbooks
            _search_and_download_workbooks(server, selected_project)

        # Clean up
        server.auth.sign_out()
        st.toast("🔐 Session ended successfully", icon="🔒")

    except TSC.ServerResponseError as e:
        st.error(f"❌ Tableau Server error: {str(e)}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")

def _download_all_workbooks(server, project_name):
    """Helper function to download all workbooks from a project"""
    with st.spinner(f"🔍 Scanning project '{project_name}' for workbooks..."):
        workbooks, _ = server.workbooks.get()
        project_workbooks = [w for w in workbooks if w.project_name == project_name]
        
        if not project_workbooks:
            st.warning(f"⚠️ No workbooks found in project '{project_name}'")
            return
        
        st.success(f"Found {len(project_workbooks)} workbooks in '{project_name}'")
        
        # Progress bar for multiple downloads
        progress_bar = st.progress(0)
        total = len(project_workbooks)
        
        for i, wb in enumerate(project_workbooks):
            try:
                progress_bar.progress((i + 1) / total, text=f"Downloading {wb.name}...")
                
                with st.spinner(f"⏳ Downloading '{wb.name}'..."):
                    workbook_path = server.workbooks.download(wb.id)
                    
                    with open(workbook_path, 'rb') as f:
                        workbook_data = f.read()
                    
                    # Create download button with additional info
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
                                key=f"dl_{wb.id}",
                                help=f"Download {wb.name}"
                            )
                    
                    os.remove(workbook_path)
                    
            except Exception as e:
                st.error(f"Failed to download '{wb.name}': {str(e)}")
                continue
        
        progress_bar.empty()
        st.toast(f"🎉 Downloaded {len(project_workbooks)} workbooks!", icon="🎉")

def _download_single_workbook(server, project_name):
    """Helper function to download a specific workbook"""
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
            help="Select the specific workbook you want to download"
        )
        
        workbook = next(w for w in project_workbooks if w.name == selected_workbook)
        
        # Show workbook metadata
        with st.expander("📊 Workbook Details"):
            st.write(f"**Name:** {workbook.name}")
            st.write(f"**Owner:** {workbook.owner_id}")
            st.write(f"**Created:** {workbook.created_at}")
            st.write(f"**Last Updated:** {workbook.updated_at}")
            st.write(f"**Size:** {getattr(workbook, 'size', 'N/A')}")
        
        if st.button("🚀 Download Workbook", type="primary"):
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
    """Helper function for search and download functionality"""
    st.markdown("### 🔍 Search Workbooks")
    
    search_query = st.text_input(
        "Search by workbook name:",
        help="Enter part of the workbook name to filter results"
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
        
        # Display workbook list with checkboxes
        selected_workbooks = []
        for wb in project_workbooks:
            if st.checkbox(
                f"{wb.name} (Updated: {wb.updated_at})",
                key=f"wb_{wb.id}"
            ):
                selected_workbooks.append(wb)
        
        if selected_workbooks and st.button(
            f"📥 Download {len(selected_workbooks)} Selected Workbooks",
            type="primary"
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
def main():
    # App Header
    st.markdown("""
    <div class="main-header">
        <div class="title-section">
            <h1>Tableau Migration Toolkit</h1>
            <p class="subtitle">Streamline your Tableau content migration with powerful automation</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    # Sidebar Navigation
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>Navigation</h2>
        </div>
        """, unsafe_allow_html=True)
        
        mode = st.radio(
            "Select Operation",
            ["📤 Export Content", 
             "📥 Import Users/Groups", 
             "🔄 Convert User Format",
             "⬇️ Download Workbooks",
             "⬆️ Upload Workbooks"],
            key="nav_mode"
        )
        
        st.markdown("---")
        
        st.markdown("""
        <div class="sidebar-footer">
            <p class="version">Version 2.0</p>
            <p class="author">Developed by MS</p>
        </div>
        """, unsafe_allow_html=True)

    # Connection Manager (for modes that need Tableau connection)
    if mode in ["📤 Export Content", "📥 Import Users/Groups", "⬇️ Download Workbooks", "⬆️ Upload Workbooks"]:
        st.markdown("""
        <div class="colored-header">
            <h2>Tableau Server Connection</h2>
            <p>Provide your Tableau Server/Cloud credentials</p>
        </div>
        """, unsafe_allow_html=True)
        
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

    # Mode Handling
    if mode == "📤 Export Content":
        try:
            with st.spinner("🔐 Connecting to Tableau Server..."):
                server = connect_to_tableau(auth, server_url)
            st.success("✅ Connection established successfully")
            
            st.markdown("""
            <div class="colored-header">
                <h2>Export Options</h2>
                <p>Select what you want to export</p>
            </div>
            """, unsafe_allow_html=True)
            
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

    elif mode == "📥 Import Users/Groups":
        st.markdown("""
        <div class="colored-header">
            <h2>Import Content</h2>
            <p>Upload your CSV files to import users or groups</p>
        </div>
        """, unsafe_allow_html=True)
        
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
                                group_name = row.iloc[0]  # Get first column value as group name
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
            help="Upload an Excel file exported from Tableau Server"
        )
        
        if uploaded_file:
            st.success("✅ File uploaded successfully")
            df = pd.read_excel(uploaded_file)
            
            with st.expander("📋 Preview Original Data"):
                st.dataframe(df.head())
            
            if st.button("🔃 Convert to CSV", type="primary"):
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
                        mime="text/csv"
                    )
                    
                    st.success("✅ Conversion complete!")
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
    
    elif mode == "⬇️ Download Workbooks":
        download_workbooks(auth, server_url)
        
    elif mode == "⬆️ Upload Workbooks":
        st.markdown("""
        <div class="colored-header">
            <h2>Workbook Upload</h2>
            <p>Upload workbooks to Tableau Server</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.warning("⚠️ Workbook upload functionality is not yet implemented")
        st.info("This feature will be available in the next version")

# ------------------------
# Run the App
# ------------------------
if __name__ == "__main__":
    main()
