import streamlit as st
import tableauserverclient as TSC
import os
import re
import time
from typing import List, Dict, Optional, Tuple, Union

# Set up Streamlit page configuration
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Content Migration Tool</h1>", unsafe_allow_html=True)

# --------------------------
# Utility Functions
# --------------------------
def sanitize(name):
    """Sanitize names to create valid directory names."""
    return re.sub(r'[^\w\-_\. ]', '_', name)

def create_local_dirs(project_name):
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

def get_auth(method, token_name, token_value, username, password, site):
    """Authenticate to Tableau Server."""
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    """Initialize Tableau Server client."""
    server = TSC.Server(url, use_server_version=True)
    server.add_http_options({'verify': False})  # Disable SSL verification if needed
    return server

def get_or_create_project(server, project_name, parent_project_id=None):
    """Get or create a project on the destination server."""
    all_projects, _ = server.projects.get()
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

# --------------------------
# User and Group Migration Functions
# --------------------------
def migrate_users(src_server, dest_server):
    """Migrate users from source to destination server."""
    st.subheader("👤 Migrating Users")
    src_users, _ = src_server.users.get()
    dest_users, _ = dest_server.users.get()
    
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
                    fullname=user.fullname,
                    email=user.email,
                    site_role=user.site_role
                )
                created_user = dest_server.users.add(new_user)
                dest_user_map[user.name.lower()] = created_user
                st.success(f"✅ Created user: {user.name}")
                migrated_users += 1
            except Exception as e:
                st.error(f"❌ Failed to create user {user.name}: {e}")
                skipped_users += 1
        else:
            st.info(f"ℹ️ User already exists: {user.name}")
            skipped_users += 1
    
    st.info(f"ℹ️ User migration summary: {migrated_users} migrated, {skipped_users} skipped")
    return dest_user_map

def migrate_groups(src_server, dest_server, user_map):
    """Migrate groups and their memberships from source to destination server."""
    st.subheader("👥 Migrating Groups")
    src_groups, _ = src_server.groups.get()
    dest_groups, _ = dest_server.groups.get()
    
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
                st.error(f"❌ Failed to create group {group.name}: {e}")
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
                        dest_server.groups.add_user(dest_group.id, user_map[user.name.lower()].id)
                        st.success(f"✅ Added user {user.name} to group {group.name}")
                        added_members += 1
                    except Exception as e:
                        st.error(f"❌ Failed to add user {user.name} to group {group.name}: {e}")
                else:
                    st.warning(f"⚠️ User not found in destination: {user.name}")
            
            st.info(f"ℹ️ Added {added_members} members to group {group.name}")
    
    st.info(f"ℹ️ Group migration summary: {migrated_groups} migrated, {skipped_groups} skipped")
    return dest_group_map

# --------------------------
# Content Download Functions
# --------------------------
def download_content(server, project_id, project_name, content_type):
    """Download content (workbooks/datasources) from Tableau Server."""
    dirs = create_local_dirs(project_name)
    downloaded_files = []
    
    try:
        if content_type == "workbook":
            items, _ = server.workbooks.get()
            for item in items:
                if item.project_id == project_id:
                    path = os.path.join(dirs['workbooks'], f"{sanitize(item.name)}.twbx")
                    try:
                        file_path = server.workbooks.download(item.id, filepath=path, include_extract=False)
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
                        file_path = server.datasources.download(item.id, filepath=path, include_extract=False)
                        if os.path.exists(file_path):
                            downloaded_files.append((item, file_path, 'datasource'))
                            st.success(f"✅ Downloaded datasource: {item.name}")
                        else:
                            st.error(f"❌ Datasource not saved: {item.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to download datasource {item.name}: {e}")
        
        elif content_type == "custom_view":
            items, _ = server.views.get()
            for item in items:
                if hasattr(item, 'workbook') and item.workbook.project_id == project_id:
                    path = os.path.join(dirs['views'], f"{sanitize(item.name)}.tvc")
                    try:
                        # Custom views need to be downloaded with their parent workbook
                        # We'll store metadata about the view for later recreation
                        view_data = {
                            'name': item.name,
                            'workbook_name': item.workbook.name,
                            'owner_name': item.owner.name if hasattr(item, 'owner') else None,
                            'view_data': item._view_data
                        }
                        downloaded_files.append((view_data, path, 'custom_view'))
                        st.success(f"✅ Captured custom view: {item.name}")
                    except Exception as e:
                        st.error(f"❌ Failed to capture custom view {item.name}: {e}")
    except Exception as e:
        st.error(f"❌ Error getting {content_type} list: {e}")
    
    return downloaded_files

