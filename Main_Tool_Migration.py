import streamlit as st
import tableauserverclient as TSC
import os
import re
import pandas as pd

# Set Streamlit app page configuration
st.set_page_config(page_title="Tableau Super Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🛠️ Tableau Migration + Export/Import Utility</h1>", unsafe_allow_html=True)

# Create tabs for migration tool and export/import utility
tab1, tab2 = st.tabs(["🔁 Migration Tool", "📤 Export / 📥 Import Users & Groups"])

# ------------------------
# Shared Functions
# ------------------------

def sanitize(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

def to_csv_download(data: list, headers: list, filename: str, label: str):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

# ------------------------
# Tab 1: Migration Tool
# ------------------------

with tab1:
    st.markdown("## 🚀 Tableau Content Migration")
    
    def create_local_dirs(project_name):
        base = os.path.join(os.getcwd(), "tableau_migration")
        src = os.path.join(base, "source", sanitize(project_name))
        dest = os.path.join(base, "destination", sanitize(project_name))
        os.makedirs(src, exist_ok=True)
        os.makedirs(dest, exist_ok=True)
        return src, dest

    def get_local_path(type_: str, project_name: str, content_name: str, ext=".twbx") -> str:
        path = os.path.join(os.getcwd(), "tableau_migration", type_, sanitize(project_name))
        return os.path.join(path, f"{sanitize(content_name)}{ext}")

    def copy_tableau_content(src, dest, content_name):
        os.rename(src, dest)
        st.success(f"✅ Successfully moved {content_name} from source to destination.")

    def get_content_from_server(server, content_type, project_name):
        if content_type == "workbook":
            return server.workbooks.get(project_name=project_name)
        elif content_type == "datasource":
            return server.datasources.get(project_name=project_name)
        elif content_type == "project":
            return server.projects.get()
        else:
            return []

    def download_tableau_content(server, content_type, content_name, project_name):
        src, dest = create_local_dirs(project_name)
        content_items = get_content_from_server(server, content_type, project_name)
        for item in content_items:
            if content_type == "workbook":
                file_path = get_local_path("source", project_name, item.name, ".twbx")
                server.workbooks.download(item.id, file_path)
                copy_tableau_content(file_path, dest, item.name)
            elif content_type == "datasource":
                file_path = get_local_path("source", project_name, item.name, ".tdsx")
                server.datasources.download(item.id, file_path)
                copy_tableau_content(file_path, dest, item.name)

    def run_migration(auth, source_server_url, dest_server_url, project_name):
        try:
            with st.spinner("🔄 Connecting to source Tableau Server..."):
                source_server = get_server(source_server_url)
                source_server.auth.sign_in(auth)

            st.success("✅ Connected to source Tableau Server!")

            with st.spinner("🔄 Connecting to destination Tableau Server..."):
                dest_server = get_server(dest_server_url)
                dest_server.auth.sign_in(auth)

            st.success("✅ Connected to destination Tableau Server!")

            # Migrate content (workbooks, datasources, etc.)
            content_type = st.selectbox("Select content to migrate", ["workbook", "datasource", "project"])
            download_tableau_content(source_server, content_type, project_name, project_name)

            st.success("✅ Migration completed successfully!")
        except Exception as e:
            st.error(f"❌ Migration failed: {str(e)}")

    # UI for Migration Tool
    st.subheader("⚙️ Migration Settings")
    source_server_url = st.text_input("Source Tableau Server URL", "https://source-tableau-server.com")
    dest_server_url = st.text_input("Destination Tableau Server URL", "https://dest-tableau-server.com")
    
    auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])
    project_name = st.text_input("Project Name")
    
    if auth_method == "PAT (Personal Access Token)":
        token_name = st.text_input("PAT Token Name")
        token_value = st.text_input("PAT Token Value", type="password")
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
    
    if st.button("🔄 Migrate Content"):
        if auth_method == "PAT (Personal Access Token)":
            auth = TSC.PersonalAccessTokenAuth(token_name, token_value)
            run_migration(auth, source_server_url, dest_server_url, project_name)
        else:
            auth = TSC.TableauAuth(username, password)
            run_migration(auth, source_server_url, dest_server_url, project_name)

# ------------------------
# Tab 2: Export/Import Tool
# ------------------------

with tab2:
    st.markdown("## 🌍 Tableau Export & Import Utility")

    mode = st.radio("📁 Select Mode", ["Export Tableau Content", "Import Users & Groups"])

    server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
    site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")
    auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

    def connect_to_tableau(auth):
        server = TSC.Server(server_url, use_server_version=True)
        server.auth.sign_in(auth)
        return server

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
                        row_dict = row.to_dict()
                        server.users.create(row_dict)
                        st.success(f"✅ User {row['Name']} created.")
                    except Exception as e:
                        st.error(f"❌ Failed to import user {row['Name']}: {str(e)}")
            elif import_type == "Groups":
                for _, row in df.iterrows():
                    try:
                        row_dict = row.to_dict()
                        server.groups.create(row_dict)
                        st.success(f"✅ Group {row['Group Name']} created.")
                    except Exception as e:
                        st.error(f"❌ Failed to import group {row['Group Name']}: {str(e)}")
            server.auth.sign_out()
            st.info("🔐 Signed out successfully.")
        except Exception as e:
            st.error(f"❌ Import failed: {str(e)}")

    # UI for Export / Import
    if auth_method == "PAT (Personal Access Token)":
        token_name = st.text_input("PAT Token Name")
        token_value = st.text_input("PAT Token Value", type="password")
        auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        auth = TSC.TableauAuth(username, password, site_id=site_content_url)

    if mode == "Export Tableau Content":
        if st.button("📥 Export"):
            run_export(auth)
    elif mode == "Import Users & Groups":
        import_type = st.selectbox("Select type to import", ["Users", "Groups"])
        uploaded_file = st.file_uploader("Upload CSV file", type="csv")
        if st.button("🔄 Import"):
            run_import(import_type, uploaded_file, auth)
