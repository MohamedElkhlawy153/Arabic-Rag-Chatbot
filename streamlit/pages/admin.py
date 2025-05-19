import streamlit as st
import requests
from typing import Dict, Any
import os

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"
UPLOAD_ENDPOINT = f"{API_BASE_URL}/upload"
AUTH_ENDPOINT = f"{API_BASE_URL}/auth"

# Initialize session state for admin auth
if "admin_token" not in st.session_state:
    st.session_state.admin_token = None

def login_admin(username: str, password: str) -> bool:
    """Handle admin login"""
    try:
        response = requests.post(
            f"{AUTH_ENDPOINT}/login",
            json={"username": username, "password": password}
        )
        if response.status_code == 200:
            response_data = response.json()
            # The response should have both token and user details
            if "token" in response_data and "access_token" in response_data["token"]:
                st.session_state.admin_token = response_data["token"]["access_token"]
                st.session_state.admin_username = response_data["user"]["username"]
                return True
            else:
                st.error("Invalid response format from server")
                return False
        elif response.status_code == 401:
            st.error("Invalid username or password")
            return False
        else:
            st.error(f"Login failed with status code: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def upload_file(file) -> Dict[str, Any]:
    """Upload a file to the backend"""
    if not st.session_state.admin_token:
        return {"error": "Not authenticated"}
    
    try:
        files = {"file": (file.name, file.getvalue())}
        headers = {"Authorization": f"Bearer {st.session_state.admin_token}"}
        response = requests.post(
            UPLOAD_ENDPOINT,
            files=files,
            headers=headers
        )
        
        if response.status_code == 201:  # Created
            return response.json()
        elif response.status_code == 401:
            st.session_state.admin_token = None  # Clear invalid token
            return {"error": "Authentication expired. Please log in again."}
        elif response.status_code == 413:
            return {"error": "File too large. Maximum size is 25MB."}
        elif response.status_code == 415:
            return {"error": "Unsupported file type. Please upload PDF, TXT, or CSV files only."}
        else:
            return {"error": f"Upload failed: {response.json().get('detail', 'Unknown error')}"}
    except Exception as e:
        st.error(f"Failed to upload file: {str(e)}")
        return {"error": str(e)}

# Admin page layout
st.title("Admin Panel")

# Back to chat button
if st.button("Back to Chat"):
    st.switch_page("app.py")

# Authentication section
if not st.session_state.admin_token:
    st.header("Admin Login")
    with st.form("admin_login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if login_admin(username, password):
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
else:
    # Document Manager button
    if st.button("Document Manager"):
        st.switch_page("pages/document_manager.py")

    # File upload section
    st.header("Upload Documents")
    st.write("Upload documents to add them to the knowledge base.")
    st.write("Supported file types: PDF, TXT, CSV")
    st.write("Maximum file size: 25MB")
    st.write("Note: CSV files must contain 'query' and 'response' columns.")

    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt", "csv"])
    if uploaded_file:
        if st.button("Process File"):
            with st.spinner("Processing file..."):
                result = upload_file(uploaded_file)
                if "error" not in result:
                    st.success(f"File processed successfully!")
                    if result.get('chunks_added'):
                        st.info(f"Added {result['chunks_added']} chunks to the knowledge base.")
                    if result.get('detail'):
                        st.info(result['detail'])
                else:
                    st.error(f"Failed to process file: {result.get('error', 'Unknown error')}")

    # Logout button
    if st.button("Logout"):
        st.session_state.admin_token = None
        st.rerun() 