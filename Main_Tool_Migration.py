import os
import tableauserverclient as TSC
import streamlit as st

def download_publish_content(server, project_id, project_name, content_type, file_extension, items_iterable, publisher):
    items = []
    os.makedirs("downloads", exist_ok=True)
    for item in items_iterable:
        item_file = f"{item.name}{file_extension}"
        item_filepath = os.path.join("downloads", item_file)
        
        # Download based on content type
        if content_type == "workbook":
            server.workbooks.download(item.id, item_filepath)
        elif content_type == "datasource":
            server.datasources.download(item.id, item_filepath)
        else:
            st.warning(f"Unsupported content type: {content_type}")
            continue
        
        items.append((item, item_filepath))
    return items

def main():
    st.title("Tableau Content Migration Tool")

    # Dummy login / server connection - Replace with your credentials and server URL
    src_server_url = st.text_input("Source Tableau Server URL", "https://your-src-server")
    src_username = st.text_input("Source Username")
    src_password = st.text_input("Source Password", type="password")

    dest_server_url = st.text_input("Destination Tableau Server URL", "https://your-dest-server")
    dest_username = st.text_input("Destination Username")
    dest_password = st.text_input("Destination Password", type="password")

    project_name = st.text_input("Project Name to Migrate", "Default")

    if st.button("Start Migration"):
        # Sign in to source server
        src_auth = TSC.TableauAuth(src_username, src_password)
        src_server = TSC.Server(src_server_url, use_server_version=True)

        # Sign in to destination server
        dest_auth = TSC.TableauAuth(dest_username, dest_password)
        dest_server = TSC.Server(dest_server_url, use_server_version=True)

        with src_server.auth.sign_in(src_auth):
            with dest_server.auth.sign_in(dest_auth):
                # Get project ID by name from source server
                all_projects, _ = src_server.projects.get()
                project_id = None
                for project in all_projects:
                    if project.name == project_name:
                        project_id = project.id
                        break
                if not project_id:
                    st.error(f"Project '{project_name}' not found on source server.")
                    return
                
                # Use Pager to get all workbooks in the source server
                all_workbooks = TSC.Pager(src_server.workbooks)
                
                st.info(f"Downloading workbooks from project '{project_name}'...")

                # Filter workbooks belonging to the project
                workbooks_in_project = [wb for wb in all_workbooks if wb.project_id == project_id]

                # Download workbooks
                files_and_wbs = []
                for wb in workbooks_in_project:
                    filename = f"{wb.name}.twbx"
                    filepath = os.path.join("downloads", filename)
                    os.makedirs("downloads", exist_ok=True)
                    src_server.workbooks.download(wb.id, filepath)
                    files_and_wbs.append((wb, filepath))
                    st.write(f"Downloaded: {wb.name}")

                st.success(f"Downloaded {len(files_and_wbs)} workbooks.")

                # Publish to destination server
                for wb, filepath in files_and_wbs:
                    new_wb = TSC.WorkbookItem(project_id)
                    new_wb = dest_server.workbooks.publish(new_wb, filepath, mode=TSC.Server.PublishMode.Overwrite)
                    st.write(f"Published workbook: {new_wb.name}")

                st.success("Migration completed!")

if __name__ == "__main__":
    main()
