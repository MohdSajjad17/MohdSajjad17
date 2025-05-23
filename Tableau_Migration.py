import streamlit as st
import tableauserverclient as TSC
import pandas as pd

# Page setup
st.set_page_config(page_title="Tableau User & Group Export", layout="wide")
st.title("🔁 Tableau User & Group Export Tool")

def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

def export_users(server):
    users, _ = server.users.get()
    user_data = [{
        "Username": user.name,
        "FullName": user.fullname or "",
        "Email": user.email or "",
        "SiteRole": user.site_role
    } for user in users]
    return pd.DataFrame(user_data)

def export_groups_and_members(server):
    groups, _ = server.groups.get()
    group_data = []

    for group in groups:
        try:
            # CORRECT USAGE: call populate on server.groups, not on group!
            server.groups.populate(group)  
            if hasattr(group, 'users') and group.users:
                for user in group.users:
                    group_data.append({
                        "GroupName": group.name,
                        "Username": user.name
                    })
            else:
                st.warning(f"Group '{group.name}' has no users.")
        except Exception as e:
            st.error(f"Failed to get users for group '{group.name}': {e}")

    return pd.DataFrame(group_data)

# UI Inputs
st.header("Source Tableau Server")

src_url = st.text_input("Source Server URL (e.g., https://your-tableau-server.com)")
src_site = st.text_input("Source Site Content URL (leave blank for default site)")
src_auth_method = st.selectbox("Authentication Method", ["PAT", "Username & Password"])

if src_auth_method == "PAT":
    src_token_name = st.text_input("Personal Access Token Name")
    src_token_secret = st.text_input("Personal Access Token Secret", type="password")
    src_username = None
    src_password = None
else:
    src_username = st.text_input("Username")
    src_password = st.text_input("Password", type="password")
    src_token_name = None
    src_token_secret = None

if st.button("Export Users and Groups"):
    try:
        src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
        server = get_server(src_url)

        with server.auth.sign_in(src_auth):
            users_df = export_users(server)
            groups_df = export_groups_and_members(server)

            st.success("Export successful!")

            users_csv = users_df.to_csv(index=False).encode('utf-8')
            groups_csv = groups_df.to_csv(index=False).encode('utf-8')

            st.download_button("Download Users CSV", users_csv, "users_export.csv", "text/csv")
            st.download_button("Download Groups CSV", groups_csv, "groups_export.csv", "text/csv")

    except Exception as e:
        st.error(f"Export failed: {e}")
