import os

import streamlit as st
from dotenv import load_dotenv

from agents import Runner
from agents.tracing import set_tracing_disabled

# Import your existing agent definition
from agent import agent as portfolio_agent


def _configure_runtime() -> None:
    load_dotenv()

    # Disable OpenAI Agents tracing export by default to avoid timeouts behind proxies.
    # Re-enable by setting OPENAI_AGENTS_DISABLE_TRACING=false in your .env.
    set_tracing_disabled(
        os.environ.get("OPENAI_AGENTS_DISABLE_TRACING", "true").lower()
        in ("1", "true", "yes", "on")
    )


_configure_runtime()

st.set_page_config(page_title="Portfolio Chatbot", page_icon="💬", layout="centered")
st.title("Portfolio – Chatbot")

with st.sidebar:
    st.header("Options")
    if st.button("🧹 Réinitialiser la conversation", use_container_width=True):
        st.session_state.pop("messages", None)
        st.session_state.pop("last_response_id", None)
        st.rerun()

    if st.button("🔄 Re-indexer les fichiers Markdown", use_container_width=True):
        with st.spinner("Indexation en cours…"):
            try:
                import indexation

                indexation.main()
                st.success("Indexation terminée. Vous pouvez reposer votre question.")
            except Exception as e:
                st.error(f"Erreur pendant l'indexation : {e}")

    st.caption(
        "Astuce : vous n'avez pas besoin de relancer l'indexation à chaque lancement. "
        "Relancez `indexation.py` seulement si vous modifiez vos fichiers Markdown."
    )

# Basic env checks (helps diagnose empty .env)
missing = []
for key in ("OPENAI_API_KEY", "UPSTASH_VECTOR_REST_URL", "UPSTASH_VECTOR_REST_TOKEN"):
    if not os.getenv(key):
        missing.append(key)
if missing:
    st.warning(
        "Variables d'environnement manquantes: "
        + ", ".join(missing)
        + ".\nCréez un fichier .env et remplissez-le avant de discuter avec l'agent."
    )

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Salut ! Pose-moi une question sur le portfolio de Justin Berruyer.",
        }
    ]

if "last_response_id" not in st.session_state:
    st.session_state.last_response_id = None

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Votre message…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Réflexion…"):
            result = Runner.run_sync(
                portfolio_agent,
                prompt,
                previous_response_id=st.session_state.last_response_id,
                auto_previous_response_id=True,
            )

        answer = (result.final_output or "").strip() or "(Pas de réponse)"
        st.markdown(answer)

    st.session_state.last_response_id = result.last_response_id
    st.session_state.messages.append({"role": "assistant", "content": answer})

    # Streamlit re-runs the script on every interaction; rerun to display the appended messages cleanly
    st.rerun()
