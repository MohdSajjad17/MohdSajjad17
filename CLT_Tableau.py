import streamlit as st
import requests
import pandas as pd

st.title("📊 Tableau Site Users Viewer")

# User inputs
server_url = st.text_input("Server URL", placeholder="https://your-server.com")
site_id = st.text_input("Site ID")
token = st.text_input("Auth Token", type="password")

if st.button("Fetch Users"):
    if not server_url or not site_id or not token:
        st.warning("Please fill in all fields.")
    else:
        headers = {
            'X-Tableau-Auth': token
        }

        page_number = 1
        page_size = 1000
        all_users = []

        with st.spinner("Fetching users..."):
            while True:
                url = f'{server_url}/api/3.22/sites/{site_id}/users?pageSize={page_size}&pageNumber={page_number}'
                response = requests.get(url, headers=headers)

                if response.status_code != 200:
                    st.error(f"Failed to fetch users: {response.status_code} - {response.text}")
                    break

                data = response.json()
                users = data['users']['user']
                all_users.extend(users)

                total_available = int(data['pagination']['totalAvailable'])
                if page_number * page_size >= total_available:
                    break
                page_number += 1

        if all_users:
            df = pd.DataFrame(all_users)
            df = df[["name", "fullName", "email", "siteRole"]]
            st.success(f"Fetched {len(df)} users.")
            st.dataframe(df)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, "tableau_users.csv", "text/csv")
