"""Workouts: log a workout, then add exercises and review your history."""

from datetime import date

import api_client
import streamlit as st
import ui

SELECTED_KEY = "selected_workout_id"
FLASH_KEY = "workouts_flash"
SECTION_KEY = "workouts_section"
GOTO_KEY = "workouts_goto"
SECTIONS = ["History", "Log workout"]


def _number(value) -> str:
    """Show a Decimal-like API value without trailing zeros, or a dash."""

    if value is None:
        return "-"
    return f"{float(value):g}"


def _workout_label(workout: dict) -> str:
    note = (workout["notes"] or "").strip()
    note = f" - {note[:30]}" if note else ""
    return f"{workout['workout_date']} ({workout['duration_minutes']} min){note}"


# --- Log a new workout -------------------------------------------------------


def _log_tab(token: str) -> None:
    with st.form("log_workout_form", clear_on_submit=True):
        workout_date = st.date_input("Date", value="today")
        minutes = st.number_input(
            "Duration (minutes)", min_value=1, max_value=1440, value=45, step=5
        )
        notes = st.text_area("Notes (optional)", max_chars=5000)
        submitted = st.form_submit_button("Create workout", type="primary")

    if not submitted:
        return

    ok, workout = ui.call(
        api_client.create_workout,
        token,
        {
            "workout_date": workout_date.isoformat(),
            "duration_minutes": int(minutes),
            "notes": notes.strip() or None,
        },
    )
    if ok:
        st.session_state[SELECTED_KEY] = workout["workout_id"]
        st.session_state[FLASH_KEY] = "Workout created. Add its exercises below."
        st.session_state[GOTO_KEY] = "History"
        st.rerun()


# --- Pieces of the history tab ----------------------------------------------


def _entries_table(entries: list[dict]) -> None:
    if not entries:
        st.info("No exercises in this workout yet. Add one below.")
        return

    st.dataframe(
        [
            {
                "#": index,
                "Exercise": entry["exercise"]["name"],
                "Sets": entry["sets"],
                "Reps": entry["reps"],
                "Weight": _number(entry["weight"]),
                "Seconds": _number(entry["duration_seconds"]),
                "Miles": _number(entry["distance_miles"]),
            }
            for index, entry in enumerate(entries, start=1)
        ],
        hide_index=True,
    )


def _add_entry_form(token: str, workout: dict, exercises: list[dict]) -> None:
    workout_id = workout["workout_id"]

    with st.form(f"add_entry_{workout_id}", clear_on_submit=True):
        exercise = st.selectbox(
            "Exercise",
            exercises,
            format_func=lambda e: f"{e['name']} ({e['muscle_group']})",
        )
        sets_col, reps_col = st.columns(2)
        sets = sets_col.number_input("Sets", min_value=1, max_value=100, value=3)
        reps = reps_col.number_input("Reps", min_value=1, max_value=1000, value=10)

        weight_col, seconds_col, miles_col = st.columns(3)
        weight = weight_col.number_input(
            "Weight (optional)", min_value=0.0, value=None, step=2.5, format="%.2f"
        )
        seconds = seconds_col.number_input(
            "Seconds (optional)", min_value=1, max_value=86_400, value=None, step=5
        )
        miles = miles_col.number_input(
            "Miles (optional)", min_value=0.0, value=None, step=0.25, format="%.2f"
        )
        submitted = st.form_submit_button("Add to workout", type="primary")

    if not submitted:
        return

    payload = {
        "exercise_id": exercise["exercise_id"],
        "position": len(workout["exercises"]),
        "sets": int(sets),
        "reps": int(reps),
        "weight": weight,
        "duration_seconds": int(seconds) if seconds is not None else None,
        "distance_miles": miles,
    }
    ok, _ = ui.call(api_client.add_workout_exercise, token, workout_id, payload)
    if ok:
        st.rerun()


