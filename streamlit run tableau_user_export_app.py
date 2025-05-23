import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os

# Page settings
st.set_page_config(page_title="Tableau Export Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World</h1>", unsafe_allow_html=True)

# Auth inputs
st.subheader("🖥️ Tableau Connection Details")
server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.text_input("Site Content URL (Leave empty for Default)", "")
auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# Export selection
export_type = st.radio("Select what you want to export:", [
    "Users", "Groups", "Projects", "Datasources", "Workbooks (.twbx)"
])

# Optional: Project filter shown before login
project_filter = None
if export_type == "Workbooks (.twbx)":
    st.markdown("🎯 **Filter Workbooks by Project**")
    project_filter = st.text_input("Enter Project Name to Filter Workbooks", "")

# Auth fields
if auth_method == "PAT (Personal Access Token)":
    token_name = st.text_input("PAT Name")
    token_value = st.text_input("PAT Secret", type="password")
else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

# Helpers
def authenticate():
    if auth_method == "PAT (Personal Access Token)":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
    return TSC.TableauAuth(username, password, site_id=site_content_url)

def init_server():
    return TSC.Server(server_url, use_server_version=True)

def download_button_csv(data, headers, filename, label):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

# Connect and export
if st.button("🔌 Connect and Export"):
    if export_type == "Workbooks (.twbx)" and not project_filter:
        st.warning("Please enter a Project Name to filter the workbooks.")
    else:
        try:
            auth = authenticate()
            server = init_server()
            server.auth.sign_in(auth)
            st.success("✅ Signed in")

            if export_type == "Users":
                users, _ = server.users.get()
                data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
                headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
                download_button_csv(data, headers, "users.csv", "⬇️ Download Users")

            elif export_type == "Groups":
                groups, _ = server.groups.get()
                data = [[g.name, g.id] for g in groups]
                headers = ["Group Name", "Group ID"]
                download_button_csv(data, headers, "groups.csv", "⬇️ Download Groups")

            elif export_type == "Projects":
                projects, _ = server.projects.get()
                data = [[p.name, p.description] for p in projects]
                headers = ["Project Name", "Description"]
                download_button_csv(data, headers, "projects.csv", "⬇️ Download Projects")

            elif export_type == "Datasources":
                datasources, _ = server.datasources.get()
                data = [[d.name, d.project_name, d.owner_id] for d in datasources]
                headers = ["Datasource Name", "Project", "Owner ID"]
                download_button_csv(data, headers, "datasources.csv", "⬇️ Download Datasources")

            elif export_type == "Workbooks (.twbx)":
                workbooks, _ = server.workbooks.get()
                filtered = [w for w in workbooks if w.project_name == project_filter]

                if not filtered:
                    st.warning("No workbooks found in the specified project.")
                for workbook in filtered:
                    try:
                        file_path = f"{workbook.name}.twbx"
                        server.workbooks.download(workbook.id, filepath=file_path, include_extract=False)
                        with open(file_path, "rb") as f:
                            st.download_button(f"⬇️ Download {workbook.name}.twbx", data=f, file_name=file_path)
                        os.remove(file_path)
                    except Exception as e:
                        st.error(f"Error downloading {workbook.name}: {e}")

            server.auth.sign_out()
            st.info("🔐 Signed out.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# Footer
st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        bottom: 0;
        width: 100%;
        background-color: #f1f1f1;
        color: #333;
        text-align: center;
        padding: 10px;
        font-weight: bold;
    }
    </style>
    <div class="footer">
        Developed with ❤️ by <strong>Mohd Sajjad</strong>
    </div>
    """, unsafe_allow_html=True
)
