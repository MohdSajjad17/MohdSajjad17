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
def run_import(import_type, uploaded_file, auth):
    if not uploaded_file:
        st.warning("⚠️ Please upload a CSV file before importing.")
        return

    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected to Tableau")

        df = pd.read_csv(uploaded_file)
        st.write("📄 CSV Preview:", df.head())

        if import_type == "Users":
            for _, row in df.iterrows():
                try:
                    new_user = TSC.UserItem(
                        name=row["name"],
                        site_role=row["site_role"],
                        full_name=row.get("fullname", ""),
                        email=row.get("email", "")
                    )
                    server.users.add(new_user)
                except Exception as e:
                    st.warning(f"⚠️ Could not add user {row['name']}: {e}")
            st.success("✅ All users imported!")

        elif import_type == "Groups":
            for _, row in df.iterrows():
                try:
                    new_group = TSC.GroupItem(name=row["group_name"])
                    server.groups.create(new_group)
                except Exception as e:
                    st.warning(f"⚠️ Could not create group {row['group_name']}: {e}")
            st.success("✅ All groups imported!")

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")
    except Exception as e:
        st.error(f"❌ Import failed: {str(e)}")

# ------------------------
# Mode Handling
# ------------------------
if mode == "Export Tableau Content":
    if auth_method == "PAT (Personal Access Token)":
        token_name = st.text_input("PAT Name")
        token_value = st.text_input("PAT Secret", type="password")
        if st.button("🔌 Export with PAT"):
            auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
            run_export(auth)
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("🔌 Export with Username & Password"):
            auth = TSC.TableauAuth(username, password, site_id=site_content_url)
            run_export(auth)

elif mode == "Import Users & Groups":
    st.subheader("📥 Select What to Import")
    import_type = st.selectbox("Import Type", ["Users", "Groups"])

    if import_type == "Users":
        uploaded_file = st.file_uploader("📤 Upload Users CSV", type="csv")
        st.markdown("Example: `name, fullname, email, site_role`")
    else:
        uploaded_file = st.file_uploader("📤 Upload Groups CSV", type="csv")
        st.markdown("Example: `group_name`")

    st.markdown("---")
    st.subheader("🔐 Tableau Credentials")

    if auth_method == "PAT (Personal Access Token)":
        token_name = st.text_input("PAT Name")
        token_value = st.text_input("PAT Secret", type="password")
        if st.button("🚀 Import Now"):
            auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
            run_import(import_type, uploaded_file, auth)
    else:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("🚀 Import Now"):
            auth = TSC.TableauAuth(username, password, site_id=site_content_url)
            run_import(import_type, uploaded_file, auth)

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
