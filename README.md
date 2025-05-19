# Arabic RAG Chatbot

This project implements a full-stack Arabic Retrieval-Augmented Generation (RAG) chatbot system. It allows users to upload documents (PDF, TXT), ask questions in Arabic about their content, and receive contextualized answers. The system is designed with a modern frontend interface and a robust backend API.

## Project Overview

The Arabic RAG Chatbot consists of two main components:

1.  **Frontend (`frontend/`)**: A React-based single-page application (SPA) providing the user interface for document upload, chat interaction, and feedback.
2.  **Backend (`backend/`)**: A FastAPI-powered Python application serving as the API for document processing, RAG pipeline execution, and feedback storage.

This root-level README provides a general overview and links to the more detailed README files for each component.

## Features

**Combined System Features:**

- **End-to-End RAG Pipeline:** From document upload to contextualized chat responses.
- **Arabic Language Focus:** Designed for interaction and document processing in Arabic.
- **Document Support:** Handles PDF and TXT file types for knowledge base creation.
- **Session-Based Context:** Chat interactions are tied to specific uploaded documents through session IDs.
- **Source-Cited Answers:** Chatbot responses include references to the document sections used for generation.
- **User Feedback Mechanism:** Allows users to rate the helpfulness of bot responses.
- **Modern User Interface:** Responsive design with light/dark theme support.
- **Developer-Friendly:** Clear separation of concerns between frontend and backend, with API documentation.

**For detailed features of each component, please refer to their respective READMEs:**

- [Frontend README](./frontend/README.md)
- [Backend README](./backend/README.md)

## Tech Stack Overview

**Frontend:**

- React
- Tailwind CSS
- Vite

**Backend:**

- Python / FastAPI
- Cohere (Embeddings & Reranking)
- Google Gemini / Qwen3 (LLM for Generation)
- Qdrant (Vector Store)
- SQLAlchemy / SQLite (Database for Logging & Feedback)

## Getting Started

To run the full application, you will need to set up and run both the frontend and backend components.

**1. Backend Setup:**

Please follow the instructions in the [Backend README](./backend/README.md) to install dependencies, configure environment variables (including API keys for Cohere, Gemini, etc.), and start the backend server.

**2. Frontend Setup:**

Once the backend is running, follow the instructions in the [Frontend README](./frontend/README.md) to install dependencies, configure the backend API URL in the frontend's environment variables, and start the frontend development server.

**Typical Workflow:**

1.  Start the backend server (usually on `http://localhost:8000`).
2.  Start the frontend development server (usually on `http://localhost:5173`).
3.  Open the frontend URL in your browser to use the application.

## Project Structure

```bash
arabic-rag-chatbot/
├── backend/ # Backend FastAPI application
│ ├── app/
│ ├── .env.example
│ ├── README.md # Detailed backend documentation
│ └── requirements.txt
│ └── ...
├── frontend/ # Frontend React application
│ ├── public/
│ ├── src/
│ ├── .env.example
│ ├── README.md # Detailed frontend documentation
│ ├── package.json
│ └── ...
├── .gitignore # Git ignore rules for the whole project
└── README.md # This root README file
```

## Contributing

Contributions are welcome to either the frontend or backend components. Please refer to the `CONTRIBUTING.md` section within each component's README for specific guidelines.

Generally, for contributions:

1.  Fork the main repository.
2.  Create a feature branch from the `main` or `develop` branch.
3.  Make your changes in the respective `frontend/` or `backend/` directory.
4.  Follow coding standards and commit conventions as outlined.
5.  Push your branch and open a Pull Request against the main repository, clearly describing your changes.
