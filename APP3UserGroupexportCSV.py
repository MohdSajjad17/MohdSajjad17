import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
from io import BytesIO

# ------------------------
# App Header
# ------------------------
st.set_page_config(page_title="Tableau Export/Import Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World CLT</h1>", unsafe_allow_html=True)
st.markdown("#### 🔐 Connect to Tableau Server / Cloud to Export or Import Content")
st.markdown("---")

# ------------------------
# Mode Selection
# ------------------------
mode = st.radio("📁 Select Mode", [
    "Export Tableau Content", 
    "Import Users & Groups", 
    "Convert User Excel to User CSV",
    "Download Workbooks",
    "Upload Workbooks"
])
st.markdown("---")

# ------------------------
# Connection Details (Only show for modes that need Tableau connection)
# ------------------------
if mode in ["Export Tableau Content", "Import Users & Groups", "Download Workbooks", "Upload Workbooks"]:
    st.subheader("🖥️ Tableau Connection Details")
    server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
    site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")
    auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])
    st.markdown("---")

# ------------------------
# Helper Functions
# ------------------------
def to_csv_download(data: list, headers: list, filename: str, label: str):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

def connect_to_tableau(auth):
    server = TSC.Server(server_url, use_server_version=True)
    server.auth.sign_in(auth)
    return server

def get_tableau_auth():
    if auth_method == "PAT (Personal Access Token)":
        token_name = st.text_input("PAT Name")
        token_value = st.text_input("PAT Secret", type="password")
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        return TSC.TableauAuth(username, password, site_id=site_content_url)

# ------------------------
# Export Functions
# ------------------------
def export_users(server):
    users, _ = server.users.get()
    data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
    headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
    to_csv_download(data, headers, "users.csv", "⬇️ Download Users")

def export_groups(server):
    groups, _ = server.groups.get()
    data = [[g.name, g.id] for g in groups]
    headers = ["Group Name", "Group ID"]
    to_csv_download(data, headers, "groups.csv", "⬇️ Download Groups")

def export_projects(server):
    projects, _ = server.projects.get()
    data = [[p.name, p.description, p.content_permissions] for p in projects]
    headers = ["Name", "Description", "Content Permissions"]
    to_csv_download(data, headers, "projects.csv", "⬇️ Download Projects")

def export_workbooks(server):
    workbooks, _ = server.workbooks.get()
    data = [[w.name, w.owner_id, w.project_name, w.created_at, w.updated_at] for w in workbooks]
    headers = ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_csv_download(data, headers, "workbooks.csv", "⬇️ Download Workbooks")

def export_datasources(server):
    datasources, _ = server.datasources.get()
    data = [[d.name, d.owner_id, d.project_name, d.created_at, d.updated_at] for d in datasources]
    headers = ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_csv_download(data, headers, "datasources.csv", "⬇️ Download Datasources")

# ------------------------
# Export Mode Logic
# ------------------------
def run_export(auth):
    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected successfully!")

        with st.expander("📋 Export Tableau Content (click to expand)"):
            export_users(server)
            export_groups(server)
            export_projects(server)
            export_workbooks(server)
            export_datasources(server)

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")

