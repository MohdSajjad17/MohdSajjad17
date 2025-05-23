import streamlit as st
import tableauserverclient as TSC
import pandas as pd

# Page Config
st.set_page_config(page_title="Tableau User & Group Migration", layout="wide")
st.title("🔁 Tableau User & Group Migration Tool")

# ---------------------------
# Helper Functions
# ---------------------------

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
        "FullName": user.fullname,
        "Email": user.email or "",
        "SiteRole": user.site_role
    } for user in users]
    df = pd.DataFrame(user_data)
    return df

def export_groups_and_members(server):
    groups, _ = server.groups.get()
    group_data = []

    for group in groups:
        try:
            server.groups.populate(group)  # Correct way to get group users
            if hasattr(group, 'users'):
                for user in group.users:
                    group_data.append({
                        "GroupName": group.name,
                        "Username": user.name
                    })
            else:
                st.warning(f"⚠️ No users found in group: {group.name}")
        except Exception as e:
            st.error(f"❌ Failed to get users for group {group.name}: {e}")

    df = pd.DataFrame(group_data)
    return df

def import_users(server, user_file):
    df = pd.read_csv(user_file)
    for _, row in df.iterrows():
        try:
            user_item = TSC.UserItem(
                name=row['Username'],
                site_role=row['SiteRole'],
                full_name=row.get('FullName', '')
            )
            server.users.add(user_item)
            st.success(f"✅ User created: {row['Username']}")
        except Exception as e:
            st.error(f"❌ Failed to add user {row['Username']}: {e}")

def import_groups_and_members(server, group_file):
    df = pd.read_csv(group_file)
    groups_map = {}

    # Create groups first
    for group_name in df["GroupName"].unique():
        try:
            group_item = TSC.GroupItem(name=group_name)
            created_group = server.groups.create(group_item)
            groups_map[group_name] = created_group.id
            st.success(f"✅ Group created: {group_name}")
        except Exception as e:
            st.error(f"❌ Failed to create group {group_name}: {e}")

    # Add users to groups
    for _, row in df.iterrows():
        try:
            users, _ = server.users.get()
            user_id = None
            for u in users:
                if u.name == row["Username"]:
                    user_id = u.id
                    break
            group_id = groups_map.get(row["GroupName"])
            if group_id and user_id:
                server.groups.add_user(group_id, user_id)
                st.info(f"👥 Added {row['Username']} to {row['GroupName']}")
            else:
                st.warning(f"⚠️ Could not find user or group for {row['Username']} / {row['GroupName']}")
        except Exception as e:
            st.error(f"❌ Failed to add {row['Username']} to group: {e}")

# ---------------------------
# UI: Source Server Export
# ---------------------------
st.subheader("🔐 Source Tableau Server")
src_url = st.text_input("Source Server URL")
src_site = st.text_input("Source Site Content URL (leave blank for Default site)")
src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"], key="src_auth")

if src_auth_method == "PAT":
    src_token_name = st.text_input("Source PAT Name")
    src_token_secret = st.text_input("Source PAT Secret", type="password")
    src_username = src_password = None
else:
    src_username = st.text_input("Source Username")
    src_password = st.text_input("Source Password", type="password")
    src_token_name = src_token_secret = None

if st.button("📤 Export Users and Groups"):
    try:
        src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
        src_server = get_server(src_url)
        with src_server.auth.sign_in(src_auth):
            users_df = export_users(src_server)
            groups_df = export_groups_and_members(src_server)

            users_csv = users_df.to_csv(index=False).encode('utf-8')
            groups_csv = groups_df.to_csv(index=False).encode('utf-8')

            st.success("✅ Export successful!")

            st.download_button("⬇️ Download Users CSV", data=users_csv, file_name="users_export.csv", mime="text/csv")
            st.download_button("⬇️ Download Groups CSV", data=groups_csv, file_name="groups_export.csv", mime="text/csv")

    except Exception as e:
        st.error(f"❌ Export failed: {e}")

# ---------------------------
# UI: Destination Server Import
# ---------------------------
st.subheader("🔐 Destination Tableau Server")
dest_url = st.text_input("Destination Server URL")
dest_site = st.text_input("Destination Site Content URL (leave blank for Default site)")
dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")

if dest_auth_method == "PAT":
    dest_token_name = st.text_input("Destination PAT Name")
    dest_token_secret = st.text_input("Destination PAT Secret", type="password")
    dest_username = dest_password = None
else:
    dest_username = st.text_input("Destination Username")
    dest_password = st.text_input("Destination Password", type="password")
    dest_token_name = dest_token_secret = None

# Upload files for import
st.subheader("📥 Import Users & Groups to Destination")
user_file = st.file_uploader("Upload Exported Users CSV", type=["csv"], key="user_csv")
group_file = st.file_uploader("Upload Exported Groups CSV", type=["csv"], key="group_csv")

if st.button("🚀 Migrate Users and Groups to Destination"):
    try:
        dest_auth = get_auth(dest_auth_method, dest_token_name, dest_token_secret, dest_username, dest_password, dest_site)
        dest_server = get_server(dest_url)
        with dest_server.auth.sign_in(dest_auth):
            if user_file:
                import_users(dest_server, user_file)
            if group_file:
                import_groups_and_members(dest_server, group_file)
            st.success("✅ Migration completed.")
    except Exception as e:
        st.error(f"❌ Import failed: {e}")
