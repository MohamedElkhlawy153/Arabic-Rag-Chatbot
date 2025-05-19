# Arabic RAG Chatbot - Streamlit Frontend

This is the Streamlit frontend for the Arabic RAG Chatbot. It provides a user-friendly interface for interacting with the chatbot, uploading documents, and providing feedback.

## Features

- User authentication
- Real-time chat interface
- Document upload and processing
- Message feedback system
- Responsive design

## Prerequisites

- Python 3.8 or higher
- Backend server running (FastAPI backend)
- Required Python packages (listed in requirements.txt)

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

## Running the App

1. Make sure the backend server is running (typically on http://localhost:8000)

2. Start the Streamlit app:
```bash
streamlit run app.py
```

3. Open your web browser and navigate to the URL shown in the terminal (typically http://localhost:8501)

## Usage

1. Log in using your credentials
2. Use the sidebar to upload documents
3. Type your questions in the chat input
4. Provide feedback on responses using the 👍 and 👎 buttons
5. Use the logout button in the sidebar when you're done

## Configuration

The app is configured to connect to the backend at http://localhost:8000 by default. If your backend is running on a different URL, you can modify the `API_BASE_URL` constant in `app.py`. 