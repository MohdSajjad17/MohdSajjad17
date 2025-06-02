import streamlit as st
import tableauserverclient as TSC
import os
import re
import time
import logging
from typing import Dict, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Streamlit page configuration
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Content Migration Tool</h1>", unsafe_allow_html=True)

# --------------------------
# Utility Functions
# --------------------------
def sanitize(name: str) -> str:
    """Sanitize names to create valid directory names."""
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name: str) -> Dict[str, str]:
    """Create local directories for all content types."""
    base = os.path.join(os.getcwd(), "tableau_migration")
    dirs = {
        'workbooks': os.path.join(base, "workbooks", sanitize(project_name)),
        'datasources': os.path.join(base, "datasources", sanitize(project_name)),
        'views': os.path.join(base, "views", sanitize(project_name)),
        'users': os.path.join(base, "users"),
        'groups': os.path.join(base, "groups")
    }
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    return dirs

def get_auth(method: str, token_name: str, token_value: str, username: str, password: str, site: str):
    """Authenticate to Tableau Server."""
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url: str) -> TSC.Server:
    """Initialize Tableau Server client."""
    server = TSC.Server(url, use_server_version=True)
    server.add_http_options({'verify': False})  # Disable SSL verification if needed
    return server

def get_or_create_project(server: TSC.Server, project_name: str, parent_project_id: str = None) -> TSC.ProjectItem:
    """Get or create a project on the destination server."""
    try:
        all_projects = list(TSC.Pager(server.projects))
        project = next((p for p in all_projects if p.name == project_name), None)
        
        if not project:
            new_project = TSC.ProjectItem(name=project_name, content_permissions="ManagedByOwner")
            if parent_project_id:
                new_project.parent_id = parent_project_id
            project = server.projects.create(new_project)
            st.success(f"✅ Created new project: {project_name}")
        else:
            st.info(f"ℹ️ Using existing project: {project_name}")
        
        return project
    except Exception as e:
        st.error(f"❌ Failed to get/create project {project_name}: {str(e)}")
        raise

# --------------------------
# Permission and Schedule Migration
# --------------------------
def migrate_permissions(src_server, src_wb, dest_server, dest_wb):
    try:
        # Populate permissions
        src_server.workbooks.populate_permissions(src_wb)
        dest_server.workbooks.populate_permissions(dest_wb)

        src_perms = src_wb.permissions
        dest_perms = dest_wb.permissions

        # Clear existing permissions safely using the public method
        for perm in dest_perms:
            dest_server.workbooks.delete_permission(dest_wb, perm)

        # Fetch users and groups
        src_users, _ = src_server.users.get()
        src_groups, _ = src_server.groups.get()
        dest_users, _ = dest_server.users.get()
        dest_groups, _ = dest_server.groups.get()

        src_user_map = {u.id: u for u in src_users}
        src_group_map = {g.id: g for g in src_groups}
        dest_user_map = {u.name: u for u in dest_users}
        dest_group_map = {g.name: g for g in dest_groups}

        new_permissions = []
        missing_grantees = []

        for perm in src_perms:
            grantee_ref = perm.grantee
            dest_grantee_ref = None

            if grantee_ref.tag_name == 'user':
                src_user = src_user_map.get(grantee_ref.id)
                if src_user and src_user.name in dest_user_map:
                    dest_user = dest_user_map[src_user.name]
                    dest_grantee_ref = TSC.UserItem.as_reference(dest_user.id)
                else:
                    missing_grantees.append(src_user.name if src_user else grantee_ref.id)

            elif grantee_ref.tag_name == 'group':
                src_group = src_group_map.get(grantee_ref.id)
                if src_group and src_group.name in dest_group_map:
                    dest_group = dest_group_map[src_group.name]
                    dest_grantee_ref = TSC.GroupItem.as_reference(dest_group.id)
                else:
                    missing_grantees.append(src_group.name if src_group else grantee_ref.id)

            if dest_grantee_ref:
                new_perm = TSC.PermissionsRule(
                    grantee=dest_grantee_ref,
                    capabilities=perm.capabilities
                )
                new_permissions.append(new_perm)
            else:
                st.warning(f"⚠️ Skipped permission for unknown grantee with ID: {grantee_ref.id}")

        # Apply all permissions at once
        if new_permissions:
            dest_server.workbooks.update_permissions(dest_wb, new_permissions)

        if missing_grantees:
            st.info("ℹ️ Skipped the following missing users/groups:")
            st.write(list(set(missing_grantees)))

        st.success(f"🔑 Permissions migrated for workbook: {src_wb.name}")

    except Exception as e:
        st.error(f"❌ Failed to migrate permissions for {src_wb.name}: {e}")

