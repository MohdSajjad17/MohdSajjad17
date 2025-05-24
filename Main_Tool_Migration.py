import streamlit as st
import tableauserverclient as TSC
import os
import re
import pandas as pd

# ------------------------
# Streamlit Page Config
# ------------------------
st.set_page_config(page_title="Tableau Management Tool", layout="wide")

st.markdown("""
    <h1 style='text-align: center; color: #4B8BBE;'>🌐 Tableau Utility Portal</h1>
    <p style='text-align: center;'>Switch between Migration Tool and Export/Import Tool using tabs below</p>
    <hr style="border: 1px solid #4B8BBE;">
""", unsafe_allow_html=True)

# ------------------------
# Tabs
# ------------------------
tab1, tab2 = st.tabs(["🔁 Migration Tool", "📁 Export / Import Tool"])

# ------------------------
# MIGRATION TOOL TAB
# ------------------------
with tab1:
    def sanitize(name):
        return re.sub(r'[^\w\-_\. ]', '_', name)

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

    def get_auth(method, token_name, token_value, username, password, site):
        if method == "PAT":
            return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
        else:
            return TSC.TableauAuth(username, password, site_id=site)

    def get_server(url):
        return TSC.Server(url, use_server_version=True)

    def migrate_permissions(src_server, src_item, dest_server, dest_item, item_type="workbook"):
        # identical to Code 1 implementation — omitted here for brevity
        pass

    def download_workbooks(server, project_id, project_name):
        # identical to Code 1 — omitted
        pass

    def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id, project_name):
        # identical to Code 1 — omitted
        pass

    def download_datasources(server, project_id, project_name):
        # identical to Code 1 — omitted
        pass

    def publish_datasources(dest_server, files_and_ds, dest_project_id):
        # identical to Code 1 — omitted
        pass

    def download_flows(server, project_id, project_name):
        # identical to Code 1 — omitted
        pass

    def publish_flows(dest_server, files_and_flows, dest_project_id):
        # identical to Code 1 — omitted
        pass

    def get_or_create_project(server, project_name):
        # identical to Code 1 — omitted
        pass

    with st.form("migration_form"):
        st.subheader("🔐 Source Tableau")
        src_url = st.text_input("Source Server URL")
        src_site = st.text_input("Source Site Content URL (leave blank for default site)")
        src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"], key="src_auth")
        if src_auth_method == "PAT":
            src_token_name = st.text_input("Source PAT Name")
            src_token_secret = st.text_input("Source PAT Secret", type="password")
            src_username = src_password = None
        else:
            src_username = st.text_input("Source Username")
            src_password = st.text_input("Source Password", type="password")
            src_token_name = src_token_secret = None

        st.subheader("🔐 Destination Tableau")
        dest_url = st.text_input("Destination Server URL")
        dest_site = st.text_input("Destination Site Content URL (leave blank for default site)")
        dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")
        if dest_auth_method == "PAT":
            dest_token_name = st.text_input("Destination PAT Name")
            dest_token_secret = st.text_input("Destination PAT Secret", type="password")
            dest_username = dest_password = None
        else:
            dest_username = st.text_input("Destination Username")
            dest_password = st.text_input("Destination Password", type="password")
            dest_token_name = dest_token_secret = None

        st.subheader("📁 Project Mapping")
        source_proj = st.text_input("Source Project Name")
        dest_proj = st.text_input("Destination Project Name")

        st.subheader("📦 Content Types to Migrate")
        content_types = st.multiselect(
            "Select content types to migrate",
            ["Workbooks", "Datasources", "Flows"],
            default=["Workbooks"]
        )

        submitted = st.form_submit_button("🚀 Start Migration")

    if submitted:
        st.info("🔄 Migration logic will execute here...")
        # Place migration logic here (from Code 1)
        pass

# ------------------------
# EXPORT/IMPORT TOOL TAB
# ------------------------
with tab2:
    mode = st.radio("📁 Select Mode", ["Export Tableau Content", "Import Users & Groups"])
    server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
    site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")
    auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

    def to_csv_download(data: list, headers: list, filename: str, label: str):
        df = pd.DataFrame(data, columns=headers)
        csv = df.to_csv(index=False)
        st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

    def connect_to_tableau(auth):
        server = TSC.Server(server_url, use_server_version=True)
        server.auth.sign_in(auth)
        return server

    def export_users(server):
        users, _ = server.users.get()
        data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
        to_csv_download(data, ["Name", "Full Name", "Email", "Site Role", "Last Login"], "users.csv", "⬇️ Download Users")

    def export_groups(server):
        groups, _ = server.groups.get()
        data = [[g.name, g.id] for g in groups]
        to_csv_download(data, ["Group Name", "Group ID"], "groups.csv", "⬇️ Download Groups")

    def export_projects(server):
        projects, _ = server.projects.get()
        data = [[p.name, p.description, p.content_permissions] for p in projects]
        to_csv_download(data, ["Name", "Description", "Content Permissions"], "projects.csv", "⬇️ Download Projects")

    def export_workbooks(server):
        workbooks, _ = server.workbooks.get()
        data = [[w.name, w.owner_id, w.project_name, w.created_at, w.updated_at] for w in workbooks]
        to_csv_download(data, ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"], "workbooks.csv", "⬇️ Download Workbooks")

    def export_datasources(server):
        datasources, _ = server.datasources.get()
        data = [[d.name, d.owner_id, d.project_name, d.created_at, d.updated_at] for d in datasources]
        to_csv_download(data, ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"], "datasources.csv", "⬇️ Download Datasources")

    def run_export(auth):
        try:
            server = connect_to_tableau(auth)
            st.success("✅ Connected successfully!")
            with st.expander("📋 Export Tableau Content"):
                export_users(server)
                export_groups(server)
                export_projects(server)
                export_workbooks(server)
                export_datasources(server)
            server.auth.sign_out()
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")

    def run_import(import_type, uploaded_file, auth):
        # Use original Code 2 import_users & import_groups logic here
        st.warning("🚧 Import logic placeholder")

    if mode == "Export Tableau Content":
        if auth_method == "PAT (Personal Access Token)":
            token_name = st.text_input("PAT Name")
            token_value = st.text_input("PAT Secret", type="password")
            if st.button("🔌 Export with PAT"):
                auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
                run_export(auth)
        else:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("🔌 Export with Username & Password"):
                auth = TSC.TableauAuth(username, password, site_id=site_content_url)
                run_export(auth)

    elif mode == "Import Users & Groups":
        st.subheader("📥 Select What to Import")
        import_type = st.selectbox("Import Type", ["Users", "Groups"])
        uploaded_file = st.file_uploader("📤 Upload CSV", type="csv")

        if auth_method == "PAT (Personal Access Token)":
            token_name = st.text_input("PAT Name")
            token_value = st.text_input("PAT Secret", type="password")
            if st.button("🚀 Import Now"):
                auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
                run_import(import_type, uploaded_file, auth)
        else:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("🚀 Import Now"):
                auth = TSC.TableauAuth(username, password, site_id=site_content_url)
                run_import(import_type, uploaded_file, auth)

# ------------------------
# Footer
# ------------------------
st.markdown("""
    <div style="text-align: center; margin-top: 20px; font-size: 16px; color: gray;">
        Developed by <strong>Mohd Sajjad</strong> • 2025
    </div>
""", unsafe_allow_html=True)
