"""AI Fitness Tracker: Streamlit frontend.

Run locally:
    BACKEND_URL=http://localhost:8000 streamlit run app.py

Inside Docker Compose, BACKEND_URL is set automatically. All backend calls go
through api_client.py; pages live in the views/ package.
"""

import streamlit as st
import ui
from views import assistant, auth, dashboard, exercises, workouts

st.set_page_config(
    page_title="AI Fitness Tracker",
    page_icon="🏋️",
    layout="wide",
)

ui.init_session()

if not ui.is_logged_in():
    auth.render()
    st.stop()

navigation = st.navigation(
    [
        st.Page(
            dashboard.render,
            title="Dashboard",
            icon=":material/home:",
            url_path="dashboard",
            default=True,
        ),
        st.Page(
            exercises.render,
            title="Exercise library",
            icon=":material/fitness_center:",
            url_path="exercises",
        ),
        st.Page(
            workouts.render,
            title="Workouts",
            icon=":material/event_note:",
            url_path="workouts",
        ),
        st.Page(
            assistant.render,
            title="AI assistant",
            icon=":material/smart_toy:",
            url_path="assistant",
        ),
        # More pages are added here as they are built.
    ]
)

ui.render_sidebar()
navigation.run()