# --------------------------
# Subscription Migration
# --------------------------
def migrate_subscriptions(src_server, dest_server, src_item, dest_item, item_type, user_map):
    """Migrate subscriptions for workbooks or views."""
    try:
        if item_type == 'workbook':
            subscriptions, _ = src_server.subscriptions.get_by_workbook(src_item.id)
        elif item_type == 'view':
            subscriptions, _ = src_server.subscriptions.get_by_view(src_item.id)
        else:
            return
        
        if not subscriptions:
            st.info(f"ℹ️ No subscriptions found for {item_type} {src_item.name}")
            return
        
        st.info(f"📨 Migrating subscriptions for {item_type} {src_item.name}")
        
        for sub in subscriptions:
            try:
                # Map the user
                if sub.user.name.lower() in user_map:
                    dest_user = user_map[sub.user.name.lower()]
                else:
                    st.warning(f"⚠️ Skipping subscription - user not found: {sub.user.name}")
                    continue
                
                # Create new subscription
                new_sub = TSC.SubscriptionItem(
                    subject=sub.subject,
                    schedule_id=sub.schedule_id,  # Note: schedule must exist on destination
                    user=dest_user,
                    content=dest_item
                )
                
                # Set recipient list
                recipients = []
                for recipient in sub.recipients:
                    if recipient.name.lower() in user_map:
                        recipients.append(user_map[recipient.name.lower()])
                    else:
                        st.warning(f"⚠️ Skipping recipient {recipient.name} - user not found")
                
                if recipients:
                    new_sub.recipients = recipients
                    created_sub = dest_server.subscriptions.create(new_sub)
                    st.success(f"✅ Created subscription for {dest_user.name}")
                else:
                    st.warning("⚠️ No valid recipients found for subscription")
                
            except Exception as e:
                st.error(f"❌ Failed to migrate subscription: {e}")
                
    except Exception as e:
        st.error(f"❌ Failed to get subscriptions for {item_type} {src_item.name}: {e}")

# --------------------------
# Custom View Migration
# --------------------------
def migrate_custom_views(src_server, dest_server, src_project_id, dest_project_id, user_map):
    """Migrate custom views (personalized dashboard views)."""
    st.subheader("👀 Migrating Custom Views")
    
    try:
        # Get all views from source
        src_views, _ = src_server.views.get()
        src_views = [v for v in src_views if hasattr(v, 'workbook') and v.workbook.project_id == src_project_id]
        
        if not src_views:
            st.info("ℹ️ No custom views found in source project")
            return
        
        # Get all workbooks in destination project
        dest_workbooks, _ = dest_server.workbooks.get()
        dest_workbooks = [w for w in dest_workbooks if w.project_id == dest_project_id]
        dest_wb_map = {w.name.lower(): w for w in dest_workbooks}
        
        migrated_count = 0
        
        for view in src_views:
            try:
                # Find matching workbook in destination
                wb_name = view.workbook.name.lower()
                if wb_name not in dest_wb_map:
                    st.warning(f"⚠️ Skipping view '{view.name}' - workbook not found: {view.workbook.name}")
                    continue
                
                dest_wb = dest_wb_map[wb_name]
                
                # Get the view details
                view_details = src_server.views.get_by_id(view.id)
                src_server.views.populate_preview_image(view_details)
                
                # Create the view on destination
                new_view = TSC.ViewItem()
                new_view._preview_image = view_details._preview_image
                new_view._preview_image_content_type = view_details._preview_image_content_type
                
                # Set owner if available
                if hasattr(view, 'owner') and view.owner.name.lower() in user_map:
                    new_view.owner_id = user_map[view.owner.name.lower()].id
                
                created_view = dest_server.views.update(dest_wb.id, new_view)
                migrated_count += 1
                st.success(f"✅ Migrated view: {view.name}")
                
            except Exception as e:
                st.error(f"❌ Failed to migrate view {view.name}: {e}")
        
        st.info(f"ℹ️ Migrated {migrated_count}/{len(src_views)} custom views")
        
    except Exception as e:
        st.error(f"❌ Failed to migrate custom views: {e}")

