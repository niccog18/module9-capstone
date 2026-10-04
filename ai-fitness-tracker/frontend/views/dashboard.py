"""Dashboard: a summary of the user's training data."""

import streamlit as st

import api_client
import ui

RECENT_WORKOUT_COUNT = 5


def render() -> None:
    st.title("Dashboard")

    token = ui.get_token()

    with st.spinner("Loading your data..."):
        workouts_ok, workouts = ui.call(api_client.list_workouts, token, limit=500)
        plans_ok, plans = ui.call(api_client.list_plans, token, limit=500)
        exercises_ok, exercises = ui.call(api_client.list_exercises, token)

    if not (workouts_ok and plans_ok and exercises_ok):
        return

    custom_count = sum(1 for exercise in exercises if exercise["user_id"] is not None)

    workouts_col, plans_col, exercises_col = st.columns(3)
    workouts_col.metric("Workouts logged", len(workouts))
    plans_col.metric("Training plans", len(plans))
    exercises_col.metric(
        "Exercises available",
        len(exercises),
        help=f"{len(exercises) - custom_count} system exercises and "
        f"{custom_count} of your own.",
    )

    st.subheader("Recent workouts")

    if not workouts:
        st.info("No workouts logged yet.")
        return

    recent = sorted(
        workouts,
        key=lambda workout: (workout["workout_date"], workout["workout_id"]),
        reverse=True,
    )[:RECENT_WORKOUT_COUNT]

    st.dataframe(
        [
            {
                "Date": workout["workout_date"],
                "Minutes": workout["duration_minutes"],
                "Notes": workout["notes"] or "",
            }
            for workout in recent
        ],
        hide_index=True,
    )