import streamlit as st
import requests
import pandas as pd

# -----------------------------
# Streamlit UI
# -----------------------------
st.title("Tableau Server / Cloud User Export Tool")

server_url = st.text_input("Tableau Server/Cloud URL", "https://YOUR-TABLEAU-SERVER")
site_content_url = st.text_input("Site Content URL (leave empty for Default site)", "")

auth_method = st.selectbox("Authentication Method", ["PAT (Personal Access Token)", "Username & Password"])

if auth_method == "PAT (Personal Access Token)":
    pat_name = st.text_input("PAT Name", type="default")
    pat_secret = st.text_input("PAT Secret", type="password")
    credentials = {
        "credentials": {
            "personalAccessTokenName": pat_name,
            "personalAccessTokenSecret": pat_secret,
            "site": {"contentUrl": site_content_url}
        }
    }
else:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    credentials = {
        "credentials": {
            "name": username,
            "password": password,
            "site": {"contentUrl": site_content_url}
        }
    }

api_version = "3.22"

if st.button("Connect and Export Users"):
    try:
        # -----------------------------
        # Sign In
        # -----------------------------
        signin_response = requests.post(
            f"{server_url}/api/{api_version}/auth/signin",
            json=credentials,
            headers={'Content-Type': 'application/json'}
        )
        signin_response.raise_for_status()
        auth_data = signin_response.json()
        token = auth_data['credentials']['token']
        site_id = auth_data['credentials']['site']['id']
        headers = {'X-Tableau-Auth': token}

        # -----------------------------
        # Fetch All Users
        # -----------------------------
        all_users = []
        page_number = 1
        page_size = 1000

        while True:
            url = f"{server_url}/api/{api_version}/sites/{site_id}/users?pageSize={page_size}&pageNumber={page_number}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            users = response.json()['users']['user']
            all_users.extend(users)
            if len(users) < page_size:
                break
            page_number += 1

        # -----------------------------
        # Sign Out
        # -----------------------------
        requests.post(f"{server_url}/api/{api_version}/auth/signout", headers=headers)

        # -----------------------------
        # Display & Export
        # -----------------------------
        df = pd.DataFrame([{
            "Username": u['name'],
            "Full Name": u.get('fullName', ''),
            "Email": u.get('email', ''),
            "Site Role": u.get('siteRole', '')
        } for u in all_users])

        st.success("Users retrieved successfully!")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download User List as CSV",
            data=csv,
            file_name='tableau_users.csv',
            mime='text/csv'
        )

    except Exception as e:
        st.error(f"Error: {str(e)}")
