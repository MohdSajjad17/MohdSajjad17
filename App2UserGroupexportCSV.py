import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import numpy as np

# ------------------------
# App Header
# ------------------------
st.set_page_config(page_title="Tableau Export/Import Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World CLT</h1>", unsafe_allow_html=True)
st.markdown("#### 🔐 Connect to Tableau Server/Cloud to Export or Import Content")
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
# Import Mode Logic (Headerless CSV)
# ------------------------
def run_import(import_type, uploaded_file, auth):
    if not uploaded_file:
        st.warning("⚠️ Please upload a CSV file before importing.")
        return

    try:
        with st.spinner("🔄 Connecting to Tableau..."):
            server = connect_to_tableau(auth)
        st.success("✅ Connected to Tableau")

        # Read CSV without headers and handle empty values
        df = pd.read_csv(uploaded_file, header=None).replace('', np.nan)
        st.write("📄 CSV Preview (first 5 rows):")
        st.dataframe(df.head(5))

        if import_type == "Users":
            st.info("ℹ️ Importing users from headerless CSV (format: name,site_role,email,full_name)")
            success_count = 0
            error_count = 0
            skipped_count = 0
            
            for index, row in df.iterrows():
                try:
                    # Skip empty rows or rows with missing required fields
                    if len(row) < 2 or pd.isna(row[0]) or pd.isna(row[1]):
                        skipped_count += 1
                        continue
                        
                    name = str(row[0]).strip()
                    site_role = str(row[1]).strip()
                    
                    # Validate site_role is not empty and is valid
                    if not site_role:
                        st.warning(f"⚠️ Row {index+1}: Skipping - site_role cannot be empty")
                        skipped_count += 1
                        continue
                    
                    # Create the user
                    new_user = TSC.UserItem(
                        name=name,
                        site_role=site_role
                    )
                    
                    # Add optional fields if they exist
                    if len(row) > 2 and not pd.isna(row[2]):  # Email
                        new_user.email = str(row[2]).strip()
                    if len(row) > 3 and not pd.isna(row[3]):  # Full name
                        new_user.full_name = str(row[3]).strip()
                    
                    server.users.add(new_user)
                    success_count += 1
                    st.success(f"Row {index+1}: Added user {name} ({site_role})")
                    
                except Exception as e:
                    error_count += 1
                    user_ref = row[0] if len(row) > 0 and not pd.isna(row[0]) else f"Row {index+1}"
                    st.warning(f"⚠️ Could not add user {user_ref}: {str(e)}")

            st.success(f"""
            ✅ User import completed!
            - Success: {success_count}
            - Failed: {error_count}
            - Skipped: {skipped_count}
            """)

        elif import_type == "Groups":
            st.info("ℹ️ Importing groups from headerless CSV (first column is group name)")
            success_count = 0
            error_count = 0
            
            for index, row in df.iterrows():
                try:
                    if len(row) == 0 or pd.isna(row[0]):
                        continue
                        
                    group_name = str(row[0]).strip()
                    if not group_name:
                        continue
                        
                    new_group = TSC.GroupItem(name=group_name)
                    server.groups.create(new_group)
                    success_count += 1
                    st.success(f"Row {index+1}: Created group {group_name}")
                except Exception as e:
                    error_count += 1
                    st.warning(f"⚠️ Row {index+1}: Could not create group: {str(e)}")

            st.success(f"""
            ✅ Group import completed!
            - Success: {success_count}
            - Failed: {error_count}
            """)

        server.auth.sign_out()
        st.info("🔐 Signed out successfully.")

    except Exception as e:
        st.error(f"❌ Import failed: {str(e)}")

# ------------------------
# Excel to CSV Conversion Logic
# ------------------------
def convert_excel_to_csv(uploaded_file):
    if not uploaded_file:
        st.warning("⚠️ Please upload an Excel file first.")
        return
    
    try:
        df = pd.read_excel(uploaded_file)
        st.write("📄 Excel Preview:", df.head())
        
        # Initialize empty list for our transformed data
        transformed_data = []
        
        # Process each row
        for _, row in df.iterrows():
            email = row.get('Email', '')  # Get email (case-sensitive)
            
            # Get site role (case-sensitive)
            site_role = row.get('Site Role', '')
            
            # Transform site role according to rules
            simplified_role = ''
            fifth_column = 'None'
            sixth_column = 'False'
            
            if 'SiteAdministratorCreator' in site_role:
                simplified_role = 'Creator'
                fifth_column = 'site'
                sixth_column = 'True'
            elif 'ExplorerCanPublish' in site_role:
                simplified_role = 'Explorer'
                sixth_column = 'True'
            elif 'Viewer' in site_role:
                simplified_role = 'Viewer'
            elif 'SiteAdministratorExplorer' in site_role:
                simplified_role = 'Explorer'
                fifth_column = 'site'
                sixth_column = 'True'
            else:
                simplified_role = site_role  # Fallback to original if no match
            
            # Add transformed row to our data
            transformed_data.append([
                email,        # 1st column: Email
                '',           # 2nd column: Empty
                '',           # 3rd column: Empty
                simplified_role,  # 4th column: Simplified role
                fifth_column,     # 5th column: 'site' or 'None'
                sixth_column       # 6th column: 'True' or 'False'
            ])
        
        # Convert to CSV without headers
        csv_data = pd.DataFrame(transformed_data).to_csv(index=False, header=False)
        
        # Create download button
        st.download_button(
            label="⬇️ Download Converted CSV",
            data=csv_data,
            file_name="converted_users.csv",
            mime="text/csv"
        )
        
        st.success("✅ Conversion complete!")
        
    except Exception as e:
        st.error(f"❌ Conversion failed: {str(e)}")

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
        uploaded_file = st.file_uploader("📤 Upload Users CSV (no headers, format: name,site_role,email,full_name)", type="csv")
        st.markdown("""
        **CSV Format Requirements:**
        - No header row
        - Columns in order: name, site_role, email (optional), full_name (optional)
        - Required fields: name and site_role
        """)
    else:
        uploaded_file = st.file_uploader("📤 Upload Groups CSV (no headers, first column is group name)", type="csv")
        st.markdown("""
        **CSV Format Requirements:**
        - No header row
        - First column contains group names
        """)

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

elif mode == "Convert User Excel to User CSV":
    st.subheader("🔄 Convert User Excel to User CSV")
    st.markdown("Upload an Excel file exported from Tableau to convert it to the required CSV format.")
    
    uploaded_file = st.file_uploader("📤 Upload Excel File", type=["xlsx", "xls"])
    
    if st.button("🔃 Convert Now"):
        convert_excel_to_csv(uploaded_file)

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
