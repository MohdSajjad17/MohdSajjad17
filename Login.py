import streamlit as st
import tableauserverclient as TSC

# ------------------------
# Streamlit UI Setup
# ------------------------
st.title("🔐 Connect to Tableau Server / Cloud")

server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")  # Tableau URL
site_content_url = st.text_input("Site Content URL (Leave empty for Default site)", "")  # Site URL (empty for default site)

auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# Input fields for Personal Access Token (PAT) or Username/Password
if auth_method == "PAT (Personal Access Token)":
    token_name = st.text_input("PAT Name")
    token_value = st.text_input("PAT Secret", type="password")

    if st.button("🔌 Connect with PAT"):
        try:
            tableau_auth = TSC.PersonalAccessTokenAuth(
                token_name=token_name,
                personal_access_token=token_value,
                site_id=site_content_url
            )
            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)
            st.success("✅ Successfully signed in using PAT!")
            server.auth.sign_out()
            st.info("🔐 Signed out successfully.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

else:  # Username & Password
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("🔌 Connect with Username & Password"):
        try:
            tableau_auth = TSC.TableauAuth(username, password, site_id=site_content_url)
            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)
            st.success("✅ Successfully signed in with Username and Password!")
            server.auth.sign_out()
            st.info("🔐 Signed out successfully.")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
