import streamlit as st
import tableauserverclient as TSC
import pandas as pd
from io import BytesIO
from datetime import datetime

# ------------------------
# App Header
# ------------------------
st.set_page_config(page_title="Tableau Export/Import Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World CLT</h1>", unsafe_allow_html=True)
st.markdown("#### 🔐 Connect to Tableau Server / Cloud to Export or Import Content")
st.markdown("---")

# ------------------------
# Mode Selection
# ------------------------
mode = st.radio("📁 Select Mode", ["Export Tableau Content", "Import Users & Groups", "Convert User Excel to User CSV"])
st.markdown("---")

# ------------------------
# Connection Details (Only show for Export/Import modes)
# ------------------------
if mode in ["Export Tableau Content", "Import Users & Groups"]:
    st.subheader("🖥️ Tableau Connection Details")
    server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
    site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")
    auth_method = st.selectbox("🔑 Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])
    st.markdown("---")

# ------------------------
# Helper: Excel Download Function with datetime handling
# ------------------------
def to_excel_download(data: list, headers: list, filename: str, label: str):
    df = pd.DataFrame(data, columns=headers)
    
    # Convert timezone-aware datetimes to naive (timezone-unaware)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.tz_localize(None)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    output.seek(0)
    st.download_button(label=label, data=output, file_name=filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ------------------------
# Export Functions (Updated with proper datetime handling)
# ------------------------
def export_users(server):
    users, _ = server.users.get()
    data = [[u.name, u.fullname, u.email, u.site_role, 
             u.last_login.replace(tzinfo=None) if u.last_login else None] 
            for u in users]
    headers = ["Name", "Full Name", "Email", "Site Role", "Last Login"]
    to_excel_download(data, headers, "users.xlsx", "⬇️ Download Users (Excel)")

def export_groups(server):
    groups, _ = server.groups.get()
    data = [[g.name, g.id] for g in groups]
    headers = ["Group Name", "Group ID"]
    to_excel_download(data, headers, "groups.xlsx", "⬇️ Download Groups (Excel)")

def export_projects(server):
    projects, _ = server.projects.get()
    data = [[p.name, p.description, p.content_permissions] for p in projects]
    headers = ["Name", "Description", "Content Permissions"]
    to_excel_download(data, headers, "projects.xlsx", "⬇️ Download Projects (Excel)")

def export_workbooks(server):
    workbooks, _ = server.workbooks.get()
    data = [[w.name, w.owner_id, w.project_name, 
             w.created_at.replace(tzinfo=None) if w.created_at else None,
             w.updated_at.replace(tzinfo=None) if w.updated_at else None] 
            for w in workbooks]
    headers = ["Workbook Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_excel_download(data, headers, "workbooks.xlsx", "⬇️ Download Workbooks (Excel)")

def export_datasources(server):
    datasources, _ = server.datasources.get()
    data = [[d.name, d.owner_id, d.project_name, 
             d.created_at.replace(tzinfo=None) if d.created_at else None,
             d.updated_at.replace(tzinfo=None) if d.updated_at else None] 
            for d in datasources]
    headers = ["Datasource Name", "Owner ID", "Project", "Created At", "Updated At"]
    to_excel_download(data, headers, "datasources.xlsx", "⬇️ Download Datasources (Excel)")

# [Rest of the code remains the same...]
