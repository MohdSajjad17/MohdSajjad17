import streamlit as st
import tableauserverclient as TSC
import pandas as pd
import os

st.set_page_config(page_title="Tableau Migration Tool", layout="centered")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🌍 Welcome to Migration World</h1>", unsafe_allow_html=True)

# 1. Tableau Login Info
st.subheader("🖥️ Tableau Server / Cloud Credentials")
server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.text_input("Site Content URL (Leave empty for Default)", "")
auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# 2. Auth input
if auth_method == "PAT (Personal Access Token)":
    token_name = st.text_input("PAT Name")
    token_value = st.text_input("PAT Secret", type="password")
else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

# Helper auth & connect
def get_auth():
    if auth_method == "PAT (Personal Access Token)":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site_content_url)
    return TSC.TableauAuth(username, password, site_id=site_content_url)

def get_server():
    return TSC.Server(server_url, use_server_version=True)

# 3. Button to sign in and fetch projects
project_list = []
if st.button("🔍 Fetch Projects"):
    try:
        auth = get_auth()
        server = get_server()
        server.auth.sign_in(auth)
        projects, _ = server.projects.get()
        project_list = sorted([p.name for p in projects])
        st.session_state["projects"] = project_list
        st.success("✅ Projects loaded successfully")
        server.auth.sign_out()
    except Exception as e:
        st.error(f"Failed to connect or fetch projects: {e}")

# 4. Select Project (dropdown)
project_filter = None
if "projects" in st.session_state:
    project_filter = st.selectbox("🎯 Choose Project", st.session_state["projects"])

# 5. Export Workbooks + Metadata + Thumbnails
if st.button("⬇️ Export Workbooks (with metadata & preview)"):
    try:
        auth = get_auth()
        server = get_server()
        server.auth.sign_in(auth)

        workbooks, _ = server.workbooks.get()
        filtered = [w for w in workbooks if w.project_name == project_filter]

        data = []
        for wb in filtered:
            preview_url = wb.preview_image_url if hasattr(wb, 'preview_image_url') else "N/A"
            data.append([
                wb.name, wb.id, wb.project_name, wb.owner_id,
                wb.webpage_url, preview_url
            ])

        df = pd.DataFrame(data, columns=[
            "Workbook Name", "Workbook ID", "Project", "Owner ID",
            "Workbook URL", "Preview Image URL"
        ])

        st.download_button(
            "📄 Download Metadata CSV",
            data=df.to_csv(index=False),
            file_name=f"{project_filter}_workbooks_metadata.csv",
            mime="text/csv"
        )

        for wb in filtered:
            try:
                file_path = f"{wb.name}.twbx"
                server.workbooks.download(wb.id, filepath=file_path)
                with open(file_path, "rb") as f:
                    st.download_button(f"📦 Download {wb.name}.twbx", f, file_name=file_path)
                os.remove(file_path)
            except Exception as e:
                st.warning(f"Couldn't download {wb.name}: {e}")

        server.auth.sign_out()
        st.success("✅ Export complete")
    except Exception as e:
        st.error(f"❌ Export error: {e}")

# 6. Placeholder for Migration Option
st.markdown("---")
st.subheader("🚀 Migration Option (Beta)")
st.info("In the next update, you’ll be able to select a **destination Tableau site** and migrate workbooks and content between environments.")

# Footer
st.markdown("""
    <style>
    .footer { position: fixed; bottom: 0; width: 100%; text-align: center; padding: 10px; font-size: 16px; color: #444; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)
