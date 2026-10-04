"""AI assistant: ask training questions answered from the knowledge base."""

import api_client
import streamlit as st
import ui

HISTORY_KEY = "assistant_history"

EXAMPLE_QUESTIONS = [
    "What is progressive overload?",
    "How long should I rest between heavy sets?",
    "What does RPE mean?",
]


def _confidence_text(confidence: float | None) -> str:
    if confidence is None:
        return ""
    return f"Match confidence: {confidence:.0%}"


def _render_sources(message: dict) -> None:
    sources = message.get("sources") or []

    # No sources means nothing relevant was found, so a confidence figure
    # (always 0%) would only be noise.
    if not sources:
        return

    confidence_text = _confidence_text(message.get("confidence"))
    if confidence_text:
        st.caption(confidence_text)

    with st.expander(
        f"Sources ({len(sources)} document{'s' if len(sources) != 1 else ''})"
    ):
        for source in sources:
            distance = source.get("distance")
            similarity = f" - {1 - distance:.0%} match" if distance is not None else ""
            st.markdown(f"**{source['document']}**{similarity}")
            if source.get("content"):
                st.caption(source["content"])


def _render_message(message: dict) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            _render_sources(message)


def _ask(question: str) -> None:
    """Show the question, get an answer and store both on success."""

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching the knowledge base..."):
            ok, result = ui.call(api_client.ask, question, ui.get_token())

        if not ok:
            st.caption("Your question was not saved. Try again in a moment.")
            return

        message = {
            "role": "assistant",
            "content": result["answer"],
            "sources": result.get("sources", []),
            "confidence": result.get("confidence"),
        }
        st.markdown(message["content"])
        _render_sources(message)

    st.session_state[HISTORY_KEY].append({"role": "user", "content": question})
    st.session_state[HISTORY_KEY].append(message)


def render() -> None:
    st.title("AI assistant")
    st.caption(
        "Ask about training principles such as progressive overload, rep ranges, "
        "rest, recovery and technique. Answers come only from the knowledge base "
        "and are general information, not medical advice."
    )

    st.session_state.setdefault(HISTORY_KEY, [])
    history = st.session_state[HISTORY_KEY]

    if history and st.button("Clear conversation"):
        st.session_state[HISTORY_KEY] = []
        st.rerun()

    for message in history:
        _render_message(message)

    if not history:
        st.write("Try one of these:")
        for index, example in enumerate(EXAMPLE_QUESTIONS):
            if st.button(example, key=f"example_{index}"):
                _ask(example)
                st.rerun()

    question = st.chat_input("Ask a training question", max_chars=2000)
    if question and question.strip():
        _ask(question.strip())
