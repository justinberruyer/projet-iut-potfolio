import streamlit as st
import random
import time


from chatbot import build_agent, get_index, run_question

st.title("Simple chat")

if "agent" not in st.session_state:
    index = get_index()
    st.session_state.agent = build_agent(index)

if "last_response_id" not in st.session_state:
    st.session_state.last_response_id = None

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Accept user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        answer, last_id = run_question(
            st.session_state.agent,
            prompt,
            st.session_state.last_response_id,
        )
        st.markdown(answer)

    st.session_state.last_response_id = last_id
    st.session_state.messages.append({"role": "assistant", "content": answer})