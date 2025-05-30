import streamlit as st
import tableauserverclient as TSC
import os
import re
from typing import List, Tuple

# Set up Streamlit page configuration
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Content Migration Tool</h1>", unsafe_allow_html=True)

def sanitize(name):
    """Sanitize names to create valid directory names."""
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
    """Create local directories for all content types."""
    base = os.path.join(os.getcwd(), "tableau_migration")
    dirs = {
        'workbooks': os.path.join(base, "workbooks", sanitize(project_name)),
        'datasources': os.path.join(base, "datasources", sanitize(project_name)),
        'views': os.path.join(base, "views", sanitize(project_name))
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def download_content(server, project_id, project_name, content_type):
    """Download content (workbooks/datasources) from Tableau Server."""
    dirs = create_local_dirs(project_name)
    downloaded_files = []
    
    if content_type == "workbook":
        items, _ = server.workbooks.get()
        for item in items:
            if item.project_id == project_id:
                path = os.path.join(dirs['workbooks'], f"{sanitize(item.name)}.twbx")
                try:
                    file_path = server.workbooks.download(item.id, filepath=path)
                    if os.path.exists(file_path):
                        downloaded_files.append((item, file_path, 'workbook'))
                        st.success(f"✅ Downloaded workbook: {item.name}")
                    else:
                        st.error(f"❌ Workbook not saved: {item.name}")
                except Exception as e:
                    st.error(f"❌ Failed to download workbook {item.name}: {e}")
    
    elif content_type == "datasource":
        items, _ = server.datasources.get()
        for item in items:
            if item.project_id == project_id:
                path = os.path.join(dirs['datasources'], f"{sanitize(item.name)}.tdsx")
                try:
                    file_path = server.datasources.download(item.id, filepath=path)
                    if os.path.exists(file_path):
                        downloaded_files.append((item, file_path, 'datasource'))
                        st.success(f"✅ Downloaded datasource: {item.name}")
                    else:
                        st.error(f"❌ Datasource not saved: {item.name}")
                except Exception as e:
                    st.error(f"❌ Failed to download datasource {item.name}: {e}")
    
    return downloaded_files

def download_views(server, project_id, project_name):
    """Download custom views from workbooks in the project."""
    dirs = create_local_dirs(project_name)
    views_data = []
    
    workbooks, _ = server.workbooks.get()
    project_workbooks = [wb for wb in workbooks if wb.project_id == project_id]
    
    for wb in project_workbooks:
        try:
            server.workbooks.populate_views(wb)
            for view in wb.views:
                if view.name != 'Sheet 1':  # Skip default views
                    view_path = os.path.join(dirs['views'], f"{sanitize(wb.name)}_{sanitize(view.name)}.pdf")
                    try:
                        server.views.populate_image(view)
                        with open(view_path, 'wb') as f:
                            f.write(view.image)
                        views_data.append((wb, view, view_path))
                        st.success(f"✅ Downloaded view: {view.name} from {wb.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to download view {view.name}: {e}")
        except Exception as e:
            st.error(f"❌ Failed to process workbook {wb.name} for views: {e}")
    
    return views_data

def migrate_permissions(src_server, src_item, dest_server, dest_item, item_type):
    """Migrate permissions for either workbook or datasource."""
    try:
        if item_type == 'workbook':
            src_server.workbooks.populate_permissions(src_item)
            dest_server.workbooks.populate_permissions(dest_item)
            permissions = src_item.permissions
            permission_manager = dest_server.workbooks
        elif item_type == 'datasource':
            src_server.datasources.populate_permissions(src_item)
            dest_server.datasources.populate_permissions(dest_item)
            permissions = src_item.permissions
            permission_manager = dest_server.datasources
        
        # Clear existing destination permissions
        for perm in dest_item.permissions:
            permission_manager._permissions.delete(dest_item, perm)
        
        # Get user/group mappings
        src_users, _ = src_server.users.get()
        src_groups, _ = src_server.groups.get()
        dest_users, _ = dest_server.users.get()
        dest_groups, _ = dest_server.groups.get()
        
        src_user_map = {u.id: u for u in src_users}
        src_group_map = {g.id: g for g in src_groups}
        dest_user_map = {u.name: u for u in dest_users}
        dest_group_map = {g.name: g for g in dest_groups}
        
        missing_grantees = []
        
        for perm in permissions:
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
                permission_manager.update_permissions(dest_item, [new_perm])
        
        if missing_grantees:
            st.warning(f"⚠️ Skipped permissions for missing users/groups in {item_type} {src_item.name}:")
            st.write(list(set(missing_grantees)))
        
        st.success(f"🔑 Permissions migrated for {item_type}: {src_item.name}")
    
    except Exception as e:
        st.error(f"❌ Failed to migrate permissions for {item_type} {src_item.name}: {e}")

def publish_content(src_server, dest_server, downloaded_items, dest_project_id, content_type):
    """Publish content to destination server."""
    for item, path, item_type in downloaded_items:
        st.info(f"⬆️ Publishing {item_type}: {item.name}")
        try:
            if item_type == 'workbook':
                new_item = TSC.WorkbookItem(name=item.name, project_id=dest_project_id)
                published_item = dest_server.workbooks.publish(new_item, path, mode=TSC.Server.PublishMode.Overwrite)
            elif item_type == 'datasource':
                new_item = TSC.DatasourceItem(name=item.name, project_id=dest_project_id)
                published_item = dest_server.datasources.publish(new_item, path, mode=TSC.Server.PublishMode.Overwrite)
            
            st.success(f"✅ Published {item_type}: {item.name}")
            migrate_permissions(src_server, item, dest_server, published_item, item_type)
        except Exception as e:
            st.error(f"❌ Failed to publish {item_type} {item.name}: {e}")

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

# Streamlit UI
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
    dest_project_name = st.text_input("Destination Project Name", help="Name of the project to migrate to")
    
    content_types = st.multiselect(
        "Select content types to migrate",
        ["Workbooks", "Data Sources", "Custom Views"],
        default=["Workbooks", "Data Sources"]
    )
    
    submitted = st.form_submit_button("🚀 Start Migration")

if submitted:
    try:
        # Validate inputs
        if not all([src_server_url, dest_server_url, src_project_name, dest_project_name]):
            st.error("Please fill in all required fields")
            st.stop()
        
        if not content_types:
            st.error("Please select at least one content type to migrate")
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
                
                # Get or create destination project
                dest_project = get_or_create_project(dest_server, dest_project_name)
                
                # Download and migrate selected content types
                downloaded_items = []
                
                if "Workbooks" in content_types:
                    st.subheader("📚 Workbooks Migration")
                    wb_items = download_content(src_server, src_project.id, src_project_name, "workbook")
                    downloaded_items.extend(wb_items)
                
                if "Data Sources" in content_types:
                    st.subheader("📊 Data Sources Migration")
                    ds_items = download_content(src_server, src_project.id, src_project_name, "datasource")
                    downloaded_items.extend(ds_items)
                
                if "Custom Views" in content_types:
                    st.subheader("👁️ Custom Views Migration")
                    view_items = download_views(src_server, src_project.id, src_project_name)
                
                # Publish downloaded content
                if downloaded_items:
                    st.subheader("🚀 Publishing Content to Destination")
                    publish_content(src_server, dest_server, downloaded_items, dest_project.id, "workbook")
                
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
