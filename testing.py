import streamlit as st
import tableauserverclient as TSC
import os
import re

# Set up Streamlit page configuration
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)

def sanitize(name):
    """Sanitize project or workbook names to create valid directory names."""
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
    """Create local directories for source and destination workbooks."""
    base = os.path.join(os.getcwd(), "tableau_migration")
    src = os.path.join(base, "source", sanitize(project_name))
    dest = os.path.join(base, "destination", sanitize(project_name))
    os.makedirs(src, exist_ok=True)
    os.makedirs(dest, exist_ok=True)
    return src, dest

def get_local_path(type_: str, project_name: str, workbook_name: str) -> str:
    """Generate local file path for a workbook."""
    path = os.path.join(os.getcwd(), "tableau_migration", type_, sanitize(project_name))
    return os.path.join(path, f"{sanitize(workbook_name)}.twbx")

def get_auth(method, token_name, token_value, username, password, site):
    """Authenticate to Tableau Server."""
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    """Initialize Tableau Server client."""
    return TSC.Server(url, use_server_version=True)

def download_workbooks(server, project_id, project_name):
    """Download workbooks from the source server."""
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
    """Migrate permissions from source to destination workbook."""
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

def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id, project_name):
    """Publish workbooks to the destination server."""
    for wb, path in files_and_wbs:
        st.info(f"⬆️ Publishing: {wb.name}")
        try:
            new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
            published_wb = dest_server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.Overwrite)
            st.success(f"✅ Published: {wb.name}")
            migrate_permissions(src_server, wb, dest_server, published_wb)
        except Exception as e:
            st.error(f"❌ Failed to publish {wb.name}: {e}")

def get_or_create_project(server, project_name):
    """Get or create a project on the destination server."""
    projects, _ = server.projects.get()
    project = next((p for p in projects if p.name == project_name), None)
    if project:
        return project
    else:
        new_project = TSC.ProjectItem(name=project_name)
        created_project = server.projects.create(new_project)
        st.info(f"📁 Created destination project: {project_name}")
        return created_project

# Streamlit UI Form
with st.form("migration_form"):
    st.subheader("🔐 Source Server Configuration")
    col1, col2 = st.columns(2)
    
    with col1:
        src_auth_method = st.radio("Authentication Method", ["PAT", "Username/Password"], key="src_auth")
        src_server_url = st.text_input("Source Server URL", help="e.g., https://server.tableau.com")
        src_site = st.text_input("Source Site ID", value="", help="Leave empty for default site")
    
    with col2:
        if src_auth_method == "PAT":
            src_token_name = st.text_input("Source Personal Access Token Name")
            src_token_value = st.text_input("Source Personal Access Token Value", type="password")
        else:
            src_username = st.text_input("Source Username")
            src_password = st.text_input("Source Password", type="password")
    
    st.subheader("🔐 Destination Server Configuration")
    col3, col4 = st.columns(2)
    
    with col3:
        dest_auth_method = st.radio("Authentication Method", ["PAT", "Username/Password"], key="dest_auth")
        dest_server_url = st.text_input("Destination Server URL", help="e.g., https://server.tableau.com")
        dest_site = st.text_input("Destination Site ID", value="", help="Leave empty for default site")
    
    with col4:
        if dest_auth_method == "PAT":
            dest_token_name = st.text_input("Destination Personal Access Token Name")
            dest_token_value = st.text_input("Destination Personal Access Token Value", type="password")
        else:
            dest_username = st.text_input("Destination Username")
            dest_password = st.text_input("Destination Password", type="password")
    
    st.subheader("📂 Migration Settings")
    src_project_name = st.text_input("Source Project Name", help="Name of the project to migrate from")
    dest_project_name = st.text_input("Destination Project Name", help="Name of the project to migrate to (will be created if it doesn't exist)")
    
    submitted = st.form_submit_button("🚀 Start Migration")

if submitted:
    try:
        # Validate inputs
        if not all([src_server_url, dest_server_url, src_project_name, dest_project_name]):
            st.error("Please fill in all required fields")
            st.stop()
        
        # Authenticate to source server
        src_auth = get_auth(
            src_auth_method,
            src_token_name if src_auth_method == "PAT" else None,
            src_token_value if src_auth_method == "PAT" else None,
            src_username if src_auth_method != "PAT" else None,
            src_password if src_auth_method != "PAT" else None,
            src_site
        )
        
        src_server = get_server(src_server_url)
        with src_server.auth.sign_in(src_auth):
            st.success("🔓 Successfully connected to source server")
            
            # Get source project
            projects, _ = src_server.projects.get()
            src_project = next((p for p in projects if p.name == src_project_name), None)
            
            if not src_project:
                st.error(f"❌ Source project '{src_project_name}' not found")
                st.stop()
            
            # Authenticate to destination server
            dest_auth = get_auth(
                dest_auth_method,
                dest_token_name if dest_auth_method == "PAT" else None,
                dest_token_value if dest_auth_method == "PAT" else None,
                dest_username if dest_auth_method != "PAT" else None,
                dest_password if dest_auth_method != "PAT" else None,
                dest_site
            )
            
            dest_server = get_server(dest_server_url)
            with dest_server.auth.sign_in(dest_auth):
                st.success("🔓 Successfully connected to destination server")
                
                # Create local directories
                create_local_dirs(src_project_name)
                
                # Download workbooks from source
                files_and_wbs = download_workbooks(src_server, src_project.id, src_project_name)
                
                if not files_and_wbs:
                    st.warning("⚠️ No workbooks found to migrate")
                    st.stop()
                
                # Get or create destination project
                dest_project = get_or_create_project(dest_server, dest_project_name)
                
                # Publish workbooks to destination
                publish_workbooks(src_server, dest_server, files_and_wbs, dest_project.id, dest_project_name)
                
                st.balloons()
                st.success("🎉 Migration completed successfully!")
    
    except Exception as e:
        st.error(f"❌ Migration failed: {str(e)}")

st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)