def migrate_extract_schedules(
    src_server: TSC.Server,
    dest_server: TSC.Server,
    src_item,
    dest_item,
    item_type: str,
    project_id: str
):
    """Migrate extract refresh schedules from source to destination item."""
    try:
        # Get source schedules
        if item_type == 'workbook':
            schedules = src_server.workbooks.get_extract_refresh_schedules(src_item.id)
        elif item_type == 'datasource':
            schedules = src_server.datasources.get_extract_refresh_schedules(src_item.id)
        else:
            return

        if not schedules:
            st.info(f"ℹ️ No extract schedules to migrate for {item_type} {src_item.name}")
            return

        # Create destination schedules
        for schedule in schedules:
            new_schedule = TSC.ScheduleItem(
                name=schedule.name,
                priority=schedule.priority,
                frequency=schedule.frequency,
                execution_order=schedule.execution_order,
                state=schedule.state
            )

            # Set time details based on frequency
            if schedule.frequency == 'Hourly':
                new_schedule.hourly_schedule = schedule.hourly_schedule
            elif schedule.frequency == 'Daily':
                new_schedule.daily_schedule = schedule.daily_schedule
            elif schedule.frequency == 'Weekly':
                new_schedule.weekly_schedule = schedule.weekly_schedule
            elif schedule.frequency == 'Monthly':
                new_schedule.monthly_schedule = schedule.monthly_schedule

            # Create schedule on destination
            created_schedule = dest_server.schedules.create(new_schedule)

            # Assign schedule to item
            if item_type == 'workbook':
                dest_server.workbooks.add_extract_refresh_task(dest_item.id, created_schedule.id)
            elif item_type == 'datasource':
                dest_server.datasources.add_extract_refresh_task(dest_item.id, created_schedule.id)

            st.success(f"✅ Created schedule {schedule.name} for {item_type} {src_item.name}")

    except Exception as e:
        st.error(f"❌ Failed to migrate schedules for {item_type} {src_item.name}: {str(e)}")
        raise

# --------------------------
# User and Group Migration
# --------------------------
def migrate_users(src_server: TSC.Server, dest_server: TSC.Server) -> Dict[str, TSC.UserItem]:
    """Migrate users from source to destination server."""
    st.subheader("👤 Migrating Users")
    try:
        src_users = list(TSC.Pager(src_server.users))
        dest_users = list(TSC.Pager(dest_server.users))
        
        src_user_map = {u.name.lower(): u for u in src_users}
        dest_user_map = {u.name.lower(): u for u in dest_users}
        
        migrated_users = 0
        skipped_users = 0
        
        for user in src_users:
            # Skip system users
            if user.name.lower() in ['system', 'guest', 'tableau']:
                continue
                
            if user.name.lower() not in dest_user_map:
                try:
                    new_user = TSC.UserItem(
                        name=user.name,
                        site_role=user.site_role
                    )
                    # Add email if available
                    if hasattr(user, 'email'):
                        new_user.email = user.email
                    
                    created_user = dest_server.users.add(new_user)
                    dest_user_map[user.name.lower()] = created_user
                    st.success(f"✅ Created user: {user.name}")
                    migrated_users += 1
                except Exception as e:
                    st.error(f"❌ Failed to create user {user.name}: {str(e)}")
                    skipped_users += 1
            else:
                st.info(f"ℹ️ User already exists: {user.name}")
                skipped_users += 1
        
        st.info(f"ℹ️ User migration summary: {migrated_users} migrated, {skipped_users} skipped")
        return dest_user_map
    except Exception as e:
        st.error(f"❌ Failed to migrate users: {str(e)}")
        raise

