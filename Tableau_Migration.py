import streamlit as st
import tableauserverclient as TSC
import os
import re
import pandas as pd

# Page setup
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)

# ----------------------------
# Helper functions
# ----------------------------
def sanitize(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
    base = os.path.join(os.getcwd(), "tableau_migration")
    src = os.path.join(base, "source", sanitize(project_name))
    dest = os.path.join(base, "destination", sanitize(project_name))
    os.makedirs(src, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    return src, dest

def get_local_path(type_: str, project_name: str, name: str, extension: str) -> str:
    path = os.path.join(os.getcwd(), "tableau_migration", type_, sanitize(project_name))
    return os.path.join(path, f"{sanitize(name)}{extension}")

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
        path = get_local_path("source", project_name, wb.name, ".twbx")
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

def publish_workbooks(server, files_and_wbs, dest_project_id, project_name):
    for wb, path in files_and_wbs:
        st.info(f"⬆️ Publishing: {wb.name}")
        try:
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.CreateNew)
            st.success(f"✅ Published: {wb.name}")
        except Exception as e:
            st.error(f"❌ Failed to publish {wb.name}: {e}")

def download_datasources(server, project_id, project_name):
    datasources, _ = server.datasources.get()
    selected = [ds for ds in datasources if ds.project_id == project_id]
    files = []
    for ds in selected:
        path = get_local_path("source", project_name, ds.name, ".tdsx")
        st.info(f"⬇️ Downloading: {ds.name}")
        try:
            file_path = server.datasources.download(ds.id, filepath=path)
            if os.path.exists(file_path):
                files.append((ds, file_path))
                st.success(f"✅ Downloaded: {ds.name}")
            else:
                st.error(f"❌ File not saved correctly: {ds.name}")
        except Exception as e:
            st.error(f"❌ Download failed for {ds.name}: {e}")
    return files

def publish_datasources(server, files_and_dss, dest_project_id, project_name):
    for ds, path in files_and_dss:
        st.info(f"⬆️ Publishing: {ds.name}")
        try:
            new_ds = TSC.DatasourceItem(name=ds.name, project_id=dest_project_id)
            server.datasources.publish(new_ds, path, mode=TSC.Server.PublishMode.CreateNew)
            st.success(f"✅ Published: {ds.name}")
        except Exception as e:
            st.error(f"❌ Failed to publish {ds.name}: {e}")

def copy_permissions(src_server, dest_server, src_project_id, dest_project_id):
    src_permissions = src_server.projects.get_permissions(src_project_id)
    for perm in src_permissions:
        grantee = perm.grantee
        capabilities = perm.capabilities
        dest_server.projects.add_permissions(dest_project_id, grantee, capabilities)
        st.info(f"✅ Copied permissions for {grantee.name}.")

def embed_credentials(server, files_and_items, is_workbook=True):
    for item, path in files_and_items:
        if is_workbook:
            server.workbooks.populate_connections(item)
            connections = item.connections
        else:
            server.datasources.populate_connections(item)
            connections = item.connections

        for conn in connections:
            if conn.username and conn.password:
                conn.embed_password = True
                if is_workbook:
                    server.workbooks.update_connection(item, conn)
                else:
                    server.datasources.update_connection(item, conn)
                st.info(f"✅ Embedded credentials for {conn.datasource_name}.")

# ----------------------------
# Streamlit UI Form
# ----------------------------
with st.form("migration_form"):
    st.subheader("🔐 Source Tableau")
    src_url = st.text_input("Source Server URL")
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

    st.subheader("🔐 Destination Tableau")
    dest_url = st.text_input("Destination Server URL")
    dest_site = st.text_input("Destination Site Content URL")
    dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")
    if dest_auth_method == "PAT":
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token_secret = st.text_input("Destination PAT Secret", type="password")
        dest_username = dest_password = None
   
::contentReference[oaicite:0]{index=0}
 