# --------------------------
# Publish Functions with Sequencing
# --------------------------
def publish_datasources_first(src_server, dest_server, downloaded_items, dest_project_id, migrate_schedules, user_map):
    """Publish datasources first, then workbooks, with proper sequencing."""
    # Separate content types
    datasources = [item for item in downloaded_items if item[2] == 'datasource']
    workbooks = [item for item in downloaded_items if item[2] == 'workbook']
    custom_views = [item for item in downloaded_items if item[2] == 'custom_view']
    
    published_ds = {}
    published_wb = {}
    
    # Publish all datasources first
    st.subheader("📊 Publishing Data Sources")
    for ds_item, path, _ in datasources:
        try:
            new_ds = TSC.DatasourceItem(name=ds_item.name, project_id=dest_project_id)
            published_ds = dest_server.datasources.publish(
                new_ds, 
                path, 
                mode=TSC.Server.PublishMode.Overwrite
            )
            st.success(f"✅ Published datasource: {ds_item.name}")
            
            # Store published datasource reference
            published_ds[ds_item.name] = published_ds.id
            
            # Migrate permissions
            migrate_permissions(src_server, ds_item, dest_server, published_ds, 'datasource', user_map)
            
            # Migrate schedules if enabled
            if migrate_schedules:
                migrate_extract_schedules(
                    src_server, 
                    dest_server, 
                    ds_item, 
                    published_ds, 
                    'datasource', 
                    dest_project_id
                )
            
            # Migrate subscriptions
            migrate_subscriptions(src_server, dest_server, ds_item, published_ds, 'datasource', user_map)
            
            time.sleep(1)  # Small delay to avoid rate limiting
            
        except Exception as e:
            st.error(f"❌ Failed to publish datasource {ds_item.name}: {e}")
    
    # Publish workbooks after datasources are available
    st.subheader("📚 Publishing Workbooks")
    for wb_item, path, _ in workbooks:
        try:
            new_wb = TSC.WorkbookItem(name=wb_item.name, project_id=dest_project_id)
            published_wb = dest_server.workbooks.publish(
                new_wb, 
                path, 
                mode=TSC.Server.PublishMode.Overwrite,
                as_job=False  # Get immediate feedback
            )
            st.success(f"✅ Published workbook: {wb_item.name}")
            
            # Store published workbook reference
            published_wb[wb_item.name] = published_wb
            
            # Migrate permissions
            migrate_permissions(src_server, wb_item, dest_server, published_wb, 'workbook', user_map)
            
            # Migrate schedules if enabled
            if migrate_schedules:
                migrate_extract_schedules(
                    src_server, 
                    dest_server, 
                    wb_item, 
                    published_wb, 
                    'workbook', 
                    dest_project_id
                )
            
            # Migrate subscriptions
            migrate_subscriptions(src_server, dest_server, wb_item, published_wb, 'workbook', user_map)
            
            time.sleep(1)  # Small delay to avoid rate limiting
            
        except Exception as e:
            st.error(f"❌ Failed to publish workbook {wb_item.name}: {e}")
            if "Datasource not found" in str(e):
                st.warning("This workbook may reference datasources that weren't migrated successfully")
    
    # Migrate custom views after workbooks are published
    if custom_views:
        migrate_custom_views(src_server, dest_server, wb_item.project_id, dest_project_id, user_map)