# ------------------------
# Import Mode Logic
# ------------------------
def run_import(import_type, uploaded_file, auth):
    if not uploaded_file:
        st.warning("⚠️ Please upload a CSV file before importing.")
        return

    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected to Tableau")

        df = pd.read_csv(uploaded_file)
        st.write("📄 CSV Preview:", df.head())

        if import_type == "Users":
            for _, row in df.iterrows():
                try:
                    row_dict = row.dropna().to_dict()
                    user_kwargs = {}
                    valid_keys = {
                        "name", "site_role", "full_name", "email",
                        "auth_setting", "external_auth_user_id", "locale",
                        "password", "password_never_expires", "must_change_password",
                        "content_admin", "server_role", "tags"
                    }

                    for k, v in row_dict.items():
                        key_lower = k.lower()
                        if key_lower in valid_keys:
                            user_kwargs[key_lower] = v

                    if "name" not in user_kwargs or "site_role" not in user_kwargs:
                        st.warning(f"Skipping row because 'name' or 'site_role' missing: {row_dict}")
                        continue

                    new_user = TSC.UserItem(
                        name=user_kwargs.get("name"),
                        site_role=user_kwargs.get("site_role"),
                        full_name=user_kwargs.get("full_name"),
                        email=user_kwargs.get("email"),
                        auth_setting=user_kwargs.get("auth_setting"),
                        external_auth_user_id=user_kwargs.get("external_auth_user_id"),
                        locale=user_kwargs.get("locale"),
                        password=user_kwargs.get("password"),
                        password_never_expires=user_kwargs.get("password_never_expires"),
                        must_change_password=user_kwargs.get("must_change_password"),
                        content_admin=user_kwargs.get("content_admin"),
                        server_role=user_kwargs.get("server_role"),
                        tags=user_kwargs.get("tags"),
                    )
                    server.users.add(new_user)

                except Exception as e:
                    st.warning(f"⚠️ Could not add user {row.get('name', 'unknown')}: {e}")

            st.success("✅ All users imported!")

        elif import_type == "Groups":
            for _, row in df.iterrows():
                try:
                    row_dict = row.dropna().to_dict()
                    group_name = None
                    for val in row_dict.values():
                        if isinstance(val, str) and val.strip():
                            group_name = val.strip()
                            break

                    if not group_name:
                        st.warning(f"Skipping row with no valid group name: {row_dict}")
                        continue

                    new_group = TSC.GroupItem(name=group_name)
                    server.groups.create(new_group)

                except Exception as e:
                    st.warning(f"⚠️ Could not create group {group_name if group_name else 'unknown'}: {e}")

            st.success("✅ All groups imported!")

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")

    except Exception as e:
        st.error(f"❌ Import failed: {str(e)}")

# ------------------------
# Excel to CSV Conversion Logic
# ------------------------
def convert_excel_to_csv(uploaded_file):
    if not uploaded_file:
        st.warning("⚠️ Please upload an Excel file first.")
        return
    
    try:
        df = pd.read_excel(uploaded_file)
        st.write("📄 Excel Preview:", df.head())
        
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

# ------------------------
# Download Workbooks Logic
# ------------------------
def download_workbooks(auth):
    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected successfully!")

        download_option = st.radio(
            "Select Download Option",
            ["Download All Workbooks from a Project", "Download Specific Workbook"]
        )

        projects, _ = server.projects.get()
        project_names = [p.name for p in projects]
        selected_project = st.selectbox("Select Project", project_names)

        if download_option == "Download All Workbooks from a Project":
            with st.spinner(f"🔄 Getting workbooks from project {selected_project}..."):
                workbooks, _ = server.workbooks.get()
                project_workbooks = [w for w in workbooks if w.project_name == selected_project]
            
            if not project_workbooks:
                st.warning(f"No workbooks found in project '{selected_project}'")
                return

            st.success(f"Found {len(project_workbooks)} workbooks in project '{selected_project}'")
            
            for wb in project_workbooks:
                try:
                    workbook_path = server.workbooks.download(wb.id)
                    with open(workbook_path, 'rb') as f:
                        workbook_data = f.read()
                    
                    st.download_button(
                        label=f"⬇️ Download {wb.name}",
                        data=workbook_data,
                        file_name=f"{wb.name}.twbx",
                        mime="application/octet-stream"
                    )
                    os.remove(workbook_path)
                except Exception as e:
                    st.error(f"Failed to download {wb.name}: {str(e)}")

        else:  # Download Specific Workbook
            workbooks, _ = server.workbooks.get()
            project_workbooks = [w for w in workbooks if w.project_name == selected_project]
            
            if not project_workbooks:
                st.warning(f"No workbooks found in project '{selected_project}'")
                return

            workbook_names = [w.name for w in project_workbooks]
            selected_workbook = st.selectbox("Select Workbook", workbook_names)
            
            with st.spinner(f"🔄 Downloading {selected_workbook}..."):
                workbook = next(w for w in project_workbooks if w.name == selected_workbook)
                workbook_path = server.workbooks.download(workbook.id)
                
                with open(workbook_path, 'rb') as f:
                    workbook_data = f.read()
                
                st.download_button(
                    label=f"⬇️ Download {selected_workbook}",
                    data=workbook_data,
                    file_name=f"{selected_workbook}.twbx",
                    mime="application/octet-stream"
                )
                os.remove(workbook_path)

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")

    except Exception as e:
        st.error(f"❌ Download failed: {str(e)}")

