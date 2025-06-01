import streamlit as st
import tableauserverclient as TSC
import os
import re
import time
import logging
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

def get_auth(method: str, token_name: str, token_value: str, 
             username: str, password: str, site: str) -> TSC.Auth:
    """Authenticate to Tableau Server."""
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    return TSC.TableauAuth(username, password, site_id=site)

def get_server(url: str) -> TSC.Server:
    """Initialize Tableau Server client with proper settings."""
    server = TSC.Server(url, use_server_version=True)
    server.add_http_options({'verify': False})  # Disable SSL verification if needed
    server.add_http_options({'timeout': 300})  # Increase timeout for large operations
    return server

def get_or_create_project(server: TSC.Server, project_name: str, 
                         parent_project_id: Optional[str] = None) -> TSC.ProjectItem:
    """Get or create a project on the destination server."""
    try:
        all_projects = list(TSC.Pager(server.projects))
        project = next((p for p in all_projects if p.name == project_name), None)
        
        if not project:
            new_project = TSC.ProjectItem(
                name=project_name, 
                content_permissions="ManagedByOwner",
                description=f"Migrated project - {time.strftime('%Y-%m-%d')}"
            )
            if parent_project_id:
                new_project.parent_id = parent_project_id
            project = server.projects.create(new_project)
            logger.info(f"Created new project: {project_name}")
        else:
            logger.info(f"Using existing project: {project_name}")
        
        return project
    except Exception as e:
        logger.error(f"Failed to get/create project {project_name}: {str(e)}")
        raise

# --------------------------
# Content Download Functions
# --------------------------
def download_content(server: TSC.Server, project_id: str, project_name: str, 
                    content_type: str) -> List[Tuple]:
    """Download content (workbooks/datasources) from Tableau Server."""
    dirs = create_local_dirs(project_name)
    downloaded_files = []
    content_map = {
        "workbook": (server.workbooks, "twbx", "workbook"),
        "datasource": (server.datasources, "tdsx", "datasource"),
        "custom_view": (server.views, "tvc", "custom_view")
    }
    
    if content_type not in content_map:
        raise ValueError(f"Unsupported content type: {content_type}")
    
    endpoint, extension, item_type = content_map[content_type]
    
    try:
        items = list(TSC.Pager(endpoint))
        for item in items:
            if (content_type != "custom_view" and item.project_id == project_id) or \
               (content_type == "custom_view" and hasattr(item, 'workbook') and item.workbook.project_id == project_id):
                
                if content_type == "custom_view":
                    path = os.path.join(dirs['views'], f"{sanitize(item.name)}.{extension}")
                    view_data = {
                        'name': item.name,
                        'workbook_name': item.workbook.name,
                        'owner_name': item.owner.name if hasattr(item, 'owner') else None,
                        'view_data': item._view_data if hasattr(item, '_view_data') else None
                    }
                    downloaded_files.append((view_data, path, item_type))
                    logger.info(f"Captured custom view: {item.name}")
                    continue
                
                path = os.path.join(dirs[item_type + 's'], f"{sanitize(item.name)}.{extension}")
                try:
                    if content_type == "workbook":
                        file_path = endpoint.download(item.id, filepath=path, include_extract=True)
                    else:
                        file_path = endpoint.download(item.id, filepath=path, include_extract=True)
                    
                    if os.path.exists(file_path):
                        downloaded_files.append((item, file_path, item_type))
                        logger.info(f"Downloaded {item_type}: {item.name}")
                    else:
                        logger.error(f"{item_type.capitalize()} not saved: {item.name}")
                except Exception as e:
                    logger.error(f"Failed to download {item_type} {item.name}: {str(e)}")
                    continue
    
    except Exception as e:
        logger.error(f"Error getting {item_type} list: {str(e)}")
        raise
    
    return downloaded_files

