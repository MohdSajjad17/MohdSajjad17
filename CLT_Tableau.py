import streamlit as st
import tableauserverclient as TSC
import pandas as pd

# ------------------------
# App Header
# ------------------------
st.set_page_config(page_title="Tableau Export/Import Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("#### 🔐 Connect to Tableau Server / Cloud to Export or Import Content")
st.markdown("---")

# ------------------------
# Mode Selection
# ------------------------
mode = st.radio("📁 Select Mode", ["Export Tableau Content", "Import Users & Groups"])
st.markdown("---")

# ------------------------
# Connection Details
# ------------------------
st.subheader("🖥️ Tableau Connection Details")
server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")
auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])
st.markdown("---")

# ------------------------
# Helper: CSV Download Function
# ------------------------
def to_csv_download(data: list, headers: list, filename: str, label: str):
    df = pd.DataFrame(data, columns=headers)
    csv = df.to_csv(index=False)
    st.download_button(label=label, data=csv, file_name=filename, mime="text/csv")

# ------------------------
# Export Functions
# ------------------------
def export_users(server):
    users, _ = server.users.get()
    data = [[u.name, u.fullname, u.email, u.site_role, u.last_login] for u in users]
    headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
    to_csv_download(data, headers, "users.csv", "⬇️ Download Users")

def export_groups(server):
    groups, _ = server.groups.get()
    data = [[g.name, g.id] for g in groups]
    headers = ["Group Name", "Group ID"]
    to_csv_download(data, headers, "groups.csv", "⬇️ Download Groups")

def export_projects(server):
    projects, _ = server.projects.get()
    data = [[p.name, p.description, p.content_permissions] for p in projects]
    headers = ["Name", "Description", "Content Permissions"]
    to_csv_download(data, headers, "projects.csv", "⬇️ Download Projects")

def export_workbooks(server):
    workbooks, _ = server.workbooks.get()
    data = [[w.name, w.owner_id, w.project_name, w.created_at, w.updated_at] for w in workbooks]
    headers = ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_csv_download(data, headers, "workbooks.csv", "⬇️ Download Workbooks")

def export_datasources(server):
    datasources, _ = server.datasources.get()
    data = [[d.name, d.owner_id, d.project_name, d.created_at, d.updated_at] for d in datasources]
    headers = ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_csv_download(data, headers, "datasources.csv", "⬇️ Download Datasources")

# ------------------------
# Tableau Authentication & Session
# ------------------------
def connect_to_tableau(auth):
    server = TSC.Server(server_url, use_server_version=True)
    server.auth.sign_in(auth)
    return server

# ------------------------
# Export Mode Logic
# ------------------------
def run_export(auth):
    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected successfully!")

        with st.expander("📋 Export Tableau Content (click to expand)"):
            export_users(server)
            export_groups(server)
            export_projects(server)
            export_workbooks(server)
            export_datasources(server)

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")
    except Exception as e:
        st.error(f"❌ Connection failed: {str(e)}")

# ------------------------
# Import Mode Logic
# ------------------------
def run_import(auth):
    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected successfully!")

        user_csv = st.file_uploader("📤 Upload Users CSV", type="csv")
        group_csv = st.file_uploader("📤 Upload Groups CSV", type="csv")

        if user_csv:
            df_users = pd.read_csv(user_csv)
            st.write("👤 Users Preview:", df_users.head())
            if st.button("🚀 Import Users"):
                for _, row in df_users.iterrows():
                    try:
                        new_user = TSC.UserItem(name=row["name"], site_role=row["site_role"], full_name=row.get("fullname", ""), email=row.get("email", ""))
                        server.users.add(new_user)
                    except Exception as e:
                        st.warning(f"⚠️ Could not add user {row['name']}: {e}")
                st.success("✅ Users imported!")

        if group_csv:
            df_groups = pd.read_csv(group_csv)
            st.write("👥 Groups Preview:", df_groups.head())
            if st.button("🚀 Import Groups"):
                for _, row in df_groups.iterrows():
                    try:
                        new_group = TSC.GroupItem(name=row["group_name"])
                        server.groups.create(new_group)
                    except Exception as e:
                        st.warning(f"⚠️ Could not create group {row['group_name']}: {e}")
                st.success("✅ Groups imported!")

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")
    except Exception as e:
        st.error(f"❌ Import failed: {str(e)}")

# ------------------------
# Main Action
# ------------------------
if auth_method == "PAT (Personal Access Token)":
    token_name = st.text_input("PAT Name")
    token_value = st.text_input("PAT Secret", type="password")
    if st.button(f"🔌 {'Export' if mode == 'Export Tableau Content' else 'Import'} with PAT"):
        auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
        run_export(auth) if mode == "Export Tableau Content" else run_import(auth)

else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button(f"🔌 {'Export' if mode == 'Export Tableau Content' else 'Import'} with Username & Password"):
        auth = TSC.TableauAuth(username, password, site_id=site_content_url)
        run_export(auth) if mode == "Export Tableau Content" else run_import(auth)

# ------------------------
# Footer
# ------------------------
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
    }
    </style>
    <div class="footer">
        Developed with ❤️ by <strong>Mohd Sajjad</strong>
    </div>
    """,
    unsafe_allow_html=True
)
