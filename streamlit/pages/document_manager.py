import streamlit as st
import requests
from typing import Dict, Any, List
import json

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"
DOCUMENTS_ENDPOINT = f"{API_BASE_URL}/admin/knowledge-base/chunks"

# Initialize session state for admin auth and deletion confirmation
if "admin_token" not in st.session_state:
    st.session_state.admin_token = None
if "pending_deletion" not in st.session_state:
    st.session_state.pending_deletion = None
if "pending_chunk_deletion" not in st.session_state:
    st.session_state.pending_chunk_deletion = None
if "show_add_chunk" not in st.session_state:
    st.session_state.show_add_chunk = False

def get_all_documents() -> List[str]:
    """Get list of all unique document names"""
    try:
        headers = {"Authorization": f"Bearer {st.session_state.admin_token}"}
        # First get a small batch to check if we can connect
        response = requests.get(
            f"{DOCUMENTS_ENDPOINT}",
            params={"source_file": "", "limit": 100},  # Empty string to get all documents
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # Extract unique source files from the chunks
            source_files = set()
            for chunk in data.get("chunks", []):
                if "metadata" in chunk and "source_file" in chunk["metadata"]:
                    source_files.add(chunk["metadata"]["source_file"])
            
            # If we have more chunks, get them all
            next_offset = data.get("next_offset_id")
            while next_offset:
                response = requests.get(
                    f"{DOCUMENTS_ENDPOINT}",
                    params={"source_file": "", "limit": 100, "offset_id": next_offset},
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    for chunk in data.get("chunks", []):
                        if "metadata" in chunk and "source_file" in chunk["metadata"]:
                            source_files.add(chunk["metadata"]["source_file"])
                    next_offset = data.get("next_offset_id")
                else:
                    st.warning("Failed to get all documents, showing partial list")
                    break
            
            return sorted(list(source_files))
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to get documents: {error_msg}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return []
    except Exception as e:
        st.error(f"Error getting document list: {str(e)}")
        return []

def get_document_chunks(source_file: str) -> Dict[str, Any]:
    """Get chunks for a specific document"""
    try:
        headers = {"Authorization": f"Bearer {st.session_state.admin_token}"}
        response = requests.get(
            f"{DOCUMENTS_ENDPOINT}",
            params={"source_file": source_file, "limit": 1000},  # Get all chunks for the document
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to get chunks: {error_msg}")
            return {"chunks": [], "total_chunks": 0}
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return {"chunks": [], "total_chunks": 0}
    except Exception as e:
        st.error(f"Error getting chunks: {str(e)}")
        return {"chunks": [], "total_chunks": 0}

def update_chunk(point_id: str, new_text: str) -> bool:
    """Update a chunk's text content"""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.admin_token}",
            "Content-Type": "application/json"
        }
        response = requests.put(
            f"{DOCUMENTS_ENDPOINT}/{point_id}",
            json={"text_content": new_text},
            headers=headers
        )
        if response.status_code == 200:
            return True
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to update chunk: {error_msg}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return False
    except Exception as e:
        st.error(f"Error updating chunk: {str(e)}")
        return False

def delete_chunk(point_id: str) -> bool:
    """Delete a specific chunk"""
    try:
        headers = {"Authorization": f"Bearer {st.session_state.admin_token}"}
        response = requests.delete(
            f"{DOCUMENTS_ENDPOINT}/{point_id}",
            headers=headers
        )
        if response.status_code == 200:
            return True
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to delete chunk: {error_msg}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return False
    except Exception as e:
        st.error(f"Error deleting chunk: {str(e)}")
        return False

def delete_document(source_file: str) -> bool:
    """Delete all chunks for a specific document"""
    try:
        headers = {"Authorization": f"Bearer {st.session_state.admin_token}"}
        response = requests.delete(
            f"{DOCUMENTS_ENDPOINT}/by-file/{source_file}",
            headers=headers
        )
        if response.status_code == 200:
            return True
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to delete document: {error_msg}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return False
    except Exception as e:
        st.error(f"Error deleting document: {str(e)}")
        return False

def create_chunk(text_content: str, source_file: str) -> bool:
    """Create a new chunk manually"""
    try:
        headers = {
            "Authorization": f"Bearer {st.session_state.admin_token}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"{DOCUMENTS_ENDPOINT}/manual",
            json={
                "text_content": text_content,
                "source_file": source_file
            },
            headers=headers
        )
        if response.status_code == 201:
            return True
        else:
            error_msg = response.json().get('detail', 'Unknown error')
            st.error(f"Failed to create chunk: {error_msg}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Could not connect to the server. Please make sure the backend is running.")
        return False
    except Exception as e:
        st.error(f"Error creating chunk: {str(e)}")
        return False

# Main page layout
st.title("Document Manager")

# Back to chat button
if st.button("Back to Chat"):
    st.switch_page("app.py")

# Authentication check
if not st.session_state.admin_token:
    st.error("Please log in as admin first")
    st.stop()

# Get list of unique source files from chunks
with st.spinner("Loading documents..."):
    source_files = get_all_documents()

if not source_files:
    st.warning("No documents found in the knowledge base. Please upload some documents first.")
    st.stop()

# Document selection
selected_file = st.selectbox("Select a document", source_files)

if selected_file:
    # Add new chunk button
    if st.button("Add New Chunk"):
        st.session_state.show_add_chunk = True
    
    # Show add chunk form if button was clicked
    if st.session_state.show_add_chunk:
        st.subheader("Add New Chunk")
        new_chunk_text = st.text_area("Chunk Content", height=200)
        if st.button("Save Chunk"):
            if new_chunk_text.strip():
                if create_chunk(new_chunk_text, selected_file):
                    st.success("Chunk created successfully!")
                    st.session_state.show_add_chunk = False
                    st.rerun()
            else:
                st.error("Chunk content cannot be empty")
        if st.button("Cancel"):
            st.session_state.show_add_chunk = False
            st.rerun()
    
    # Handle document deletion
    if st.session_state.pending_deletion == selected_file:
        st.warning(f"Are you sure you want to delete all chunks for '{selected_file}'?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Delete"):
                if delete_document(selected_file):
                    st.success(f"Document '{selected_file}' deleted successfully!")
                    st.session_state.pending_deletion = None
                    st.rerun()
        with col2:
            if st.button("No, Cancel"):
                st.session_state.pending_deletion = None
                st.rerun()
    else:
        if st.button("Delete Document", type="primary"):
            st.session_state.pending_deletion = selected_file
            st.rerun()
    
    # Get chunks for selected document
    with st.spinner(f"Loading chunks for {selected_file}..."):
        chunks_data = get_document_chunks(selected_file)
    
    if chunks_data["chunks"]:
        st.subheader(f"Chunks for {selected_file}")
        
        # Display chunks with edit functionality
        for chunk in chunks_data["chunks"]:
            with st.expander(f"Chunk {chunk['metadata']['chunk_index']}"):
                # Display chunk text in a text area for editing
                new_text = st.text_area(
                    "Chunk Content",
                    value=chunk["text_content"],
                    key=f"chunk_{chunk['point_id']}"
                )
                
                # Create columns for buttons
                col1, col2 = st.columns(2)
                
                # Update button - only update when button is clicked
                with col1:
                    if st.button("Update Chunk", key=f"update_{chunk['point_id']}"):
                        if update_chunk(chunk["point_id"], new_text):
                            st.success("Chunk updated successfully!")
                            st.rerun()
                
                # Delete chunk button with confirmation
                with col2:
                    if st.session_state.pending_chunk_deletion == chunk["point_id"]:
                        st.warning("Are you sure you want to delete this chunk?")
                        col3, col4 = st.columns(2)
                        with col3:
                            if st.button("Yes, Delete", key=f"confirm_delete_{chunk['point_id']}"):
                                if delete_chunk(chunk["point_id"]):
                                    st.success("Chunk deleted successfully!")
                                    st.session_state.pending_chunk_deletion = None
                                    st.rerun()
                        with col4:
                            if st.button("No, Cancel", key=f"cancel_delete_{chunk['point_id']}"):
                                st.session_state.pending_chunk_deletion = None
                                st.rerun()
                    else:
                        if st.button("Delete Chunk", key=f"delete_{chunk['point_id']}", type="secondary"):
                            st.session_state.pending_chunk_deletion = chunk["point_id"]
                            st.rerun()
                
                # Display metadata
                st.write("Metadata:")
                st.json(chunk["metadata"])
    else:
        st.info(f"No chunks found for {selected_file}") 