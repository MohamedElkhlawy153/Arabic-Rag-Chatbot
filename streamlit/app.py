import streamlit as st
import requests
import json
import uuid

# Constants
API_BASE_URL = "http://localhost:8000/api/v1"
CHAT_ENDPOINT = f"{API_BASE_URL}/chat"
FEEDBACK_ENDPOINT = f"{API_BASE_URL}/feedback"

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

def send_message(message: str):
    """Send a message to the chat endpoint."""
    try:
        response = requests.post(
            CHAT_ENDPOINT,
            json={
                "query": message,
                "session_id": st.session_state.session_id
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to send message: {e}")
        return {"error": str(e)}

def send_feedback(query_id: str, rating: int, comment: str = "", query_text: str = "", response_text: str = ""):
    """Send feedback to the feedback endpoint."""
    try:
        response = requests.post(
            FEEDBACK_ENDPOINT,
            json={
                "session_id": st.session_state.session_id,
                "query_id": query_id,
                "rating": rating,
                "comment": comment if comment else None,
                "query_text_snapshot": query_text,
                "response_text_snapshot": response_text
            }
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to send feedback: {e}")
        return {"error": str(e)}

def display_feedback_buttons(query_id: str, prompt: str, answer: str):
    """Displays thumbs-up and thumbs-down buttons for feedback."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("👍", key=f"like_{query_id}"):
            fb = send_feedback(
                query_id=query_id,
                rating=1,
                query_text=prompt,
                response_text=answer
            )
            if "error" not in fb:
               st.success("✅!شكرًا لك على تقييمك")

    with col2:
        if st.button("👎", key=f"dislike_{query_id}"):
            comment = st.text_area(":يرجى إخبارنا بما حدث", key=f"comment_{query_id}")
            if st.button("إرسال الملاحظات", key=f"submit_feedback_{query_id}"):
                fb = send_feedback(
                    query_id=query_id,
                    rating=0,
                    comment=comment,
                    query_text=prompt,
                    response_text=answer
                )
                if "error" not in fb:
                    st.success("🙏 Thank you! Your feedback has been submitted.")

def display_chat_history():
    """Displays the chat history from session state."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant" and "message_id" in message:
                display_feedback_buttons(
                    query_id=message["message_id"],
                    prompt=message.get("query", ""),
                    answer=message["content"]
                )

# Page title
st.title("Arabic RAG Chatbot")

# Sidebar with only Admin Panel button
if st.sidebar.button("Admin Panel"):
    st.switch_page("pages/admin.py")

# Display chat history
display_chat_history()

# Chat input
if prompt := st.chat_input("What would you like to know?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("...يتم الآن توليد الإجابة"):
            response = send_message(prompt)
            if "error" not in response:
                answer = response["answer"]
                query_id = response.get("query_id")

                st.write(answer)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "message_id": query_id,
                    "query": prompt
                })
                # عرض أزرار التقييم مباشرة بعد الحصول على الإجابة
                display_feedback_buttons(
                    query_id=query_id,
                    prompt=prompt,
                    answer=answer
                )
            else:
                st.error("❌ Failed to get response from the assistant.")