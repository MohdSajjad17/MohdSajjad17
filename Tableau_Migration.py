import streamlit as st
import tableauserverclient as TSC
import os
import re

st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)

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

def download_data_sources(server, project_id, project_name):
    data_sources, _ = server.datasources.get()
    selected = [ds for ds in data_sources if ds.project_id == project_id]
    files = []
    for ds in selected:
        path = get_local_path("source", project_name, ds.name)
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

def migrate_permissions(src_server, src_wb, dest_server, dest_wb):
    try:
        src_server.workbooks.populate_permissions(src_wb)
        dest_server.workbooks.populate_permissions(dest_wb)

        src_perms = src_wb.permissions
        dest_perms = dest_wb.permissions

        # Clear existing destination permissions
        for perm in dest_perms:
            dest_server.workbooks._permissions.delete(dest_wb, perm)

        src_users, _ = src_server.users.get()
        src_groups, _ = src_server.groups.get()
        dest_users, _ = dest_server.users.get()
        dest_groups, _ = dest_server.groups.get()

        src_user_map = {u.id: u for u in src_users}
        src_group_map = {g.id: g for g in src_groups}
        dest_user_map = {u.name: u for u in dest_users}
        dest_group_map = {g.name: g for g in dest_groups}

        missing_grantees = []

        for perm in src_perms:
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
                dest_server.workbooks.update_permissions(dest_wb, [new_perm])
            else:
                st.warning(f"⚠️ Skipped permission for unknown grantee with ID: {grantee_ref.id}")

        if missing_grantees:
            st.info("ℹ️ Skipped the following missing users/groups:")
            st.write(list(set(missing_grantees)))

        st.success(f"🔑 Permissions migrated for workbook: {src_wb.name}")

    except Exception as e:
        st.error(f"❌ Failed to migrate permissions for {src_wb.name}: {e}")

def migrate_data_source_permissions(src_server, src_ds, dest_server, dest_ds):
    try:
        src_server.datasources.populate_permissions(src_ds)
        dest_server.datasources.populate_permissions(dest_ds)

        src_perms = src_ds.permissions
        dest_perms = dest_ds.permissions

        # Clear existing destination permissions
        for perm in dest_perms:
            dest_server.datasources._permissions.delete(dest_ds, perm)

        src_users, _ = src_server.users.get()
        src_groups, _ = src_server.groups.get()
        dest_users, _ = dest_server.users.get()
        dest_groups, _ = dest_server.groups.get()

        src_user_map = {u.id: u for u in src_users}
        src_group_map = {g.id: g for g in src_groups}
        dest_user_map = {u.name: u for u in dest_users}
        dest_group_map = {g.name: g for g in dest_groups}

        missing_grantees = []

        for perm in src_perms:
            grantee_ref = perm.grantee
            dest_grantee = None

            if grantee_ref.tag_name == 'user':
                src_user = src_user_map.get(gr
::contentReference[oaicite:0]{index=0}
 
