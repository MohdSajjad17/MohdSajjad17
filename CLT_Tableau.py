import streamlit as st
import tableauserverclient as TSC

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("🔐 Connect to Tableau Server / Cloud (via Tableau Server Client)")

server_url = st.text_input("Tableau Server/Cloud URL", "https://prod-apsoutheast-b.online.tableau.com")
site_content_url = st.text_input("Site Content URL (leave empty for Default site)", "zubermohd006-fa3eb7239f")

auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# Choose authentication method
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
            st.info(f"🔄 Signing in with PAT to {server_url}...")

            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)

            # Use the auth token to get the user details (alternate approach)
            users, pagination_item = server.users.get()
            user = next((u for u in users if u.id == server.auth.token), None)  # Match based on token
            server_info = server.server_info.get()

            if user:
                st.success("✅ Successfully connected!")
                st.write(f"📡 Server version: {server_info.product_version}")
                st.write(f"👤 Signed in as: {user.name} ({user.site_role})")
                st.write(f"🔐 Site ID: {server.site_id}")
            else:
                st.error("❌ User not found.")

            server.auth.sign_out()

        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")

else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("🔌 Connect with Username & Password"):
        try:
            tableau_auth = TSC.TableauAuth(username, password, site_id=site_content_url)
            st.info(f"🔄 Signing in with username to {server_url}...")

            server = TSC.Server(server_url, use_server_version=True)
            server.auth.sign_in(tableau_auth)

            # Use the auth token to get the user details (alternate approach)
            users, pagination_item = server.users.get()
            user = next((u for u in users if u.id == server.auth.token), None)  # Match based on token
            server_info = server.server_info.get()

            if user:
                st.success("✅ Successfully connected!")
                st.write(f"📡 Server version: {server_info.product_version}")
                st.write(f"👤 Signed in as: {user.name} ({user.site_role})")
                st.write(f"🔐 Site ID: {server.site_id}")
            else:
                st.error("❌ User not found.")

            server.auth.sign_out()

        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