# --------------------------
# Schedule Migration Functions
# --------------------------
def get_extract_schedules(server, content_item, item_type: str) -> List[Dict]:
    """Get extract refresh schedules for a workbook or datasource."""
    schedules = []
    try:
        if item_type == 'workbook':
            tasks = server.schedules.get_by_workbook(content_item.id)
        elif item_type == 'datasource':
            tasks = server.schedules.get_by_datasource(content_item.id)
        
        for task in tasks:
            if hasattr(task, 'schedule_item'):
                schedule = {
                    'id': task.id,
                    'name': task.name,
                    'priority': task.priority,
                    'frequency': task.frequency,
                    'execution_order': task.execution_order,
                    'schedule_details': {
                        'start_time': task.schedule_item.start_time,
                        'end_time': task.schedule_item.end_time,
                        'interval': task.schedule_item.interval,
                        'interval_unit': task.schedule_item.interval_unit
                    }
                }
                schedules.append(schedule)
    except Exception as e:
        st.error(f"❌ Failed to get schedules for {item_type} {content_item.name}: {e}")
    return schedules

def create_schedule(server, schedule_config: Dict) -> Optional[TSC.ScheduleItem]:
    """Create a new schedule on the destination server."""
    try:
        new_schedule = TSC.ScheduleItem(
            name=schedule_config['name'],
            priority=schedule_config['priority'],
            execution_order=schedule_config['execution_order'],
            frequency=schedule_config['frequency']
        )
        
        # Set schedule details
        details = schedule_config['schedule_details']
        new_schedule.schedule_item = TSC.ScheduleItem.Type(
            start_time=details['start_time'],
            end_time=details['end_time'],
            interval=details['interval'],
            interval_unit=details['interval_unit']
        )
        
        created_schedule = server.schedules.create(new_schedule)
        return created_schedule
    except Exception as e:
        st.error(f"❌ Failed to create schedule {schedule_config['name']}: {e}")
        return None

def migrate_extract_schedules(src_server, dest_server, src_item, dest_item, item_type, project_id):
    """Migrate extract refresh schedules from source to destination."""
    st.info(f"⏱️ Migrating extract schedules for {item_type}: {src_item.name}")
    
    # Get source schedules
    src_schedules = get_extract_schedules(src_server, src_item, item_type)
    if not src_schedules:
        st.warning(f"⚠️ No extract schedules found for {item_type} {src_item.name}")
        return
    
    # Create schedules on destination
    for schedule in src_schedules:
        created_schedule = create_schedule(dest_server, schedule)
        if created_schedule:
            st.success(f"✅ Created schedule: {created_schedule.name}")
            
            # Assign schedule to content
            try:
                if item_type == 'workbook':
                    dest_server.workbooks.add_schedule(dest_item.id, created_schedule.id)
                elif item_type == 'datasource':
                    dest_server.datasources.add_schedule(dest_item.id, created_schedule.id)
                st.success(f"🔗 Attached schedule to {item_type} {dest_item.name}")
            except Exception as e:
                st.error(f"❌ Failed to attach schedule to {item_type} {dest_item.name}: {e}")
            
            time.sleep(0.5)  # Small delay between schedule creations