def migrate_groups(src_server: TSC.Server, dest_server: TSC.Server, user_map: Dict[str, TSC.UserItem]) -> Dict[str, TSC.GroupItem]:
    """Migrate groups and their memberships from source to destination server."""
    st.subheader("👥 Migrating Groups")
    try:
        src_groups = list(TSC.Pager(src_server.groups))
        dest_groups = list(TSC.Pager(dest_server.groups))
        
        src_group_map = {g.name.lower(): g for g in src_groups}
        dest_group_map = {g.name.lower(): g for g in dest_groups}
        
        migrated_groups = 0
        skipped_groups = 0
        
        # First create all groups
        for group in src_groups:
            if group.name.lower() not in dest_group_map:
                try:
                    new_group = TSC.GroupItem(group.name)
                    created_group = dest_server.groups.create(new_group)
                    dest_group_map[group.name.lower()] = created_group
                    st.success(f"✅ Created group: {group.name}")
                    migrated_groups += 1
                except Exception as e:
                    st.error(f"❌ Failed to create group {group.name}: {str(e)}")
                    skipped_groups += 1
            else:
                st.info(f"ℹ️ Group already exists: {group.name}")
                skipped_groups += 1
        
        # Then populate group memberships
        st.subheader("👥➡👤 Migrating Group Memberships")
        for group in src_groups:
            if group.name.lower() in dest_group_map:
                dest_group = dest_group_map[group.name.lower()]
                
                # Get source group members
                src_server.groups.populate_users(group)
                if not hasattr(group, 'users'):
                    continue
                    
                added_members = 0
                for user in group.users:
                    if user.name.lower() in user_map:
                        try:
                            dest_user = user_map[user.name.lower()]
                            if isinstance(dest_user, TSC.UserItem):
                                dest_server.groups.add_user(dest_group.id, dest_user.id)
                                st.success(f"✅ Added user {user.name} to group {group.name}")
                                added_members += 1
                            else:
                                st.error(f"❌ Invalid user object for {user.name}")
                        except Exception as e:
                            st.error(f"❌ Failed to add user {user.name} to group {group.name}: {str(e)}")
                    else:
                        st.warning(f"⚠️ User not found in destination: {user.name}")
                
                st.info(f"ℹ️ Added {added_members} members to group {group.name}")
        
        st.info(f"ℹ️ Group migration summary: {migrated_groups} migrated, {skipped_groups} skipped")
        return dest_group_map
    except Exception as e:
        st.error(f"❌ Failed to migrate groups: {str(e)}")
        raise

# --------------------------
# Content Download Functions
# --------------------------
def download_content(server: TSC.Server, project_id: str, project_name: str, content_type: str) -> List:
    """Download content (workbooks/datasources) from Tableau Server."""
    dirs = create_local_dirs(project_name)
    downloaded_files = []
    
    try:
        if content_type == "datasource":
            items = list(TSC.Pager(server.datasources))
            for item in items:
                if item.project_id == project_id:
                    path = os.path.join(dirs['datasources'], f"{sanitize(item.name)}.tdsx")
                    try:
                        file_path = server.datasources.download(item.id, filepath=path, include_extract=True)
                        if os.path.exists(file_path):
                            downloaded_files.append((item, file_path, 'datasource'))
                            st.success(f"✅ Downloaded datasource: {item.name}")
                        else:
                            st.error(f"❌ Datasource not saved: {item.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to download datasource {item.name}: {str(e)}")
        elif content_type == "workbook":
            items = list(TSC.Pager(server.workbooks))
            for item in items:
                if item.project_id == project_id:
                    path = os.path.join(dirs['workbooks'], f"{sanitize(item.name)}.twbx")
                    try:
                        file_path = server.workbooks.download(item.id, filepath=path, include_extract=True)
                        if os.path.exists(file_path):
                            downloaded_files.append((item, file_path, 'workbook'))
                            st.success(f"✅ Downloaded workbook: {item.name}")
                        else:
                            st.error(f"❌ Workbook not saved: {item.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to download workbook {item.name}: {str(e)}")
        

        
        elif content_type == "custom_view":
            items = list(TSC.Pager(server.views))
            for item in items:
                if hasattr(item, 'workbook') and item.workbook.project_id == project_id:
                    path = os.path.join(dirs['views'], f"{sanitize(item.name)}.tvc")
                    try:
                        view_data = {
                            'name': item.name,
                            'workbook_name': item.workbook.name,
                            'owner_name': item.owner.name if hasattr(item, 'owner') else None,
                            'view_data': item._view_data if hasattr(item, '_view_data') else None
                        }
                        downloaded_files.append((view_data, path, 'custom_view'))
                        st.success(f"✅ Captured custom view: {item.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to capture custom view {item.name}: {str(e)}")
    except Exception as e:
        st.error(f"❌ Error getting {content_type} list: {str(e)}")
    
    return downloaded_files

