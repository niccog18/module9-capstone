"""Login and account-creation page."""

import streamlit as st

import api_client
import ui
from api_client import ApiError


def _sign_in(username: str, password: str) -> None:
    """Log in, store the token and reload into the app."""

    with st.spinner("Signing in..."):
        try:
            token = api_client.login(username, password)
        except ApiError as error:
            # Not ui.call: a 401 here means wrong credentials, not an expired session.
            st.error(error.message)
            return

        display_name = username
        try:
            display_name = api_client.get_current_user(token).get("username", username)
        except ApiError:
            pass  # the name typed at login is good enough

    ui.login_user(token, display_name)
    st.rerun()


def _login_tab() -> None:
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", type="primary")

    if not submitted:
        return

    if not username.strip() or not password:
        st.error("Enter your username and password.")
        return

    _sign_in(username.strip(), password)


def _register_tab() -> None:
    with st.form("register_form"):
        username = st.text_input(
            "Username", help="3-50 characters: letters, numbers, . _ -"
        )
        email = st.text_input("Email")
        password = st.text_input(
            "Password", type="password", help="At least 8 characters."
        )
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account", type="primary")

    if not submitted:
        return

    if not (username.strip() and email.strip() and password):
        st.error("Fill in every field.")
        return

    if password != confirm:
        st.error("The passwords do not match.")
        return

    with st.spinner("Creating your account..."):
        try:
            api_client.register(username.strip(), email.strip(), password)
        except ApiError as error:
            st.error(error.message)
            return

    _sign_in(username.strip(), password)


def render() -> None:
    st.title("AI Fitness Tracker")
    st.caption("Log workouts, build training plans, and ask the fitness assistant.")

    ui.show_flash()

    login_tab, register_tab = st.tabs(["Log in", "Create account"])
    with login_tab:
        _login_tab()
    with register_tab:
        _register_tab()