# ------------------------
# Upload Workbooks Logic
# ------------------------
def upload_workbooks(auth):
    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected successfully!")

        # Get list of projects
        projects, _ = server.projects.get()
        project_names = [p.name for p in projects]
        
        # Upload options
        upload_option = st.radio(
            "Upload Option",
            ["Upload to Existing Project", "Create New Project and Upload"]
        )

        if upload_option == "Upload to Existing Project":
            selected_project = st.selectbox("Select Project", project_names)
            project_id = next(p.id for p in projects if p.name == selected_project)
        else:
            new_project_name = st.text_input("New Project Name")
            project_id = None

        uploaded_files = st.file_uploader(
            "📤 Upload Workbook Files (.twbx or .twb)",
            type=["twbx", "twb"],
            accept_multiple_files=True
        )

        if uploaded_files and st.button("🚀 Upload Workbooks"):
            if upload_option == "Create New Project and Upload":
                if not new_project_name:
                    st.error("Please enter a project name")
                    return
                
                new_project = TSC.ProjectItem(name=new_project_name)
                project = server.projects.create(new_project)
                project_id = project.id
                st.success(f"Created new project: {new_project_name}")

            for uploaded_file in uploaded_files:
                try:
                    file_name = uploaded_file.name
                    file_content = uploaded_file.read()
                    
                    # Create a temporary file
                    temp_path = f"temp_{file_name}"
                    with open(temp_path, 'wb') as f:
                        f.write(file_content)
                    
                    # Upload to server
                    new_workbook = TSC.WorkbookItem(project_id=project_id, name=os.path.splitext(file_name)[0])
                    new_workbook = server.workbooks.publish(
                        new_workbook,
                        temp_path,
                        'Overwrite'
                    )
                    
                    os.remove(temp_path)
                    st.success(f"✅ Successfully uploaded: {file_name}")
                
                except Exception as e:
                    st.error(f"❌ Failed to upload {file_name}: {str(e)}")

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")

    except Exception as e:
        st.error(f"❌ Upload failed: {str(e)}")

# ------------------------
# Mode Handling
# ------------------------
if mode == "Export Tableau Content":
    auth = get_tableau_auth()
    if st.button("🔌 Export with Selected Authentication"):
        run_export(auth)

elif mode == "Import Users & Groups":
    st.subheader("📥 Select What to Import")
    import_type = st.selectbox("Import Type", ["Users", "Groups"])

    if import_type == "Users":
        uploaded_file = st.file_uploader("📤 Upload Users CSV (any format with needed columns)", type="csv")
    else:
        uploaded_file = st.file_uploader("📤 Upload Groups CSV (any format with group names)", type="csv")

    st.markdown("---")
    st.subheader("🔐 Tableau Credentials")
    
    auth = get_tableau_auth()
    if st.button("🚀 Import Now"):
        run_import(import_type, uploaded_file, auth)

elif mode == "Convert User Excel to User CSV":
    st.subheader("🔄 Convert User Excel to User CSV")
    st.markdown("Upload an Excel file exported from Tableau to convert it to the required CSV format.")
    
    uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx", "xls"])
    
    if st.button("🔃 Convert Now"):
        convert_excel_to_csv(uploaded_file)

elif mode == "Download Workbooks":
    st.subheader("📥 Download Workbooks from Tableau Server")
    st.markdown("Download workbooks from your Tableau Server/Cloud")
    
    auth = get_tableau_auth()
    if st.button("🔍 Connect and Browse Workbooks"):
        download_workbooks(auth)

elif mode == "Upload Workbooks":
    st.subheader("📤 Upload Workbooks to Tableau Server")
    st.markdown("Upload workbooks from your local machine to Tableau Server/Cloud")
    
    auth = get_tableau_auth()
    if st.button("🔍 Connect and Prepare Upload"):
        upload_workbooks(auth)

# ------------------------
# Footer
# ------------------------
st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        bottom: 0;
        width: 100%;
        background-color: #f1f1f1;
        color: #333;
        text-align: center;
        padding: 10px;
    }
    </style>
    <div class="footer">
        Developed with ❤️ by <strong>Mohd Sajjad</strong>
    </div>
    """,
    unsafe_allow_html=True
)
