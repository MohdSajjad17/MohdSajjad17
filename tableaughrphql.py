import streamlit as st
import requests
import json
from typing import Dict, Any, Optional

class TableauGraphQLUtility:
    """
    A utility class for executing GraphQL queries against Tableau Server/Cloud using a Personal Access Token (PAT).
    """
    
    def __init__(
        self,
        server_url: str,
        pat_name: str,
        pat_value: str,
        site_id: str = '',
        api_version: str = '3.20'
    ):
        self.server_url = server_url.rstrip('/')
        self.pat_name = pat_name
        self.pat_value = pat_value
        self.site_id = site_id
        self.api_version = api_version
        self.session = requests.Session()
        self._authenticate()
        
    def _authenticate(self) -> None:
        """Authenticate with Tableau Server using PAT."""
        auth_url = f"{self.server_url}/api/{self.api_version}/auth/signin"
        payload = {
            "credentials": {
                "personalAccessTokenName": self.pat_name,
                "personalAccessTokenSecret": self.pat_value,
                "site": {
                    "contentUrl": self.site_id
                }
            }
        }
        
        try:
            response = self.session.post(
                auth_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            
            auth_data = response.json()
            self.token = auth_data['credentials']['token']
            self.site_id = auth_data['credentials']['site']['id']
            
            # Update session headers with auth token
            self.session.headers.update({
                'X-Tableau-Auth': self.token,
                'Content-Type': 'application/json'
            })
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Authentication failed: {str(e)}")
    
    def execute_graphql_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the Tableau Server.
        """
        graphql_url = f"{self.server_url}/api/{self.api_version}/graphql"
        
        payload = {'query': query}
        if variables:
            payload['variables'] = variables
        if operation_name:
            payload['operationName'] = operation_name
            
        try:
            response = self.session.post(
                graphql_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"GraphQL query failed: {str(e)}")
    
    def close(self) -> None:
        """Close the session and sign out."""
        if hasattr(self, 'token'):
            signout_url = f"{self.server_url}/api/{self.api_version}/auth/signout"
            self.session.post(signout_url)
        self.session.close()

def main():
    st.set_page_config(page_title="Tableau GraphQL Query Tool", layout="wide")
    st.title("Tableau GraphQL Query Tool")
    st.markdown("Execute GraphQL queries against your Tableau Server/Cloud instance")
    
    with st.sidebar:
        st.header("Connection Settings")
        server_url = st.text_input(
            "Tableau Server URL",
            value="https://10ax.online.tableau.com",
            help="Base URL of your Tableau Server (e.g., 'https://10ax.online.tableau.com')"
        )
        pat_name = st.text_input(
            "PAT Name",
            help="Name of your Personal Access Token"
        )
        pat_value = st.text_input(
            "PAT Value",
            type="password",
            help="Value/secret of your Personal Access Token"
        )
        site_id = st.text_input(
            "Site ID (Content URL)",
            value="",
            help="Leave empty for default site"
        )
        api_version = st.text_input(
            "API Version",
            value="3.20",
            help="Tableau REST API version to use"
        )
    
    # Query input section
    st.subheader("GraphQL Query")
    query = st.text_area(
        "Enter your GraphQL query",
        height=200,
        value="""query {
  workbooks {
    id
    name
    createdAt
    owner {
      name
    }
    project {
      name
    }
  }
}"""
    )
    
    # Variables input (optional)
    st.subheader("Query Variables (Optional)")
    variables_json = st.text_area(
        "Enter variables as JSON (if your query uses variables)",
        height=100,
        value='{\n  "workbookId": "your-workbook-id"\n}'
    )
    
    # Operation name (optional)
    operation_name = st.text_input(
        "Operation Name (if query has multiple operations)",
        value=""
    )
    
    if st.button("Execute Query"):
        if not server_url or not pat_name or not pat_value:
            st.error("Please provide all required connection details")
            return
        
        if not query:
            st.error("Please enter a GraphQL query")
            return
        
        try:
            variables = json.loads(variables_json) if variables_json.strip() else None
            
            # Initialize utility and execute query
            with st.spinner("Executing query..."):
                tableau = TableauGraphQLUtility(
                    server_url=server_url,
                    pat_name=pat_name,
                    pat_value=pat_value,
                    site_id=site_id,
                    api_version=api_version
                )
                
                result = tableau.execute_graphql_query(
                    query=query,
                    variables=variables,
                    operation_name=operation_name
                )
                
                tableau.close()
            
            # Display results
            st.success("Query executed successfully!")
            
            st.subheader("Results")
            st.json(result)
            
            # Download button for results
            st.download_button(
                label="Download Results as JSON",
                data=json.dumps(result, indent=2),
                file_name="tableau_graphql_results.json",
                mime="application/json"
            )
            
        except json.JSONDecodeError:
            st.error("Invalid JSON format for variables")
        except Exception as e:
            st.error(f"Error executing query: {str(e)}")

if __name__ == "__main__":
    main()