# --------------------------
# Permission Migration
# --------------------------
def migrate_permissions(src_server, src_item, dest_server, dest_item, item_type, user_map):
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
        
        # Get group mappings
        src_groups, _ = src_server.groups.get()
        dest_groups, _ = dest_server.groups.get()
        
        src_group_map = {g.name.lower(): g for g in src_groups}
        dest_group_map = {g.name.lower(): g for g in dest_groups}
        
        missing_grantees = []
        
        for perm in permissions:
            grantee_ref = perm.grantee
            dest_grantee = None
            
            if grantee_ref.tag_name == 'user':
                if grantee_ref.name.lower() in user_map:
                    dest_grantee = user_map[grantee_ref.name.lower()]
                else:
                    missing_grantees.append(grantee_ref.name if hasattr(grantee_ref, 'name') else grantee_ref.id)
            
            elif grantee_ref.tag_name == 'group':
                src_group = src_group_map.get(grantee_ref.name.lower() if hasattr(grantee_ref, 'name') else '')
                if src_group and src_group.name.lower() in dest_group_map:
                    dest_grantee = dest_group_map[src_group.name.lower()]
                else:
                    missing_grantees.append(grantee_ref.name if hasattr(grantee_ref, 'name') else grantee_ref.id)
            
            if dest_grantee:
                new_perm = TSC.PermissionsRule(grantee=dest_grantee, capabilities=perm.capabilities)
                permission_manager.update_permissions(dest_item, [new_perm])
        
        if missing_grantees:
            st.warning(f"⚠️ Skipped permissions for missing users/groups in {item_type} {src_item.name}:")
            st.write(list(set(missing_grantees)))
        
        st.success(f"🔑 Permissions migrated for {item_type}: {src_item.name}")
    
    except Exception as e:
        st.error(f"❌ Failed to migrate permissions for {item_type} {src_item.name}: {e}")

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
        
        # User and Group Migration Section
        st.subheader("👥 User and Group Migration")
        migrate_users_groups = st.checkbox("Enable User and Group Migration", value=True)
        
        if migrate_users_groups:
            col5, col6 = st.columns(2)
            with col5:
                migrate_users = st.checkbox("Migrate Users", value=True)
            with col6:
                migrate_groups = st.checkbox("Migrate Groups", value=True)
        
        # Content Migration Section
        st.subheader("📦 Content to Migrate")
        content_types = st.multiselect(
            "Select content types to migrate",
            ["Workbooks", "Data Sources", "Custom Views", "Subscriptions"],
            default=["Workbooks", "Data Sources"]
        )
        
        st.subheader("⏱️ Extract Refresh Settings")
        migrate_schedules = st.checkbox(
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
                    
                    # Migrate users and groups first if enabled
                    user_map = {}
                    group_map = {}
                    if migrate_users_groups:
                        if migrate_users:
                            user_map = migrate_users(src_server, dest_server)
                        if migrate_groups and user_map:
                            group_map = migrate_groups(src_server, dest_server, user_map)
                    
                    # Get or create destination project
                    dest_project = get_or_create_project(dest_server, dest_project_name)
                    
                    # Download content in proper sequence
                    downloaded_items = []
                    
                    # Always download datasources first if selected
                    if "Data Sources" in content_types:
                        st.subheader("📥 Downloading Data Sources")
                        ds_items = download_content(src_server, src_project.id, src_project_name, "datasource")
                        downloaded_items.extend(ds_items)
                    
                    if "Workbooks" in content_types:
                        st.subheader("📥 Downloading Workbooks")
                        wb_items = download_content(src_server, src_project.id, src_project_name, "workbook")
                        downloaded_items.extend(wb_items)
                    
                    if "Custom Views" in content_types:
                        st.subheader("📥 Capturing Custom Views")
                        view_items = download_content(src_server, src_project.id, src_project_name, "custom_view")
                        downloaded_items.extend(view_items)
                    
                    # Publish content in proper sequence (datasources first)
                    if downloaded_items:
                        publish_datasources_first(
                            src_server,
                            dest_server,
                            downloaded_items,
                            dest_project.id,
                            migrate_schedules,
                            user_map
                        )
                    
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

if __name__ == "__main__":
    main()
