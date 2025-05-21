import streamlit as st
import requests

# -----------------------------
# Streamlit UI for Connection
# -----------------------------
st.title("Connect to Tableau Server / Cloud")

server_url = st.text_input("Tableau Server/Cloud URL", "https://YOUR-TABLEAU-SERVER")
site_content_url = st.text_input("Site Content URL", "")

auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

# Credentials Input
if auth_method == "PAT (Personal Access Token)":
    pat_name = st.text_input("PAT Name")
    pat_secret = st.text_input("PAT Secret", type="password")
    auth_payload = {
        "credentials": {
            "personalAccessTokenName": pat_name,
            "personalAccessTokenSecret": pat_secret,
            "site": {"contentUrl": site_content_url}
        }
    }
else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    auth_payload = {
        "credentials": {
            "name": username,
            "password": password,
            "site": {"contentUrl": site_content_url}
        }
    }

api_version = "3.22"

# Connection Request
if st.button("Connect to Tableau"):
    try:
        response = requests.post(
            f"{server_url}/api/{api_version}/auth/signin",
            json=auth_payload,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        token = data['credentials']['token']
        site_id = data['credentials']['site']['id']
        st.success(f"✅ Connected to Tableau Site: {site_id}")
        st.session_state['tableau_token'] = token
        st.session_state['site_id'] = site_id

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Connection failed: {e}")