# --------------------------
# Content Publishing Functions
# --------------------------
def publish_datasource(server: TSC.Server, ds_item: TSC.DatasourceItem, 
                      file_path: str, project_id: str) -> Optional[TSC.DatasourceItem]:
    """Publish a datasource to Tableau Server with error handling."""
    try:
        new_item = TSC.DatasourceItem(
            name=ds_item.name, 
            project_id=project_id,
            description=getattr(ds_item, 'description', None) or f"Migrated on {time.strftime('%Y-%m-%d')}"
        )
        
        published_ds = server.datasources.publish(
            new_item,
            file_path,
            mode=TSC.Server.PublishMode.Overwrite,
            as_job=False
        )
        
        if published_ds:
            logger.info(f"Published datasource: {ds_item.name}")
            return published_ds
        
        logger.error(f"Failed to verify publication of {ds_item.name}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to publish datasource {ds_item.name}: {str(e)}")
        return None

def publish_workbook(server: TSC.Server, wb_item: TSC.WorkbookItem, 
                    file_path: str, project_id: str) -> Optional[TSC.WorkbookItem]:
    """Publish a workbook to Tableau Server with comprehensive error handling."""
    try:
        new_item = TSC.WorkbookItem(
            name=wb_item.name, 
            project_id=project_id,
            show_tabs=getattr(wb_item, 'show_tabs', False),
            description=getattr(wb_item, 'description', None) or f"Migrated on {time.strftime('%Y-%m-%d')}"
        )
        
        published_wb = server.workbooks.publish(
            new_item,
            file_path,
            mode=TSC.Server.PublishMode.Overwrite,
            as_job=False
        )
        
        if published_wb:
            logger.info(f"Published workbook: {wb_item.name}")
            return published_wb
        
        logger.error(f"Failed to verify publication of {wb_item.name}")
        return None
        
    except Exception as e:
        logger.error(f"Failed to publish workbook {wb_item.name}: {str(e)}")
        if "failed to establish a connection" in str(e).lower():
            logger.warning("This workbook may reference datasources that weren't migrated successfully")
        return None

# --------------------------
# User and Group Migration
# --------------------------
def migrate_users(src_server: TSC.Server, dest_server: TSC.Server) -> Dict[str, TSC.UserItem]:
    """Migrate users from source to destination server with comprehensive mapping."""
    logger.info("Starting user migration")
    user_map = {}
    
    try:
        src_users = list(TSC.Pager(src_server.users))
        dest_users = list(TSC.Pager(dest_server.users))
        
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
                        site_role=user.site_role,
                        email=getattr(user, 'email', None),
                        fullname=getattr(user, 'fullname', None)
                    )
                    
                    created_user = dest_server.users.add(new_user)
                    dest_user_map[user.name.lower()] = created_user
                    user_map[user.name.lower()] = created_user
                    migrated_users += 1
                    logger.info(f"Created user: {user.name}")
                except Exception as e:
                    logger.error(f"Failed to create user {user.name}: {str(e)}")
                    skipped_users += 1
            else:
                user_map[user.name.lower()] = dest_user_map[user.name.lower()]
                skipped_users += 1
                logger.info(f"User already exists: {user.name}")
        
        logger.info(f"User migration complete: {migrated_users} migrated, {skipped_users} skipped")
        return user_map
        
    except Exception as e:
        logger.error(f"User migration failed: {str(e)}")
        raise

def migrate_groups(src_server: TSC.Server, dest_server: TSC.Server, 
                  user_map: Dict[str, TSC.UserItem]) -> Dict[str, TSC.GroupItem]:
    """Migrate groups and memberships with name-based matching."""
    logger.info("Starting group migration")
    group_map = {}
    
    try:
        src_groups = list(TSC.Pager(src_server.groups))
        dest_groups = list(TSC.Pager(dest_server.groups))
        
        dest_group_map = {g.name.lower(): g for g in dest_groups}
        migrated_groups = 0
        skipped_groups = 0
        
        # Create missing groups
        for group in src_groups:
            if group.name.lower() not in dest_group_map:
                try:
                    new_group = TSC.GroupItem(group.name)
                    created_group = dest_server.groups.create(new_group)
                    dest_group_map[group.name.lower()] = created_group
                    group_map[group.name.lower()] = created_group
                    migrated_groups += 1
                    logger.info(f"Created group: {group.name}")
                except Exception as e:
                    logger.error(f"Failed to create group {group.name}: {str(e)}")
                    skipped_groups += 1
            else:
                group_map[group.name.lower()] = dest_group_map[group.name.lower()]
                skipped_groups += 1
                logger.info(f"Group already exists: {group.name}")
        
        # Populate memberships
        logger.info("Starting group membership migration")
        for group_name, group in group_map.items():
            src_group = next((g for g in src_groups if g.name.lower() == group_name), None)
            if not src_group:
                continue
                
            src_server.groups.populate_users(src_group)
            if not hasattr(src_group, 'users'):
                continue
                
            added_members = 0
            for user in src_group.users:
                if user.name.lower() in user_map:
                    try:
                        dest_server.groups.add_user(group.id, user_map[user.name.lower()].id)
                        added_members += 1
                        logger.info(f"Added user {user.name} to group {group.name}")
                    except Exception as e:
                        logger.error(f"Failed to add user {user.name} to group {group.name}: {str(e)}")
                else:
                    logger.warning(f"User not found in destination: {user.name}")
            
            logger.info(f"Added {added_members} members to group {group.name}")
        
        logger.info(f"Group migration complete: {migrated_groups} migrated, {skipped_groups} skipped")
        return group_map
        
    except Exception as e:
        logger.error(f"Group migration failed: {str(e)}")
        raise

