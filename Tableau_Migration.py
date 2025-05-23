import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os

st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Tableau Content Migration Tool</h1>", unsafe_allow_html=True)

# Sidebar for source and destination login
st.sidebar.title("🔐 Tableau Login")

auth_section = st.sidebar.radio("Choose Environment to Connect:", ["Source Site", "Destination Site"])
server_url = st.sidebar.text_input(f"{auth_section} - Tableau URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.sidebar.text_input(f"{auth_section} - Site Content URL", "")
auth_method = st.sidebar.selectbox(f"{auth_section} - Auth Method", ["PAT", "Username & Password"])

# Auth fields
if auth_method == "PAT":
    token_name = st.sidebar.text_input(f"{auth_section} - PAT Name")
    token_value = st.sidebar.text_input(f"{auth_section} - PAT Secret", type="password")
else:
    username = st.sidebar.text_input(f"{auth_section} - Username")
    password = st.sidebar.text_input(f"{auth_section} - Password", type="password")

# Auth helper
def get_auth():
    if auth_method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
    return TSC.TableauAuth(username, password, site_id=site_content_url)

def get_server():
    return TSC.Server(server_url, use_server_version=True)

# Cache projects per environment
if 'source_projects' not in st.session_state:
    st.session_state.source_projects = []
if 'destination_projects' not in st.session_state:
    st.session_state.destination_projects = []

# Project Fetch
if st.sidebar.button(f"🔍 Fetch Projects for {auth_section}"):
    try:
        auth = get_auth()
        server = get_server()
        server.auth.sign_in(auth)
        projects, _ = server.projects.get()
        names = sorted([p.name for p in projects])
        if auth_section == "Source Site":
            st.session_state.source_projects = names
        else:
            st.session_state.destination_projects = names
        st.sidebar.success(f"✅ Projects loaded for {auth_section}")
        server.auth.sign_out()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# Project mapping UI
st.subheader("🔀 Project Mapping")
if st.session_state.source_projects and st.session_state.destination_projects:
    source_proj = st.selectbox("Source Project", st.session_state.source_projects)
    dest_proj = st.selectbox("Destination Project", st.session_state.destination_projects)
    migrate_btn = st.button("🚀 Migrate Workbooks")

    if migrate_btn:
        try:
            # Login to source
            source_auth = get_auth()
            source_server = get_server()
            source_server.auth.sign_in(source_auth)

            # Get project ID from name
            projects, _ = source_server.projects.get()
            src_proj_obj = next(p for p in projects if p.name == source_proj)

            # Download workbooks from source
            workbooks, _ = source_server.workbooks.get()
            filtered = [w for w in workbooks if w.project_id == src_proj_obj.id]

            downloaded_files = []
            for wb in filtered:
                path = f"{wb.name}.twbx"
                source_server.workbooks.download(wb.id, filepath=path)
                downloaded_files.append((wb.name, path))
            source_server.auth.sign_out()

            st.success(f"✅ Downloaded {len(downloaded_files)} workbooks from source.")

            # Login to destination
            dest_auth = get_auth()
            dest_server = get_server()
            dest_server.auth.sign_in(dest_auth)

            # Get destination project ID
            projects_dest, _ = dest_server.projects.get()
            dest_proj_obj = next(p for p in projects_dest if p.name == dest_proj)

            # Publish to destination
            for wb_name, path in downloaded_files:
                new_wb = TSC.WorkbookItem(name=wb_name, project_id=dest_proj_obj.id)
                with open(path, 'rb') as f:
                    dest_server.workbooks.publish(new_wb, f.name, mode=TSC.Server.PublishMode.CreateNew)
                os.remove(path)

            dest_server.auth.sign_out()
            st.success("🎉 Migration complete!")

        except Exception as e:
            st.error(f"❌ Migration failed: {e}")
else:
    st.warning("Load projects from both sites to enable mapping.")

# Footer
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 50px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)