# --------------------------
# Content Publishing Functions
# --------------------------
def publish_datasource(server: TSC.Server, ds_item: TSC.DatasourceItem, file_path: str, project_id: str) -> TSC.DatasourceItem:
    """Publish a datasource to Tableau Server."""
    try:
        new_item = TSC.DatasourceItem(name=ds_item.name, project_id=project_id)
        published_ds = server.datasources.publish(
            new_item,
            file_path,
            mode=TSC.Server.PublishMode.Overwrite,
            as_job=False
        )
        
        # Verify publication
        if published_ds:
            st.success(f"✅ Published datasource: {ds_item.name}")
            return published_ds
        else:
            st.error(f"❌ Failed to verify publication of {ds_item.name}")
            return None
    except Exception as e:
        st.error(f"❌ Failed to publish datasource {ds_item.name}: {str(e)}")
        return None

def publish_workbook(server: TSC.Server, wb_item: TSC.WorkbookItem, file_path: str, project_id: str) -> TSC.WorkbookItem:
    """Publish a workbook to Tableau Server."""
    try:
        new_item = TSC.WorkbookItem(name=wb_item.name, project_id=project_id)
        published_wb = server.workbooks.publish(
            new_item,
            file_path,
            mode=TSC.Server.PublishMode.Overwrite,
            as_job=False
            # Removed include_extract as it's not supported in newer versions
        )
        
        # Verify publication
        if published_wb:
            st.success(f"✅ Published workbook: {wb_item.name}")
            return published_wb
        else:
            st.error(f"❌ Failed to verify publication of {wb_item.name}")
            return None
    except Exception as e:
        st.error(f"❌ Failed to publish workbook {wb_item.name}: {str(e)}")
        if "failed to establish a connection" in str(e).lower():
            st.warning("⚠️ This workbook may reference datasources that weren't migrated successfully")
            st.warning("Try publishing the dependent datasources first or check connection settings")
        return None

def publish_content_in_sequence(
    src_server: TSC.Server,
    dest_server: TSC.Server,
    downloaded_items: List,
    dest_project_id: str,
    migrate_schedules: bool,
    user_map: Dict[str, TSC.UserItem]
) -> None:
    """Publish content in proper sequence (datasources first, then workbooks)."""
    # Separate content types
    datasources = [item for item in downloaded_items if item[2] == 'datasource']
    workbooks = [item for item in downloaded_items if item[2] == 'workbook']
    
    published_ds = {}
    published_wb = {}
    
    # Publish all datasources first
    st.subheader("📊 Publishing Data Sources")
    for ds_item, path, _ in datasources:
        published_datasource = publish_datasource(dest_server, ds_item, path, dest_project_id)
        if published_datasource:
            published_ds[ds_item.name] = published_datasource
            
            # Migrate permissions
            try:
                src_server.datasources.populate_permissions(ds_item)
                migrate_permissions(src_server, ds_item, dest_server, published_datasource, 'datasource', user_map)
            except Exception as e:
                st.error(f"❌ Failed to migrate permissions for datasource {ds_item.name}: {str(e)}")
            
            # Migrate schedules if enabled
            if migrate_schedules:
                try:
                    migrate_extract_schedules(
                        src_server, 
                        dest_server, 
                        ds_item, 
                        published_datasource, 
                        'datasource', 
                        dest_project_id
                    )
                except Exception as e:
                    st.error(f"❌ Failed to migrate schedules for datasource {ds_item.name}: {str(e)}")
            
            time.sleep(2)  # Delay to avoid rate limiting
    
    # Publish workbooks after datasources are available
    st.subheader("📚 Publishing Workbooks")
    for wb_item, path, _ in workbooks:
        published_workbook = publish_workbook(dest_server, wb_item, path, dest_project_id)
        if published_workbook:
            published_wb[wb_item.name] = published_workbook
            
            # Migrate permissions
            try:
                src_server.workbooks.populate_permissions(wb_item)
                migrate_permissions(src_server, wb_item, dest_server, published_workbook, 'workbook', user_map)
            except Exception as e:
                st.error(f"❌ Failed to migrate permissions for workbook {wb_item.name}: {str(e)}")
            
            # Migrate schedules if enabled
            if migrate_schedules:
                try:
                    migrate_extract_schedules(
                        src_server, 
                        dest_server, 
                        wb_item, 
                        published_workbook, 
                        'workbook', 
                        dest_project_id
                    )
                except Exception as e:
                    st.error(f"❌ Failed to migrate schedules for workbook {wb_item.name}: {str(e)}")
            
            time.sleep(2)  # Delay to avoid rate limiting