# --------------------------
# Permission Migration
# --------------------------
def migrate_permissions(
    src_server: TSC.Server,
    src_item,
    dest_server: TSC.Server,
    dest_item,
    item_type: str,
    user_map: Dict[str, TSC.UserItem],
    group_map: Optional[Dict[str, TSC.GroupItem]] = None
) -> bool:
    """Migrate permissions with comprehensive error handling."""
    try:
        if item_type == 'workbook':
            src_server.workbooks.populate_permissions(src_item)
            permissions = src_item.permissions
        elif item_type == 'datasource':
            src_server.datasources.populate_permissions(src_item)
            permissions = src_item.permissions
        else:
            return False

        if not permissions:
            logger.info(f"No permissions to migrate for {item_type} {src_item.name}")
            return True

        new_permissions = []
        for rule in permissions:
            grantee_type = rule.grantee.tag_name
            capabilities = rule.capabilities

            if grantee_type == 'user':
                if rule.grantee.name.lower() in user_map:
                    grantee = TSC.UserItem.as_reference(user_map[rule.grantee.name.lower()].id)
                else:
                    logger.warning(f"User {rule.grantee.name} not found, skipping permission")
                    continue
            elif grantee_type == 'group':
                if group_map and rule.grantee.name.lower() in group_map:
                    grantee = TSC.GroupItem.as_reference(group_map[rule.grantee.name.lower()].id)
                else:
                    logger.warning(f"Group {rule.grantee.name} not found, skipping permission")
                    continue
            else:
                continue

            new_permissions.append(TSC.PermissionsRule(grantee=grantee, capabilities=capabilities))

        if item_type == 'workbook':
            dest_server.workbooks.update_permissions(dest_item, new_permissions)
        elif item_type == 'datasource':
            dest_server.datasources.update_permissions(dest_item, new_permissions)

        logger.info(f"Migrated permissions for {item_type} {src_item.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to migrate permissions for {item_type} {src_item.name}: {str(e)}")
        return False

# --------------------------
# Schedule Migration
# --------------------------
def migrate_extract_schedules(
    src_server: TSC.Server,
    dest_server: TSC.Server,
    src_item,
    dest_item,
    item_type: str,
    project_id: str
) -> bool:
    """Migrate extract refresh schedules with improved error handling."""
    try:
        if item_type == 'workbook':
            schedules = src_server.schedules.get_by_workbook(src_item.id)
        elif item_type == 'datasource':
            schedules = src_server.schedules.get_by_datasource(src_item.id)
        else:
            return False

        if not schedules:
            logger.info(f"No extract schedules to migrate for {item_type} {src_item.name}")
            return True

        dest_schedules = {s.name.lower(): s for s in list(TSC.Pager(dest_server.schedules))}
        created_schedules = 0

        for schedule in schedules:
            if schedule.name.lower() in dest_schedules:
                logger.info(f"Schedule {schedule.name} already exists")
                continue

            new_schedule = TSC.ScheduleItem(
                name=schedule.name,
                priority=schedule.priority,
                frequency=schedule.frequency,
                execution_order=schedule.execution_order,
                state=schedule.state
            )

            # Copy schedule details based on frequency
            freq_attr = f"{schedule.frequency.lower()}_schedule"
            if hasattr(schedule, freq_attr):
                setattr(new_schedule, freq_attr, getattr(schedule, freq_attr))

            try:
                created_schedule = dest_server.schedules.create(new_schedule)
                created_schedules += 1
                
                if item_type == 'workbook':
                    dest_server.workbooks.schedule_extract_refresh(dest_item.id, created_schedule.id)
                elif item_type == 'datasource':
                    dest_server.datasources.schedule_extract_refresh(dest_item.id, created_schedule.id)
                
                logger.info(f"Created schedule {schedule.name} for {item_type} {src_item.name}")
            except Exception as e:
                logger.error(f"Failed to create schedule {schedule.name}: {str(e)}")

        logger.info(f"Created {created_schedules} schedules for {item_type} {src_item.name}")
        return created_schedules > 0
        
    except Exception as e:
        logger.error(f"Failed to migrate schedules for {item_type} {src_item.name}: {str(e)}")
        return False
