import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os
import re

# Set up Streamlit page
st.set_page_config(page_title="Tableau Migration Suite", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Tableau Migration Suite</h1>", unsafe_allow_html=True)

# ---------------------------
# Utility Functions
# ---------------------------
def sanitize(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
    base = os.path.join(os.getcwd(), "tableau_migration")
    src = os.path.join(base, "source", sanitize(project_name))
    dest = os.path.join(base, "destination", sanitize(project_name))
    os.makedirs(src, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    return src, dest

def get_local_path(type_, project_name, content_name, ext=".twbx"):
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
    try:
        if item_type == "workbook":
            src_server.workbooks.populate_permissions(src_item)
            dest_server.workbooks.populate_permissions(dest_item)
            dest_perms_obj = dest_server.workbooks
        elif item_type == "datasource":
            src_server.datasources.populate_permissions(src_item)
            dest_server.datasources.populate_permissions(dest_item)
            dest_perms_obj = dest_server.datasources
        elif item_type == "flow":
            src_server.flows.populate_permissions(src_item)
            dest_server.flows.populate_permissions(dest_item)
            dest_perms_obj = dest_server.flows
        else:
            st.warning(f"⚠️ Permissions migration not implemented for type: {item_type}")
            return

        for perm in dest_item.permissions:
            dest_perms_obj._permissions.delete(dest_item, perm)

        src_users, _ = src_server.users.get()
        src_groups, _ = src_server.groups.get()
        dest_users, _ = dest_server.users.get()
        dest_groups, _ = dest_server.groups.get()

        src_user_map = {u.id: u for u in src_users}
        src_group_map = {g.id: g for g in src_groups}
        dest_user_map = {u.name: u for u in dest_users}
        dest_group_map = {g.name: g for g in dest_groups}

        missing_grantees = []

        for perm in src_item.permissions:
            grantee_ref = perm.grantee
            dest_grantee = None

            if grantee_ref.tag_name == 'user':
                src_user = src_user_map.get(grantee_ref.id)
                if src_user and src_user.name in dest_user_map:
                    dest_grantee = dest_user_map[src_user.name]
                else:
                    missing_grantees.append(src_user.name if src_user else grantee_ref.id)

            elif grantee_ref.tag_name == 'group':
                src_group = src_group_map.get(grantee_ref.id)
                if src_group and src_group.name in dest_group_map:
                    dest_grantee = dest_group_map[src_group.name]
                else:
                    missing_grantees.append(src_group.name if src_group else grantee_ref.id)

            if dest_grantee:
                new_perm = TSC.PermissionsRule(grantee=dest_grantee, capabilities=perm.capabilities)
                dest_perms_obj.update_permissions(dest_item, [new_perm])
            else:
                st.warning(f"⚠️ Skipped unknown grantee with ID: {grantee_ref.id}")

        if missing_grantees:
            st.info("ℹ️ Skipped missing users/groups:")
            st.write(list(set(missing_grantees)))

        st.success(f"🔑 Permissions migrated for {item_type}: {src_item.name}")
    except Exception as e:
        st.error(f"❌ Permission migration failed: {e}")

def download_publish_content(server, project_id, project_name, type_, ext, downloader, publisher, migrate=False, src_server=None):
    items, _ = downloader()
    selected = [i for i in items if i.project_id == project_id]
    files = []
    for item in selected:
        path = get_local_path("source", project_name, item.name, ext=ext)
        st.info(f"⬇️ Downloading {type_}: {item.name}")
        try:
            file_path = downloader(item.id, filepath=path)
            if os.path.exists(file_path):
                files.append((item, file_path))
                st.success(f"✅ Downloaded {type_}: {item.name}")
            else:
                st.error(f"❌ File not saved: {item.name}")
        except Exception as e:
            st.error(f"❌ Download failed for {item.name}: {e}")
    return files

def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id, project_name):
    for wb, path in files_and_wbs:
        st.info(f"⬆️ Publishing workbook: {wb.name}")
        try:
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            published_wb = dest_server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.Overwrite)
            st.success(f"✅ Published workbook: {wb.name}")
            migrate_permissions(src_server, wb, dest_server, published_wb, "workbook")
        except Exception as e:
            st.error(f"❌ Publish failed: {e}")

def publish_datasources(dest_server, files_and_ds, dest_project_id):
    for ds, path in files_and_ds:
        st.info(f"⬆️ Publishing datasource: {ds.name}")
        try:
            new_ds = TSC.DatasourceItem(name=ds.name, project_id=dest_project_id)
            published_ds = dest_server.datasources.publish(new_ds, path, mode=TSC.Server.PublishMode.Overwrite)
            st.success(f"✅ Published datasource: {ds.name}")
        except Exception as e:
            st.error(f"❌ Publish failed: {e}")

def publish_flows(dest_server, files_and_flows, dest_project_id):
    for flow, path in files_and_flows:
        st.info(f"⬆️ Publishing flow: {flow.name}")
        try:
            new_flow = TSC.FlowItem(name=flow.name, project_id=dest_project_id)
            published_flow = dest_server.flows.publish(new_flow, path, mode=TSC.Server.PublishMode.Overwrite)
            st.success(f"✅ Published flow: {flow.name}")
        except Exception as e:
            st.error(f"❌ Publish failed: {e}")

def get_or_create_project(server, project_name):
    projects, _ = server.projects.get()
    existing = next((p for p in projects if p.name == project_name), None)
    if existing:
        return existing
    else:
        new_project = TSC.ProjectItem(name=project_name)
        return server.projects.create(new_project)

def to_csv_download(data, headers, filename, label):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

def run_import(import_type, uploaded_file, auth):
    if not uploaded_file:
        st.warning("⚠️ Upload a CSV first.")
        return
    server = get_server(server_url)
    server.auth.sign_in(auth)
    df = pd.read_csv(uploaded_file)
    if import_type == "Users":
        for _, row in df.iterrows():
            try:
                user = TSC.UserItem(name=row['name'], site_role=row['site_role'])
                server.users.add(user)
            except Exception as e:
                st.warning(f"⚠️ Failed to add user: {e}")
        st.success("✅ Users imported.")
    elif import_type == "Groups":
        for _, row in df.iterrows():
            try:
                group = TSC.GroupItem(name=row[0])
                server.groups.create(group)
            except Exception as e:
                st.warning(f"⚠️ Failed to add group: {e}")
        st.success("✅ Groups imported.")
    server.auth.sign_out()

# ---------------------------
# UI with Tabs
# ---------------------------
tab1, tab2 = st.tabs(["🔁 Migration Tool", "📤 Export / Import Tool"])

with tab1:
    with st.form("migration_form"):
        st.subheader("🔐 Source Tableau")
        src_url = st.text_input("Source Server URL")
        src_site = st.text_input("Source Site Content URL", "")
        src_auth_method = st.selectbox("Source Auth", ["PAT", "Username & Password"])
        if src_auth_method == "PAT":
            src_token_name = st.text_input("Source PAT Name")
            src_token = st.text_input("Source PAT Token", type="password")
            src_auth = get_auth("PAT", src_token_name, src_token, None, None, src_site)
        else:
            src_user = st.text_input("Source Username")
            src_pass = st.text_input("Source Password", type="password")
            src_auth = get_auth("Password", None, None, src_user, src_pass, src_site)

        st.divider()
        st.subheader("🚀 Destination Tableau")
        dest_url = st.text_input("Destination Server URL")
        dest_site = st.text_input("Destination Site Content URL", "")
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token = st.text_input("Destination PAT Token", type="password")
        dest_auth = get_auth("PAT", dest_token_name, dest_token, None, None, dest_site)

        project_name = st.text_input("Project Name for Migration")

        if st.form_submit_button("Start Migration"):
            with st.spinner("🔁 Migrating..."):
                src_server = get_server(src_url)
                dest_server = get_server(dest_url)
                src_server.auth.sign_in(src_auth)
                dest_server.auth.sign_in(dest_auth)
                src_project_id = next((p.id for p in src_server.projects.get()[0] if p.name == project_name), None)
                dest_project = get_or_create_project(dest_server, project_name)

                # Download Workbooks
                files_and_wbs = download_publish_content(
                    src_server, src_project_id, project_name, "workbook", ".twbx",
                    src_server.workbooks.download, src_server.workbooks.publish)

                publish_workbooks(src_server, dest_server, files_and_wbs, dest_project.id, project_name)

                # Data sources
                files_and_ds = download_publish_content(
                    src_server, src_project_id, project_name, "datasource", ".tdsx",
                    src_server.datasources.download, src_server.datasources.publish)
                publish_datasources(dest_server, files_and_ds, dest_project.id)

                # Flows
                files_and_flows = download_publish_content(
                    src_server, src_project_id, project_name, "flow", ".tflx",
                    src_server.flows.download, src_server.flows.publish)
                publish_flows(dest_server, files_and_flows, dest_project.id)

                src_server.auth.sign_out()
                dest_server.auth.sign_out()
                st.success("✅ Migration completed.")

with tab2:
    st.subheader("📤 Export / Import Users and Groups")
    server_url = st.text_input("Server URL")
    site = st.text_input("Site Content URL", "")
    auth_method = st.selectbox("Authentication Method", ["PAT", "Username & Password"])
    if auth_method == "PAT":
        token_name = st.text_input("PAT Name")
        token = st.text_input("PAT Token", type="password")
        auth = get_auth("PAT", token_name, token, None, None, site)
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        auth = get_auth("Password", None, None, username, password, site)

    if st.button("Export Users and Groups"):
        server = get_server(server_url)
        server.auth.sign_in(auth)
        users = server.users.get()[0]
        groups = server.groups.get()[0]
        user_data = [(u.name, u.site_role) for u in users]
        group_data = [(g.name,) for g in groups]
        server.auth.sign_out()

        to_csv_download(user_data, ["name", "site_role"], "users.csv", "Download Users CSV")
        to_csv_download(group_data, ["group_name"], "groups.csv", "Download Groups CSV")

    import_type = st.selectbox("Import Type", ["Users", "Groups"])
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if st.button("Import"):
        run_import(import_type, uploaded_file, auth)
