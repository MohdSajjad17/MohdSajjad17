import streamlit as st
import tableauserverclient as TSC
import pandas as pd

# Page setup
st.set_page_config(page_title="Tableau Migration Tool", layout="wide")
st.markdown("<h1 style='text-align: center; color: #4B8BBE;'>🔁 Welcome to Migration World</h1>", unsafe_allow_html=True)
st.markdown("""
    <style>
    .footer { text-align: center; margin-top: 40px; color: #888; font-size: 16px; }
    </style>
    <div class="footer">Developed with ❤️ by <strong>Mohd Sajjad</strong></div>
""", unsafe_allow_html=True)

# Auth helpers
def get_auth(method, token_name, token_value, username, password, site):
    if method == "PAT":
        return TSC.PersonalAccessTokenAuth(token_name, token_value, site_id=site)
    else:
        return TSC.TableauAuth(username, password, site_id=site)

def get_server(url):
    return TSC.Server(url, use_server_version=True)

# Export users
def export_users(server):
    users, _ = server.users.get()
    user_data = [{
        "Username": user.name,
        "FullName": user.fullname or "",
        "Email": user.email or "",
        "SiteRole": user.site_role
    } for user in users]
    return pd.DataFrame(user_data)

# Export groups and members (fixed method)
def export_groups(server):
    groups, _ = server.groups.get()
    rows = []

    for group in groups:
        try:
            server.groups.populate(group)  # Fetch users in the group
            if hasattr(group, 'users') and group.users:
                for user in group.users:
                    rows.append([group.name, user.name])
            else:
                # Group with no users
                rows.append([group.name, ""])
        except Exception as e:
            st.error(f"Failed to get users for group {group.name}: {e}")

    df = pd.DataFrame(rows, columns=["Group Name", "Username"])
    return df

# Import users to destination server
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
            st.success(f"User created: {row['Username']}")
        except Exception as e:
            st.error(f"Failed to add user {row['Username']}: {e}")

# Import groups and members to destination server
def import_groups_and_members(server, group_file):
    df = pd.read_csv(group_file)
    groups_map = {}

    # Create groups first
    for group_name in df["Group Name"].unique():
        try:
            group_item = TSC.GroupItem(name=group_name)
            created_group = server.groups.create(group_item)
            groups_map[group_name] = created_group.id
            st.success(f"Group created: {group_name}")
        except Exception as e:
            st.error(f"Failed to create group {group_name}: {e}")

    # Map existing users on destination by username
    users, _ = server.users.get()
    users_dict = {u.name: u.id for u in users}

    # Add users to groups
    for _, row in df.iterrows():
        try:
            user_id = users_dict.get(row["Username"])
            group_id = groups_map.get(row["Group Name"])
            if group_id and user_id:
                server.groups.add_user(group_id, user_id)
                st.info(f"Added {row['Username']} to {row['Group Name']}")
            else:
                st.warning(f"User or group not found for {row['Username']} / {row['Group Name']}")
        except Exception as e:
            st.error(f"Failed to add {row['Username']} to group: {e}")

# ----------------- Streamlit UI --------------------

with st.form("migration_form"):

    st.subheader("🔐 Source Tableau Server")
    src_url = st.text_input("Source Server URL")
    src_site = st.text_input("Source Site Content URL")
    src_auth_method = st.selectbox("Source Auth Method", ["PAT", "Username & Password"], key="src_auth")
    if src_auth_method == "PAT":
        src_token_name = st.text_input("Source PAT Name")
        src_token_secret = st.text_input("Source PAT Secret", type="password")
        src_username = src_password = None
    else:
        src_username = st.text_input("Source Username")
        src_password = st.text_input("Source Password", type="password")
        src_token_name = src_token_secret = None

    st.subheader("🔐 Destination Tableau Server")
    dest_url = st.text_input("Destination Server URL")
    dest_site = st.text_input("Destination Site Content URL")
    dest_auth_method = st.selectbox("Destination Auth Method", ["PAT", "Username & Password"], key="dest_auth")
    if dest_auth_method == "PAT":
        dest_token_name = st.text_input("Destination PAT Name")
        dest_token_secret = st.text_input("Destination PAT Secret", type="password")
        dest_username = dest_password = None
    else:
        dest_username = st.text_input("Destination Username")
        dest_password = st.text_input("Destination Password", type="password")
        dest_token_name = dest_token_secret = None

    st.markdown("---")
    st.subheader("📂 Export and Download Users and Groups CSV")

    export_btn = st.form_submit_button("Export Users and Groups")
    if export_btn:
        try:
            src_auth = get_auth(src_auth_method, src_token_name, src_token_secret, src_username, src_password, src_site)
            src_server = get_server(src_url)
            with src_server.auth.sign_in(src_auth):
                users_df = export_users(src_server)
                groups_df = export_groups(src_server)

                st.success("Export successful!")

                st.download_button("⬇️ Download Users CSV", users_df.to_csv(index=False).encode('utf-8'), "users_export.csv", "text/csv")
                st.download_button("⬇️ Download Groups with Users CSV", groups_df.to_csv(index=False).encode('utf-8'), "groups_export.csv", "text/csv")
        except Exception as e:
            st.error(f"Export failed: {e}")

    st.markdown("---")
    st.subheader("📂 Upload Exported CSV Files to Import on Destination")

    user_file = st.file_uploader("Upload Exported Users CSV", type=["csv"])
    group_file = st.file_uploader("Upload Exported Groups CSV", type=["csv"])

    migrate_btn = st.form_submit_button("Migrate Users and Groups")
    if migrate_btn:
        try:
            dest_auth = get_auth(dest_auth_method, dest_token_name, dest_token_secret, dest_username, dest_password, dest_site)
            dest_server = get_server(dest_url)
            with dest_server.auth.sign_in(dest_auth):
                if user_file is not None:
                    import_users(dest_server, user_file)
                if group_file is not None:
                    import_groups_and_members(dest_server, group_file)
                st.success("Migration completed!")
        except Exception as e:
            st.error(f"Migration failed: {e}")