# --------------------------
# Main Application
# --------------------------
def main():
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
        
        st.subheader("👥 User and Group Migration")
        migrate_users_groups = st.checkbox("Enable User and Group Migration", value=True)
        
        if migrate_users_groups:
            col5, col6 = st.columns(2)
            with col5:
                migrate_users_flag = st.checkbox("Migrate Users", value=True)
            with col6:
                migrate_groups_flag = st.checkbox("Migrate Groups", value=True)
        
        st.subheader("📦 Content to Migrate")
        content_types = st.multiselect(
            "Select content types to migrate",
            ["Workbooks", "Data Sources", "Custom Views", "Subscriptions"],
            default=["Workbooks", "Data Sources"]
        )
        
        st.subheader("⏱️ Extract Refresh Settings")
        migrate_schedules_flag = st.checkbox(
            "Migrate extract refresh schedules", 
            value=True,
            help="Enable to migrate extract refresh schedules along with content"
        )
        
        submitted = st.form_submit_button("🚀 Start Migration")

    if submitted:
        try:
            # Validate inputs
            if not all([src_server_url, dest_server_url, src_project_name, dest_project_name]):
                st.error("Please fill in all required fields")
                return
            
            if not content_types:
                st.error("Please select at least one content type to migrate")
                return
            
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
                try:
                    projects = list(TSC.Pager(src_server.projects))
                    src_project = next((p for p in projects if p.name == src_project_name), None)
                    
                    if not src_project:
                        st.error(f"❌ Source project '{src_project_name}' not found")
                        return
                except Exception as e:
                    st.error(f"❌ Failed to get source project: {str(e)}")
                    return
                
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
                    
                    # Migrate users and groups first if enabled
                    user_map = {}
                    if migrate_users_groups and migrate_users_flag:
                        try:
                            user_map = migrate_users(src_server, dest_server)
                        except Exception as e:
                            st.error(f"❌ User migration failed: {str(e)}")
                            if "continue without users" not in st.session_state:
                                if st.button("Continue without user migration?"):
                                    st.session_state["continue without users"] = True
                                return
                    
                    if migrate_users_groups and migrate_groups_flag and user_map:
                        try:
                            group_map = migrate_groups(src_server, dest_server, user_map)
                        except Exception as e:
                            st.error(f"❌ Group migration failed: {str(e)}")
                            if "continue without groups" not in st.session_state:
                                if st.button("Continue without group migration?"):
                                    st.session_state["continue without groups"] = True
                                return
                    
                    # Get or create destination project
                    try:
                        dest_project = get_or_create_project(dest_server, dest_project_name)
                    except Exception as e:
                        st.error(f"❌ Failed to setup destination project: {str(e)}")
                        return
                    
                    # Download content in proper sequence
                    downloaded_items = []
                    
                    if "Data Sources" in content_types:
                        st.subheader("📥 Downloading Data Sources")
                        try:
                            ds_items = download_content(src_server, src_project.id, src_project_name, "datasource")
                            downloaded_items.extend(ds_items)
                        except Exception as e:
                            st.error(f"❌ Failed to download datasources: {str(e)}")
                            if "continue without datasources" not in st.session_state:
                                if st.button("Continue without datasources?"):
                                    st.session_state["continue without datasources"] = True
                                return
                    
                    if "Workbooks" in content_types:
                        st.subheader("📥 Downloading Workbooks")
                        try:
                            wb_items = download_content(src_server, src_project.id, src_project_name, "workbook")
                            downloaded_items.extend(wb_items)
                        except Exception as e:
                            st.error(f"❌ Failed to download workbooks: {str(e)}")
                            if "continue without workbooks" not in st.session_state:
                                if st.button("Continue without workbooks?"):
                                    st.session_state["continue without workbooks"] = True
                                return
                    
                    if "Custom Views" in content_types:
                        st.subheader("📥 Capturing Custom Views")
                        try:
                            view_items = download_content(src_server, src_project.id, src_project_name, "custom_view")
                            downloaded_items.extend(view_items)
                        except Exception as e:
                            st.error(f"❌ Failed to capture custom views: {str(e)}")
                    
                    # Publish content in proper sequence (datasources first)
                    if downloaded_items:
                        try:
                            publish_content_in_sequence(
                                src_server,
                                dest_server,
                                downloaded_items,
                                dest_project.id,
                                migrate_schedules_flag,
                                user_map
                            )
                            st.balloons()
                            st.success("🎉 Migration completed successfully!")
                        except Exception as e:
                            st.error(f"❌ Failed during content publishing: {str(e)}")
                    else:
                        st.warning("⚠️ No content was downloaded for migration")
        
        except Exception as e:
            st.error(f"❌ Migration failed: {str(e)}")
            logger.exception("Migration error")

    st.markdown("""
        <style>
        .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
        </style>
        <div class="footer">Developed by <strong>Mohd Sajjad</strong></div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
