import tableauserverclient as TSC

# ------------------------
# Credentials
# ------------------------

# Set up your Tableau Server URL and Site
server_url = "https://prod-apsoutheast-b.online.tableau.com"  # Tableau Cloud URL or Tableau Server URL
site_content_url = ""  # Leave blank for default site (""), or set a custom site (e.g., "yoursite")

# Authentication Method (Personal Access Token or Username/Password)
auth_method = "PAT"  # Change to "Username" for Username/Password method

# Personal Access Token (if using PAT method)
token_name = "your_token_name"
token_value = "your_token_value"

# Username and Password (if using Username/Password method)
username = "your_username"
password = "your_password"

# ------------------------
# Authentication Process
# ------------------------

def login_tableau():
    if auth_method == "PAT":
        tableau_auth = TSC.PersonalAccessTokenAuth(
            token_name=token_name,
            personal_access_token=token_value,
            site_id=site_content_url
        )
    else:  # Username/Password
        tableau_auth = TSC.TableauAuth(username, password, site_id=site_content_url)

    # Create a Tableau server object
    server = TSC.Server(server_url, use_server_version=True)

    try:
        # Sign in to the server
        print("Signing in...")
        server.auth.sign_in(tableau_auth)
        print("Successfully signed in!")
        # You can perform further operations here, such as fetching data or listing sites.
        
        # Sign out after completing actions (optional)
        server.auth.sign_out()
        print("Signed out successfully.")
    except Exception as e:
        print(f"Error during sign-in: {str(e)}")

if __name__ == "__main__":
    login_tableau()