# --------------------------
# Streamlit UI Configuration
# --------------------------
def configure_streamlit_ui():
    """Set up the Streamlit page configuration."""
    st.set_page_config(
        page_title="Tableau Migration Tool",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.markdown("""
        <style>
        .main { padding-top: 2rem; }
        .stButton>button { width: 100%; }
        .stProgress > div > div > div { background-color: #4B8BBE; }
        .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Content Migration Tool</h1>", 
                unsafe_allow_html=True)

# --------------------------
# Migration Form
# --------------------------
def show_migration_form() -> Dict:
    """Display and process the migration configuration form."""
    with st.form("migration_form"):
        form_data = {}
        
        # Source Server Configuration
        st.subheader("🔐 Source Server Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            form_data['src_auth_method'] = st.radio(
                "Authentication Method", 
                ["PAT", "Username/Password"], 
                key="src_auth"
            )
            form_data['src_server_url'] = st.text_input(
                "Source Server URL", 
                help="e.g., https://server.tableau.com"
            )
            form_data['src_site'] = st.text_input(
                "Source Site ID", 
                value="", 
                help="Leave empty for default site"
            )
        
        with col2:
            if form_data['src_auth_method'] == "PAT":
                form_data['src_token_name'] = st.text_input("Source Personal Access Token Name")
                form_data['src_token_value'] = st.text_input(
                    "Source Personal Access Token Value", 
                    type="password"
                )
            else:
                form_data['src_username'] = st.text_input("Source Username")
                form_data['src_password'] = st.text_input("Source Password", type="password")
        
        # Destination Server Configuration
        st.subheader("🔐 Destination Server Configuration")
        col3, col4 = st.columns(2)
        
        with col3:
            form_data['dest_auth_method'] = st.radio(
                "Authentication Method", 
                ["PAT", "Username/Password"], 
                key="dest_auth"
            )
            form_data['dest_server_url'] = st.text_input(
                "Destination Server URL", 
                help="e.g., https://server.tableau.com"
            )
            form_data['dest_site'] = st.text_input(
                "Destination Site ID", 
                value="", 
                help="Leave empty for default site"
            )
        
        with col4:
            if form_data['dest_auth_method'] == "PAT":
                form_data['dest_token_name'] = st.text_input("Destination Personal Access Token Name")
                form_data['dest_token_value'] = st.text_input(
                    "Destination Personal Access Token Value", 
                    type="password"
                )
            else:
                form_data['dest_username'] = st.text_input("Destination Username")
                form_data['dest_password'] = st.text_input("Destination Password", type="password")
        
        # Migration Settings
        st.subheader("📂 Migration Settings")
        form_data['src_project_name'] = st.text_input(
            "Source Project Name", 
            help="Name of the project to migrate from"
        )
        form_data['dest_project_name'] = st.text_input(
            "Destination Project Name", 
            help="Name of the project to migrate to"
        )
        
        # User and Group Migration
        st.subheader("👥 User and Group Migration")
        form_data['migrate_users_groups'] = st.checkbox(
            "Enable User and Group Migration", 
            value=True
        )
        
        if form_data['migrate_users_groups']:
            col5, col6 = st.columns(2)
            with col5:
                form_data['migrate_users_flag'] = st.checkbox("Migrate Users", value=True)
            with col6:
                form_data['migrate_groups_flag'] = st.checkbox("Migrate Groups", value=True)
        
        # Content Selection
        st.subheader("📦 Content to Migrate")
        form_data['content_types'] = st.multiselect(
            "Select content types to migrate",
            ["Workbooks", "Data Sources", "Custom Views"],
            default=["Workbooks", "Data Sources"]
        )
        
        # Extract Refresh Settings
        st.subheader("⏱️ Extract Refresh Settings")
        form_data['migrate_schedules_flag'] = st.checkbox(
            "Migrate extract refresh schedules", 
            value=True,
            help="Enable to migrate extract refresh schedules along with content"
        )
        
        # Submit Button
        form_data['submitted'] = st.form_submit_button("🚀 Start Migration")
        
        return form_data

# --------------------------
# Migration Progress Tracking
# --------------------------
def track_migration_progress(step: int, total_steps: int, message: str):
    """Display migration progress with a progress bar."""
    progress = step / total_steps
    st.progress(progress)
    st.info(f"Step {step} of {total_steps}: {message}")

# --------------------------
# Main Migration Controller
# --------------------------
def execute_migration(form_data: Dict):
    """Orchestrate the entire migration process."""
    if not form_data['submitted']:
        return
    
    # Validate inputs
    required_fields = [
        'src_server_url', 'dest_server_url', 
        'src_project_name', 'dest_project_name'
    ]
    
    if not all(form_data.get(field) for field in required_fields):
        st.error("Please fill in all required fields")
        return
    
    if not form_data.get('content_types'):
        st.error("Please select at least one content type to migrate")
        return
    
    try:
        # Setup authentication
        src_auth = get_auth(
            form_data['src_auth_method'],
            form_data.get('src_token_name'),
            form_data.get('src_token_value'),
            form_data.get('src_username'),
            form_data.get('src_password'),
            form_data['src_site']
        )
        
        dest_auth = get_auth(
            form_data['dest_auth_method'],
            form_data.get('dest_token_name'),
            form_data.get('dest_token_value'),
            form_data.get('dest_username'),
            form_data.get('dest_password'),
            form_data['dest_site']
        )
        
        # Initialize servers
        src_server = get_server(form_data['src_server_url'])
        dest_server = get_server(form_data['dest_server_url'])
        
        with st.spinner("Initializing migration..."):
            # Connect to source server
            with src_server.auth.sign_in(src_auth):
                st.success("🔓 Successfully connected to source server")
                
                # Get source project
                try:
                    projects = list(TSC.Pager(src_server.projects))
                    src_project = next(
                        (p for p in projects if p.name == form_data['src_project_name']), 
                        None
                    )
                    
                    if not src_project:
                        st.error(f"❌ Source project '{form_data['src_project_name']}' not found")
                        return
                except Exception as e:
                    st.error(f"❌ Failed to get source project: {str(e)}")
                    return
                
                # Connect to destination server
                with dest_server.auth.sign_in(dest_auth):
                    st.success("🔓 Successfully connected to destination server")
                    
                    # Initialize progress tracking
                    total_steps = 3  # Base steps
                    if form_data.get('migrate_users_groups'):
                        total_steps += 2
                    if "Data Sources" in form_data['content_types']:
                        total_steps += 2
                    if "Workbooks" in form_data['content_types']:
                        total_steps += 2
                    
                    current_step = 1
                    
                    # Migrate users and groups first if enabled
                    user_map = {}
                    group_map = {}
                    
                    if form_data.get('migrate_users_groups') and form_data.get('migrate_users_flag'):
                        track_migration_progress(
                            current_step, total_steps, 
                            "Migrating users from source to destination"
                        )
                        current_step += 1
                        
                        try:
                            user_map = migrate_users(src_server, dest_server)
                            st.success("✅ User migration completed")
                        except Exception as e:
                            st.error(f"❌ User migration failed: {str(e)}")
                            if not st.checkbox("Continue without user migration?"):
                                return
                    
                    if (form_data.get('migrate_users_groups') and 
                        form_data.get('migrate_groups_flag') and 
                        user_map):
                        track_migration_progress(
                            current_step, total_steps, 
                            "Migrating groups and memberships"
                        )
                        current_step += 1
                        
                        try:
                            group_map = migrate_groups(src_server, dest_server, user_map)
                            st.success("✅ Group migration completed")
                        except Exception as e:
                            st.error(f"❌ Group migration failed: {str(e)}")
                            if not st.checkbox("Continue without group migration?"):
                                return
                    
                    # Get or create destination project
                    track_migration_progress(
                        current_step, total_steps, 
                        "Setting up destination project"
                    )
                    current_step += 1
                    
                    try:
                        dest_project = get_or_create_project(
                            dest_server, 
                            form_data['dest_project_name']
                        )
                    except Exception as e:
                        st.error(f"❌ Failed to setup destination project: {str(e)}")
                        return
                    
                    # Download and publish content
                    downloaded_items = []
                    
                    if "Data Sources" in form_data['content_types']:
                        track_migration_progress(
                            current_step, total_steps, 
                            "Downloading data sources from source"
                        )
                        current_step += 1
                        
                        try:
                            ds_items = download_content(
                                src_server, 
                                src_project.id, 
                                form_data['src_project_name'], 
                                "datasource"
                            )
                            downloaded_items.extend(ds_items)
                            st.success(f"✅ Downloaded {len(ds_items)} data sources")
                        except Exception as e:
                            st.error(f"❌ Failed to download datasources: {str(e)}")
                            if not st.checkbox("Continue without datasources?"):
                                return
                    
                    if "Workbooks" in form_data['content_types']:
                        track_migration_progress(
                            current_step, total_steps, 
                            "Downloading workbooks from source"
                        )
                        current_step += 1
                        
                        try:
                            wb_items = download_content(
                                src_server, 
                                src_project.id, 
                                form_data['src_project_name'], 
                                "workbook"
                            )
                            downloaded_items.extend(wb_items)
                            st.success(f"✅ Downloaded {len(wb_items)} workbooks")
                        except Exception as e:
                            st.error(f"❌ Failed to download workbooks: {str(e)}")
                            if not st.checkbox("Continue without workbooks?"):
                                return
                    
                    if "Custom Views" in form_data['content_types']:
                        track_migration_progress(
                            current_step, total_steps, 
                            "Capturing custom views from source"
                        )
                        current_step += 1
                        
                        try:
                            view_items = download_content(
                                src_server, 
                                src_project.id, 
                                form_data['src_project_name'], 
                                "custom_view"
                            )
                            downloaded_items.extend(view_items)
                            st.success(f"✅ Captured {len(view_items)} custom views")
                        except Exception as e:
                            st.error(f"❌ Failed to capture custom views: {str(e)}")
                    
                    # Publish content
                    if downloaded_items:
                        track_migration_progress(
                            current_step, total_steps, 
                            "Publishing content to destination"
                        )
                        current_step += 1
                        
                        try:
                            # Separate content types
                            datasources = [item for item in downloaded_items if item[2] == 'datasource']
                            workbooks = [item for item in downloaded_items if item[2] == 'workbook']
                            
                            # Publish datasources first
                            for ds_item, path, _ in datasources:
                                published_ds = publish_datasource(
                                    dest_server, 
                                    ds_item, 
                                    path, 
                                    dest_project.id
                                )
                                if published_ds:
                                    if form_data['migrate_schedules_flag']:
                                        migrate_extract_schedules(
                                            src_server, 
                                            dest_server, 
                                            ds_item, 
                                            published_ds, 
                                            'datasource', 
                                            dest_project.id
                                        )
                            
                            # Then publish workbooks
                            for wb_item, path, _ in workbooks:
                                published_wb = publish_workbook(
                                    dest_server, 
                                    wb_item, 
                                    path, 
                                    dest_project.id
                                )
                                if published_wb:
                                    if form_data['migrate_schedules_flag']:
                                        migrate_extract_schedules(
                                            src_server, 
                                            dest_server, 
                                            wb_item, 
                                            published_wb, 
                                            'workbook', 
                                            dest_project.id
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

# --------------------------
# Main Application
# --------------------------
def main():
    configure_streamlit_ui()
    form_data = show_migration_form()
    execute_migration(form_data)
    
    st.markdown("""
        <div class="footer">Developed by <strong>Mohd Sajjad</strong></div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