def _remove_entry(token: str, workout: dict) -> None:
    entries = workout["exercises"]
    if not entries:
        return

    chosen = st.selectbox(
        "Remove an exercise from this workout",
        entries,
        format_func=lambda e: f"{e['exercise']['name']} ({e['sets']} x {e['reps']})",
        key=f"remove_entry_{workout['workout_id']}",
    )
    if st.button("Remove exercise"):
        ok, _ = ui.call(
            api_client.delete_workout_exercise,
            token,
            workout["workout_id"],
            chosen["workout_exercise_id"],
        )
        if ok:
            st.rerun()


def _edit_workout_form(token: str, workout: dict) -> None:
    workout_id = workout["workout_id"]

    with st.form(f"edit_workout_{workout_id}"):
        workout_date = st.date_input(
            "Date", value=date.fromisoformat(workout["workout_date"])
        )
        minutes = st.number_input(
            "Duration (minutes)",
            min_value=1,
            max_value=1440,
            value=int(workout["duration_minutes"]),
        )
        notes = st.text_area("Notes", value=workout["notes"] or "", max_chars=5000)
        saved = st.form_submit_button("Save changes", type="primary")

    if saved:
        ok, _ = ui.call(
            api_client.update_workout,
            token,
            workout_id,
            {
                "workout_date": workout_date.isoformat(),
                "duration_minutes": int(minutes),
                "notes": notes.strip() or None,
            },
        )
        if ok:
            st.session_state[FLASH_KEY] = "Workout updated."
            st.rerun()

    st.divider()
    confirm = st.checkbox(
        "Yes, delete this whole workout", key=f"confirm_delete_{workout_id}"
    )
    if st.button("Delete workout", disabled=not confirm):
        ok, _ = ui.call(api_client.delete_workout, token, workout_id)
        if ok:
            st.session_state.pop(SELECTED_KEY, None)
            st.session_state[FLASH_KEY] = "Workout deleted."
            st.rerun()


def _history_tab(token: str, workouts: list[dict], exercises: list[dict]) -> None:
    if not workouts:
        st.info("No workouts yet. Log your first one in the 'Log workout' section.")
        return

    ordered = sorted(
        workouts,
        key=lambda w: (w["workout_date"], w["workout_id"]),
        reverse=True,
    )

    selected_id = st.session_state.get(SELECTED_KEY)
    index = next(
        (i for i, w in enumerate(ordered) if w["workout_id"] == selected_id), 0
    )

    chosen = st.selectbox("Workout", ordered, index=index, format_func=_workout_label)
    st.session_state[SELECTED_KEY] = chosen["workout_id"]

    ok, workout = ui.call(api_client.get_workout, token, chosen["workout_id"])
    if not ok:
        return

    if workout["notes"]:
        st.write(workout["notes"])

    st.subheader("Exercises")
    _entries_table(workout["exercises"])
    _remove_entry(token, workout)

    st.subheader("Add an exercise")
    _add_entry_form(token, workout, exercises)

    with st.expander("Edit or delete this workout"):
        _edit_workout_form(token, workout)


def render() -> None:
    st.title("Workouts")

    token = ui.get_token()

    message = st.session_state.pop(FLASH_KEY, None)
    if message:
        st.success(message)

    ok_w, workouts = ui.call(api_client.list_workouts, token, limit=500)
    ok_e, exercises = ui.call(api_client.list_exercises, token)
    if not (ok_w and ok_e):
        return

    # Jump requested by an earlier run (e.g. after creating a workout). It must
    # be applied before the selector below is created.
    goto = st.session_state.pop(GOTO_KEY, None)
    if goto:
        st.session_state[SECTION_KEY] = goto
    st.session_state.setdefault(SECTION_KEY, SECTIONS[0])

    section = (
        st.segmented_control(
            "Section",
            SECTIONS,
            key=SECTION_KEY,
            label_visibility="collapsed",
        )
        or SECTIONS[0]
    )

    if section == "History":
        _history_tab(token, workouts, exercises)
    else:
        _log_tab(token)
