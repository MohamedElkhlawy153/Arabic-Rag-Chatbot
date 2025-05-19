# Arabic RAG Chatbot - Backend

This project implements the backend API for an Arabic Retrieval-Augmented Generation (RAG) chatbot. It allows users to upload documents (PDF, TXT) to create a session-specific knowledge base, and then query this knowledge base in Arabic. The system uses Cohere for embeddings and reranking, Qdrant as a vector store, and Google Gemini (with Qwen3 as a configurable alternative) for generating responses.

## Features

- **Document Upload & Ingestion:**
  - Supports PDF and TXT file uploads.
  - Automatically extracts text, chunks it into manageable pieces.
  - Generates embeddings using Cohere's multilingual models.
  - Stores document chunks and their embeddings in a Qdrant vector database.
  - Each upload session is tagged with a unique `session_id`.
  - Uploading a new file with an existing `session_id` (or if one is provided and exists) will first delete the old documents associated with that session.
- **RAG Chat Functionality:**
  - Accepts user queries in Arabic and a `session_id`.
  - Retrieves relevant document chunks from Qdrant based on semantic similarity to the query (using Cohere embeddings).
  - Reranks the retrieved chunks using Cohere Rerank for improved relevance.
  - Constructs a prompt with the reranked context and the user's query.
  - Generates a contextualized answer in Arabic using Google Gemini (primary) or Qwen3 (fallback/alternative).
  - Returns the answer along with source document information.
- **Feedback Mechanism:**
  - Allows authenticated "agents" to submit positive/negative feedback on chat responses.
  - Feedback is linked to specific queries via a `query_id`.
- **Database Logging:**
  - Logs key events like file ingestion, chat queries, and feedback submissions to a SQLite database.
- **Configuration:**
  - Settings are managed via environment variables and a `.env` file.
- **API Documentation:**
  - Provides OpenAPI (Swagger) documentation for all endpoints.

## Tech Stack

- **Programming Language:** Python 3.10+
- **Web Framework:** FastAPI
- **Embeddings & Reranking:** Cohere API
- **Generation LLM:** Google Gemini API (primary), Qwen3 (Hugging Face Transformers - alternative)
- **Vector Store:** Qdrant
- **Text Processing:** `pypdf`, `python-docx`, `langchain_text_splitters`
- **Database ORM:** SQLAlchemy
- **Database:** SQLite (default, configurable)
- **Dependency Management:** Poetry (recommended) or pip with `requirements.txt`
- **API Documentation:** OpenAPI / Swagger UI

## Project Structure

```css
backend/
├── app/ # Main application module
│ ├── api/ # API versioning and endpoints
│ │ ├── deps.py # FastAPI dependencies
│ │ └── v1/ # Version 1 of the API
│ │ ├── endpoints/ # Endpoint modules (chat, upload, feedback)
│ │ └── routes.py # API v1 router
│ ├── core/ # Core components
│ │ ├── config.py # Application settings
│ │ └── logging_config.py # Logging setup
│ ├── db/ # Database related modules
│ │ ├── models.py # SQLAlchemy models
│ │ └── session.py # Database session management
│ ├── schemas/ # Pydantic schemas for request/response validation
│ ├── services/ # Business logic (chat, feedback, logging)
│ ├── utils/ # Utility functions (embeddings, qdrant, cohere, gemini, text processing)
│ ├── llm_loader.py # (If using local Qwen3)
│ └── main.py # FastAPI application entry point
├── .env.example # Example environment variables file
├── .gitignore
├── README.md # This file
└── requirements.txt
```

## Setup and Installation

**1. Prerequisites:**

- Python 3.10 or higher
- Access to Cohere API and Google Gemini API (requires API keys)

**2. Clone the Repository (if applicable):**

```bash
git clone https://github.com/moatasem75291/arabic-rag-chatbot.git
cd backend
```

**3. Create a Virtual Environment:**

````bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate```
````

**4. Install Dependencies:**

```bash
pip install -r requirements.txt
```

**5. Configure Environment Variables:**

- Copy .env.example to .env
- Update the `.env` file with your API keys and other configurations.

**7. Run the Application:**

```bash
uvicorn app.main:app --reload
```

## API Endpoints

The API provides the following main endpoints (prefixed with /api/v1):

- GET /: Health check.
- POST /upload/: Upload a document (PDF/TXT) to create/replace a session context.
  - Request: multipart/form-data with file and optional session_id.
  - Response: JSON with session_id, filename, chunks_added.
- POST /chat/: Send a query for a given session_id.
  - Request: JSON with query and session_id.
  - Response: JSON with query_id, answer, sources.
- POST /feedback/: Submit feedback for a specific query_id. (Requires X-API-Key authentication)
  - Request: JSON with query_id, rating (boolean), and optional comment.
  - Response: JSON confirming submission.

For detailed request/response schemas and examples, refer to the OpenAPI documentation available at:

- **Swagger UI:** http://127.0.0.1:8000/docs
- **ReDoc:** http://127.0.0.1:8000/redoc
- **OpenAPI JSON:** http://127.0.0.1:8000/api/v1/openapi.json

## Switching LLM (Gemini vs. Qwen3)

The chat_service.py is currently configured to use Google Gemini for generation. The Qwen3 generation block is commented out. To switch:

1. In app/services/chat_service.py:
   - Comment out the Gemini generation block.
   - Uncomment the Qwen3 generation block.
   - Ensure get_qwen_model() and get_qwen_tokenizer() from app.llm_loader are correctly set up if you use Qwen3.
   - Update log_event_type and generation_llm_used variables accordingly.
2. Ensure Qwen3 model settings (QWEN_MODEL_NAME, LOCAL_MODELS_DIR, etc.) are correctly configured in your .env file and app/core/config.py.
3. Install necessary Qwen3 dependencies (transformers, torch, accelerate).

## Session Management

- When a file is uploaded via /upload/, it's associated with a session_id.
- If a session_id is provided during upload and documents already exist for that session in Qdrant, those old documents are deleted before the new ones are added. This ensures each session context is based on the latest upload for that ID.

* The /chat/ endpoint uses this session_id to filter the Qdrant vector store, ensuring that only documents from the specified session are used as context for generating answers.

## Contributing

(Add guidelines if this is an open project: e.g., fork, branch, commit conventions, pull requests, code style with linters/formatters like Black, Flake8, isort).
