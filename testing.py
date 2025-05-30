import streamlit as st
import tableauserverclient as TSC
import os
import re
from typing import List, Dict, Optional

# ... [Previous imports and setup code remains the same] ...

def get_extract_schedules(server, content_item, item_type: str) -> List[Dict]:
    """Get extract refresh schedules for a workbook or datasource."""
    schedules = []
    try:
        if item_type == 'workbook':
            tasks = server.schedules.get_by_workbook(content_item.id)
        elif item_type == 'datasource':
            tasks = server.schedules.get_by_datasource(content_item.id)
        
        for task in tasks:
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

def create_schedule(server, schedule_config: Dict, project_id: str) -> Optional[TSC.ScheduleItem]:
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

def migrate_extract_schedules(
    src_server, 
    dest_server, 
    src_item, 
    dest_item, 
    item_type: str,
    project_id: str
):
    """Migrate extract refresh schedules from source to destination."""
    st.info(f"⏱️ Migrating extract schedules for {item_type}: {src_item.name}")
    
    # Get source schedules
    src_schedules = get_extract_schedules(src_server, src_item, item_type)
    if not src_schedules:
        st.warning(f"⚠️ No extract schedules found for {item_type} {src_item.name}")
        return
    
    # Create schedules on destination
    created_schedules = []
    for schedule in src_schedules:
        created_schedule = create_schedule(dest_server, schedule, project_id)
        if created_schedule:
            created_schedules.append(created_schedule)
            st.success(f"✅ Created schedule: {created_schedule.name}")
    
    # Assign schedules to content
    if created_schedules:
        try:
            if item_type == 'workbook':
                dest_server.workbooks.add_schedule(dest_item.id, created_schedules[0].id)
            elif item_type == 'datasource':
                dest_server.datasources.add_schedule(dest_item.id, created_schedules[0].id)
            st.success(f"🔗 Attached schedule to {item_type} {dest_item.name}")
        except Exception as e:
            st.error(f"❌ Failed to attach schedule to {item_type} {dest_item.name}: {e}")

def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id, project_name, migrate_schedules: bool):
    """Publish workbooks to the destination server with optional schedule migration."""
    for wb, path, item_type in files_and_wbs:
        st.info(f"⬆️ Publishing {item_type}: {wb.name}")
        try:
            if item_type == 'workbook':
                new_wb = TSC.WorkbookItem(name=wb.name, project_id=dest_project_id)
                published_wb = dest_server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.Overwrite)
            elif item_type == 'datasource':
                new_wb = TSC.DatasourceItem(name=wb.name, project_id=dest_project_id)
                published_wb = dest_server.datasources.publish(new_wb, path, mode=TSC.Server.PublishMode.Overwrite)
            
            st.success(f"✅ Published {item_type}: {wb.name}")
            
            # Migrate permissions
            migrate_permissions(src_server, wb, dest_server, published_wb, item_type)
            
            # Migrate extract schedules if enabled
            if migrate_schedules and item_type in ['workbook', 'datasource']:
                migrate_extract_schedules(src_server, dest_server, wb, published_wb, item_type, dest_project_id)
                
        except Exception as e:
            st.error(f"❌ Failed to publish {item_type} {wb.name}: {e}")

# ... [Previous helper functions remain the same] ...

# Update the Streamlit UI to include schedule migration option
with st.form("migration_form"):
    # ... [Previous form elements remain the same] ...
    
    st.subheader("⏱️ Extract Refresh Settings")
    migrate_schedules = st.checkbox(
        "Migrate extract refresh schedules", 
        value=True,
        help="Enable to migrate extract refresh schedules along with content"
    )
    
    submitted = st.form_submit_button("🚀 Start Migration")

if submitted:
    try:
        # ... [Previous validation and auth code remains the same] ...
        
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
            
            # Publish downloaded content with schedule migration
            if downloaded_items:
                st.subheader("🚀 Publishing Content to Destination")
                publish_content(
                    src_server, 
                    dest_server, 
                    downloaded_items, 
                    dest_project.id, 
                    "workbook",
                    migrate_schedules  # Pass the schedule migration flag
                )
            
            st.balloons()
            st.success("🎉 Migration completed successfully!")
    
    except Exception as e:
        st.error(f"❌ Migration failed: {str(e)}")

# ... [Footer remains the same] ...
