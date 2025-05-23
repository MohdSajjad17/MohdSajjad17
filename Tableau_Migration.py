import streamlit as st
import tableauserverclient as TSC
import os
import re

# ---------------------------- Page Setup ----------------------------
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)

# ---------------------------- Helper Functions ----------------------------
def sanitize(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
    base = os.path.join(os.getcwd(), "tableau_migration")
    src = os.path.join(base, "source", sanitize(project_name))
    dest = os.path.join(base, "destination", sanitize(project_name))
    os.makedirs(src, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    return src, dest

def get_local_path(type_: str, project_name: str, workbook_name: str) -> str:
    path = os.path.join(os.getcwd(), "tableau_migration", type_, sanitize(project_name))
    return os.path.join(path, f"{sanitize(workbook_name)}.twbx")

def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

def download_workbooks(server, project_id, project_name):
    workbooks, _ = server.workbooks.get()
    selected = [wb for wb in workbooks if wb.project_id == project_id]
    files = []
    for wb in selected:
        path = get_local_path("source", project_name, wb.name)
        st.info(f"⬇️ Downloading: {wb.name}")
        try:
            file_path = server.workbooks.download(wb.id, filepath=path)
            if os.path.exists(file_path):
                files.append((wb, file_path))
                st.success(f"✅ Downloaded: {wb.name}")
            else:
                st.error(f"❌ File not saved correctly: {wb.name}")
        except Exception as e:
            st.error(f"❌ Download failed for {wb.name}: {e}")
    return files

def migrate_permissions(src_server, src_wb, dest_server, dest_wb):
    try:
        # Populate permissions first
        src_server.workbooks.populate_permissions(src_wb)
        dest_server.workbooks.populate_permissions(dest_wb)

        # Access the populated permissions
        src_permissions = src_wb.permissions
        dest_permissions = dest_wb.permissions

        # Clear existing destination permissions
        for perm in dest_permissions:
            dest_server.workbooks._permissions.delete(dest_wb, perm)

        # Add permissions from source
        for perm in src_permissions:
            new_perm = TSC.PermissionsRule(grantee=perm.grantee, capabilities=perm.capabilities)
            dest_server.workbooks._permissions.add(dest_wb, new_perm)

        st.success(f"🔑 Permissions migrated for workbook: {src_wb.name}")
    except Exception as e:
        st.error(f"❌ Failed to migrate permissions for {src_wb.name}: {e}")

def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id):
    for wb, path in files_and_wbs:
        st.info(f"⬆️ Publishing: {wb.name}")
        try:
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            published_wb = dest_server.workbooks.publish(
                new_wb, path, mode=TSC.Server.PublishMode.Overwrite
            )
            st.success(f"✅ Published: {wb.name}")
            migrate_permissions(src_server, wb, dest_server, published_wb)
        except Exception as e:
            st.error(f"❌ Failed to publish {wb.name}: {e}")

# ---------------------------- Streamlit UI ----------------------------
with st.form("migration_form"):
    st.subheader("🔐 Source Tableau")
    src_url = st.text_input("Source Server URL")
    src_site = st.text_input("Source Site Content URL (leave blank for default site)")
    src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"])
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
    dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"])
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

    submitted = st.form_submit_button("🚀 Start Migration")

# ---------------------------- Migration Logic ----------------------------
if submitted:
    try:
        src_dir, dest_dir = create_local_dirs(source_proj)
        st.success(f"📂 Local folders created:\n- {src_dir}\n- {dest_dir}")

        src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
        src_server = get_server(src_url)
        src_server.auth.sign_in(src_auth)

        src_proj_obj = next((p for p in src_server.projects.get()[0] if p.name == source_proj), None)
        if not src_proj_obj:
            st.error(f"❌ Source project '{source_proj}' not found.")
            src_server.auth.sign_out()
            st.stop()

        files_and_wbs = download_workbooks(src_server, src_proj_obj.id, source_proj)
        if not files_and_wbs:
            st.warning("⚠️ No workbooks downloaded.")
            src_server.auth.sign_out()
            st.stop()

        dest_auth = get_auth(dest_auth_method, dest_token_name, dest_token_secret, dest_username, dest_password, dest_site)
        dest_server = get_server(dest_url)
        dest_server.auth.sign_in(dest_auth)

        dest_proj_obj = next((p for p in dest_server.projects.get()[0] if p.name == dest_proj), None)
        if not dest_proj_obj:
            st.error(f"❌ Destination project '{dest_proj}' not found.")
            src_server.auth.sign_out()
            dest_server.auth.sign_out()
            st.stop()

        publish_workbooks(src_server, dest_server, files_and_wbs, dest_proj_obj.id)

        src_server.auth.sign_out()
        dest_server.auth.sign_out()
        st.success("🎉 Migration completed successfully!")

    except Exception as e:
        st.error(f"❌ Migration failed: {e}")
