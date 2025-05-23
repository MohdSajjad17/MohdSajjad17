import streamlit as st
import tableauserverclient as TSC
import os
import re

st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)

# Input Form
with st.form("migration_form"):
    st.subheader("🔐 Source Tableau Credentials")
    src_url = st.text_input("Source Server URL", "https://prod-apsoutheast-b.online.tableau.com")
    src_site = st.text_input("Source Site Content URL")
    src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"], key="src_auth")

    if src_auth_method == "PAT":
        src_token_name = st.text_input("Source PAT Name")
        src_token_secret = st.text_input("Source PAT Secret", type="password")
        src_username = src_password = None
    else:
        src_username = st.text_input("Source Username")
        src_password = st.text_input("Source Password", type="password")
        src_token_name = src_token_secret = None

    st.divider()

    st.subheader("🔐 Destination Tableau Credentials")
    dest_url = st.text_input("Destination Server URL")
    dest_site = st.text_input("Destination Site Content URL")
    dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")

    if dest_auth_method == "PAT":
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token_secret = st.text_input("Destination PAT Secret", type="password")
        dest_username = dest_password = None
    else:
        dest_username = st.text_input("Destination Username")
        dest_password = st.text_input("Destination Password", type="password")
        dest_token_name = dest_token_secret = None

    st.divider()

    st.subheader("📦 Project Mapping")
    source_proj = st.text_input("Source Project Name")
    dest_proj = st.text_input("Destination Project Name")

    submitted = st.form_submit_button("🚀 Start Migration")

# Helper Functions
def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

def sanitize_filename(name):
    # Replace invalid filename characters with underscore
    return re.sub(r'[^\w\-_\. ]', '_', name)

# Run Migration on Submit
if submitted:
    try:
        # Create a dedicated temp folder inside current working directory
        temp_folder = os.path.join(os.getcwd(), "temp_workbooks")
        os.makedirs(temp_folder, exist_ok=True)

        # Authenticate source
        src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
        src_server = get_server(src_url)
        src_server.auth.sign_in(src_auth)

        # Get source project
        src_projects, _ = src_server.projects.get()
        src_proj_obj = next((p for p in src_projects if p.name == source_proj), None)
        if not src_proj_obj:
            raise Exception(f"Source project '{source_proj}' not found.")

        # Get workbooks in source project
        src_workbooks, _ = src_server.workbooks.get()
        workbooks_to_migrate = [w for w in src_workbooks if w.project_id == src_proj_obj.id]

        if not workbooks_to_migrate:
            st.warning("⚠️ No workbooks found in source project.")

        downloaded = []
        for wb in workbooks_to_migrate:
            try:
                safe_name = sanitize_filename(wb.name)
                path = os.path.join(temp_folder, f"{safe_name}.twbx")
                src_server.workbooks.download(wb.id, filepath=path)
                downloaded.append((wb.name, path))
                st.info(f"✅ Downloaded: {wb.name}")
            except Exception as e:
                st.warning(f"❌ Failed to download {wb.name}: {e}")
        src_server.auth.sign_out()

        # Authenticate destination
        dest_auth = get_auth(dest_auth_method, dest_token_name, dest_token_secret, dest_username, dest_password, dest_site)
        dest_server = get_server(dest_url)
        dest_server.auth.sign_in(dest_auth)

        # Get destination project
        dest_projects, _ = dest_server.projects.get()
        dest_proj_obj = next((p for p in dest_projects if p.name == dest_proj), None)
        if not dest_proj_obj:
            raise Exception(f"Destination project '{dest_proj}' not found.")

        # Publish downloaded workbooks to destination
        for wb_name, path in downloaded:
            try:
                new_wb = TSC.WorkbookItem(name=wb_name, project_id=dest_proj_obj.id)
                # Open file in binary mode, pass handle and actual path
                with open(path, 'rb') as f:
                    dest_server.workbooks.publish(new_wb, path, mode=TSC.Server.PublishMode.CreateNew)
                st.success(f"📤 Published: {wb_name}")
                os.remove(path)  # Clean up downloaded file after publishing
            except Exception as e:
                st.warning(f"❌ Failed to publish {wb_name}: {e}")

        dest_server.auth.sign_out()
        st.success("🎉 Migration completed successfully!")

    except Exception as final_error:
        st.error(f"❌ Migration failed: {final_error}")

# Footer (signature)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 50px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)
