import streamlit as st
import tableauserverclient as TSC
import os
import re
import pandas as pd
import logging

# Set up logging
log_file = "migration_log.csv"
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(message)s')
log_header = ["Content Type", "Name", "Status", "Message"]
if not os.path.exists(log_file):
    pd.DataFrame(columns=log_header).to_csv(log_file, index=False)

# Page setup
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Migration Tool</h1>", unsafe_allow_html=True)

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

def log_migration(content_type, name, status, message):
    logging.info(f"{content_type},{name},{status},{message}")
    df = pd.read_csv(log_file)
    df = df.append({"Content Type": content_type, "Name": name, "Status": status, "Message": message}, ignore_index=True)
    df.to_csv(log_file, index=False)

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
                log_migration("Workbook", wb.name, "Success", f"Downloaded to {file_path}")
                st.success(f"✅ Downloaded: {wb.name}")
            else:
                log_migration("Workbook", wb.name, "Failure", "File not saved correctly")
                st.error(f"❌ File not saved correctly: {wb.name}")
        except Exception as e:
            log_migration("Workbook", wb.name, "Failure", f"Download failed: {e}")
            st.error(f"❌ Download failed for {wb.name}: {e}")
    return files

def publish_workbooks(server, files_and_wbs, dest_project_id, project_name):
    for wb, path in files_and_wbs:
        st.info(f"⬆️ Publishing: {wb.name}")
        try:
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.CreateNew)
            log_migration("Workbook", wb.name, "Success", f"Published to project ID {dest_project_id}")
            st.success(f"✅ Published: {wb.name}")
        except Exception as e:
            log_migration("Workbook", wb.name, "Failure", f"Publish failed: {e}")
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
                log_migration("Datasource", ds.name, "Success", f"Downloaded to {file_path}")
                st.success(f"✅ Downloaded: {ds.name}")
            else:
                log_migration("Datasource", ds.name, "Failure", "File not saved correctly")
                st.error(f"❌ File not saved correctly: {ds.name}")
        except Exception as e:
            log_migration("Datasource", ds.name, "Failure", f"Download failed: {e}")
            st.error(f"❌ Download failed for {ds.name}: {e}")
    return files

def publish_datasources(server, files_and_dss, dest_project_id, project_name):
    for ds, path in files_and_dss:
        st.info(f"⬆️ Publishing: {ds.name}")
        try:
            new_ds = TSC.DatasourceItem(name=ds.name, project_id=dest_project_id)
            server.datasources.publish(new_ds, path, mode=TSC.Server.PublishMode.CreateNew)
            log_migration("Datasource", ds.name, "Success", f"Published to project ID {dest_project_id}")
            st.success(f"✅ Published: {ds.name}")
        except Exception as e:
            log_migration("Datasource", ds.name, "Failure", f"Publish failed: {e}")
            st.error(f"❌ Failed to publish {ds.name}: {e}")

def copy_permissions(src_server, dest_server, src_project_id, dest_project_id):
    src_permissions = src_server.projects.get_permissions(src_project_id)
    for perm in src_permissions:
        grantee = perm.grantee
        capabilities = perm.capabilities
        dest_server.projects.add_permissions(dest_project_id, grantee, capabilities)
        log_migration("Permission", grantee.name, "Success", f"Copied to project ID {dest_project_id}")
        st.info(f"✅ Copied permissions for {grantee.name}.")

def embed_credentials(server, files_and_items, is_workbook=True):
    for item, path in files_and_items:
        if is_workbook:
            server.workbooks.populate
::contentReference[oaicite:0]{index=0}
 
