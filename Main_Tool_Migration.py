import os
import tableauserverclient as TSC
import streamlit as st
import pandas as pd

# Function to handle authentication
def get_auth(auth_type, token_name, token, username, password, site):
    if auth_type == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token, site)
    else:
        return TSC.TableauAuth(username, password, site)

# Function to get the server instance
def get_server(url):
    server = TSC.Server(url)
    server.use_server_version()
    return server

# Function to download and publish content
def download_publish_content(server, project_id, project_name, content_type, file_extension, downloader, publisher):
    items = []
    for item in downloader():
        item_file = f"{item.name}{file_extension}"
        item_filepath = os.path.join("downloads", item_file)
        os.makedirs(os.path.dirname(item_filepath), exist_ok=True)
        server.content.download(item.id, item_filepath)
        items.append((item, item_filepath))
    return items

# Function to publish workbooks
def publish_workbooks(src_server, dest_server, files_and_wbs, dest_project_id, project_name):
    for workbook, file_path in files_and_wbs:
        dest_workbook = TSC.WorkbookItem(workbook.name, dest_project_id)
        dest_server.workbooks.publish(dest_workbook, file_path, TSC.Server.PublishMode.Overwrite)

# Streamlit UI
st.title("Tableau Migration Tool")
tab1, tab2 = st.tabs(["Migration", "Export/Import"])

with tab1:
    with st.form("migration_form"):
        st.subheader("🔁 Migrate Tableau Content")
        src_url = st.text_input("Source Server URL")
        src_site = st.text_input("Source Site Content URL", "")
        src_token_name = st.text_input("Source PAT Name")
        src_token = st.text_input("Source PAT Token", type="password")

        dest_url = st.text_input("Destination Server URL")
        dest_site = st.text_input("Destination Site Content URL", "")
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token = st.text_input("Destination PAT Token", type="password")

        project_name = st.text_input("Project Name for Migration")

        submitted = st.form_submit_button("Start Migration")

    if submitted:
        with st.spinner("🔁 Migrating..."):
            src_auth = get_auth("PAT", src_token_name, src_token, None, None, src_site)
            dest_auth = get_auth("PAT", dest_token_name, dest_token, None, None, dest_site)

            src_server = get_server(src_url)
            dest_server = get_server(dest_url)

            src_server.auth.sign_in(src_auth)
            dest_server.auth.sign_in(dest_auth)

            # Download and publish workbooks
            files_and_wbs = download_publish_content(
                src_server, None, project_name, "workbook", ".twbx",
                lambda: TSC.Pager(src_server.workbooks), dest_server.workbooks.publish)
            publish_workbooks(src_server, dest_server, files_and_wbs, None, project_name)

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
