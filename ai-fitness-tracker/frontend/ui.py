"""Shared Streamlit helpers: session state, API error handling, sidebar."""

from typing import Any, Callable

import streamlit as st

import api_client
from api_client import ApiError

HEALTH_LABELS = {
    "healthy": ("🟢", "All systems healthy"),
    "degraded": ("🟡", "Degraded: the AI assistant may be unavailable"),
    "unhealthy": ("🔴", "The database is unavailable"),
    "unreachable": ("🔴", "The backend cannot be reached"),
}


# --- Session state ---------------------------------------------------------


def init_session() -> None:
    """Create every session key before anything reads it."""

    st.session_state.setdefault("token", None)
    st.session_state.setdefault("username", None)
    st.session_state.setdefault("flash", None)


def is_logged_in() -> bool:
    return bool(st.session_state.get("token"))


def get_token() -> str:
    return st.session_state["token"]


def login_user(token: str, username: str) -> None:
    st.session_state["token"] = token
    st.session_state["username"] = username


def logout(message: str | None = None) -> None:
    """Forget the user. The optional message is shown on the login page."""

    st.session_state["token"] = None
    st.session_state["username"] = None
    st.session_state["flash"] = message


def show_flash() -> None:
    """Show (once) a message left by logout(), such as 'session expired'."""

    message = st.session_state.get("flash")
    if message:
        st.warning(message)
        st.session_state["flash"] = None


# --- API calls --------------------------------------------------------------


def call(func: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Run an api_client function and handle failures for the page.

    Returns (True, result) on success. On failure the error is shown to the
    user and (False, None) is returned. An expired or invalid token logs the
    user out and sends them back to the login page.
    """

    try:
        return True, func(*args, **kwargs)
    except ApiError as error:
        if error.is_unauthorized:
            logout("Your session has expired. Please log in again.")
            st.rerun()
        st.error(error.message)
        return False, None


# --- Sidebar ----------------------------------------------------------------


@st.cache_data(ttl=15, show_spinner=False)
def _cached_health() -> dict[str, Any]:
    return api_client.health_check()


def render_sidebar() -> None:
    """Show who is logged in, a log-out button and the backend status."""

    with st.sidebar:
        st.markdown(f"Signed in as **{st.session_state['username']}**")

        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()

        st.divider()

        report = _cached_health()
        icon, label = HEALTH_LABELS.get(report.get("status"), ("⚪", "Status unknown"))
        st.caption(f"{icon} {label}")

        with st.expander("Service details"):
            for service in ("database", "chromadb", "ollama"):
                st.write(f"{service}: {report.get(service, 'unknown')}")