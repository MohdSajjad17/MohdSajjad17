import streamlit as st
import tableauserverclient as TSC
import pandas as pd
from io import StringIO

# ------------------------
# Streamlit UI Setup
# ------------------------
st.title("🔐 Connect to Tableau Server / Cloud & Export User Inventory")

server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")

auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# ------------------------
# User Inventory Export Logic
# ------------------------
def export_user_inventory(server):
    try:
        all_users, _ = server.users.get()
        user_data = [
            {
                "Name": user.name,
                "Full Name": user.fullname,
                "Email": user.email,
                "Site Role": user.site_role,
                "Last Login": user.last_login
            }
            for user in all_users
        ]
        df = pd.DataFrame(user_data)
        csv_buffer = StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue()
    except Exception as e:
        st.error(f"❌ Failed to fetch users: {str(e)}")
        return None

# ------------------------
# Authentication Flow
# ------------------------
if auth_method == "PAT (Personal Access Token)":
    token_name = st.text_input("PAT Name")
    token_value = st.text_input("PAT Secret", type="password")

    if st.button("🔌 Connect and Export Users (PAT)"):
        try:
            tableau_auth = TSC.PersonalAccessTokenAuth(
                token_name=token_name,
                personal_access_token=token_value,
                site_id=site_content_url
            )
            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)
            st.success("✅ Connected using PAT!")

            csv_data = export_user_inventory(server)
            if csv_data:
                st.download_button(
                    label="⬇️ Download User Inventory CSV",
                    data=csv_data,
                    file_name="tableau_users.csv",
                    mime="text/csv"
                )

            server.auth.sign_out()
            st.info("🔐 Signed out successfully.")
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")

else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("🔌 Connect and Export Users (Username & Password)"):
        try:
            tableau_auth = TSC.TableauAuth(username, password, site_id=site_content_url)
            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)
            st.success("✅ Connected using Username & Password!")

            csv_data = export_user_inventory(server)
            if csv_data:
                st.download_button(
                    label="⬇️ Download User Inventory CSV",
                    data=csv_data,
                    file_name="tableau_users.csv",
                    mime="text/csv"
                )

            server.auth.sign_out()
            st.info("🔐 Signed out successfully.")
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
