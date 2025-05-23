import streamlit as st
import tableauserverclient as TSC
import os
import re

# --- Setup ---
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def sanitize_filename(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_download_path(project_name: str, workbook_name: str) -> str:
    base_folder = os.path.join(os.getcwd(), "source_files")
    project_folder = os.path.join(base_folder, sanitize_filename(project_name))
    os.makedirs(project_folder, exist_ok=True)
    return os.path.join(project_folder, f"{sanitize_filename(workbook_name)}.twbx")

def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

def download_workbooks(server_src, project_id, project_name):
    workbooks, _ = server_src.workbooks.get()
    selected_wbs = [wb for wb in workbooks if wb.project_id == project_id]
    if not selected_wbs:
        st.warning("No workbooks found in the selected source project.")
        return []

    downloaded_files = []
    for wb in selected_wbs:
        download_path = create_local_download_path(project_name, wb.name)
        st.info(f"Downloading '{wb.name}' to:\n{download_path}")
        server_src.workbooks.download(wb.id, filepath=download_path)
        if os.path.exists(download_path):
            downloaded_files.append((wb, download_path))
        else:
            st.error(f"❌ Failed to download: {wb.name}")
    return downloaded_files

def publish_workbooks(server_dest, files_and_workbooks, dest_project_id):
    for wb, filepath in files_and_workbooks:
        try:
            st.info(f"Publishing '{wb.name}'")
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            server_dest.workbooks.publish(new_wb, filepath, mode=TSC.Server.PublishMode.CreateNew)
            st.success(f"✅ Published '{wb.name}'")
        except Exception as e:
            st.error(f"❌ Failed to publish '{wb.name}': {e}")

# --- Streamlit Form ---
with st.form("migration_form"):
    st.subheader("🔐 Source Tableau")
    src_url = st.text_input("Source Server URL", "https://prod-apsoutheast-b.online.tableau.com")
    src_site = st.text_input("Source Site Content URL")
    src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"], key="src_auth")
    if src_auth_method == "PAT":
        src_token_name = st.text_input("Source PAT Name")
        src_token_secret = st.text_input("Source PAT Secret", type="password")
        src_username = src_password = None
    else:
        src_username = st.text_input("Source Username")
        src_password = st.text_input("Source Password", type="password")
        src_token_name = src_token_secret = None

    st.divider()

    st.subheader("🔐 Destination Tableau")
    dest_url = st.text_input("Destination Server URL")
    dest_site = st.text_input("Destination Site Content URL")
    dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")
    if dest_auth_method == "PAT":
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token_secret = st.text_input("Destination PAT Secret", type="password")
        dest_username = dest_password = None
    else:
        dest_username = st.text_input("Destination Username")
        dest_password = st.text_input("Destination Password", type="password")
        dest_token_name = dest_token_secret = None

    st.divider()

    st.subheader("📦 Project Mapping")
    source_proj = st.text_input("Source Project Name")
    dest_proj = st.text_input("Destination Project Name")

    submitted = st.form_submit_button("🚀 Start Migration")

# --- Logic ---
if submitted:
    try:
        # Connect source
        src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
        src_server = get_server(src_url)
        src_server.auth.sign_in(src_auth)

        # Find source project
        src_projects, _ = src_server.projects.get()
        src_proj_obj = next((p for p in src_projects if p.name == source_proj), None)
        if not src_proj_obj:
            st.error(f"❌ Source project '{source_proj}' not found.")
            st.stop()

        # Download to local machine
        downloaded_wbs = download_workbooks(src_server, src_proj_obj.id, source_proj)
        if not downloaded_wbs:
            st.warning("⚠️ No workbooks downloaded.")
            st.stop()

        src_server.auth.sign_out()

        # Connect destination
        dest_auth = get_auth(dest_auth_method, dest_token_name, dest_token_secret, dest_username, dest_password, dest_site)
        dest_server = get_server(dest_url)
        dest_server.auth.sign_in(dest_auth)

        # Find destination project
        dest_projects, _ = dest_server.projects.get()
        dest_proj_obj = next((p for p in dest_projects if p.name == dest_proj), None)
        if not dest_proj_obj:
            st.error(f"❌ Destination project '{dest_proj}' not found.")
            st.stop()

        # Publish from local folder
        publish_workbooks(dest_server, downloaded_wbs, dest_proj_obj.id)
        dest_server.auth.sign_out()

        st.success("🎉 Migration completed!")
        st.info(f"📁 Downloaded workbooks stored in:\n./source_files/{sanitize_filename(source_proj)}")

    except Exception as e:
        st.error(f"❌ Migration failed: {e}")
