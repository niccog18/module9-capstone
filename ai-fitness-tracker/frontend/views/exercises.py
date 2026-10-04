"""Exercise library: browse system exercises and manage your own."""

import api_client
import streamlit as st
import ui

ALL = "All"
SECTION_KEY = "exercise_section"
SECTIONS = ["Browse", "Add custom", "Manage mine"]


def _matches(
    exercise: dict, search: str, muscle: str, equipment: str, mine: bool
) -> bool:
    if mine and exercise["user_id"] is None:
        return False
    if muscle != ALL and exercise["muscle_group"] != muscle:
        return False
    if equipment != ALL and exercise["equipment"] != equipment:
        return False
    if search:
        haystack = f"{exercise['name']} {exercise['description'] or ''}".lower()
        return search.lower() in haystack
    return True


def _browse_tab(exercises: list[dict]) -> None:
    muscles = [ALL] + sorted({e["muscle_group"] for e in exercises})
    equipment_types = [ALL] + sorted({e["equipment"] for e in exercises})

    search_col, muscle_col, equipment_col = st.columns([2, 1, 1])
    search = search_col.text_input("Search", placeholder="Name or description")
    muscle = muscle_col.selectbox("Muscle group", muscles)
    equipment = equipment_col.selectbox("Equipment", equipment_types)
    mine = st.checkbox("Only my custom exercises")

    shown = [
        e for e in exercises if _matches(e, search.strip(), muscle, equipment, mine)
    ]
    st.caption(f"Showing {len(shown)} of {len(exercises)} exercises")

    if not shown:
        st.info("No exercises match your filters.")
        return

    st.dataframe(
        [
            {
                "Name": e["name"],
                "Muscle group": e["muscle_group"],
                "Equipment": e["equipment"],
                "Type": "Custom" if e["user_id"] is not None else "System",
                "Description": e["description"] or "",
            }
            for e in shown
        ],
        hide_index=True,
    )


def _add_tab(token: str) -> None:
    with st.form("add_exercise_form", clear_on_submit=True):
        name = st.text_input("Name", max_chars=100)
        muscle_group = st.text_input(
            "Muscle group", max_chars=100, placeholder="e.g. Chest"
        )
        equipment = st.text_input(
            "Equipment", max_chars=100, placeholder="e.g. Barbell"
        )
        description = st.text_area("Description (optional)", max_chars=2000)
        submitted = st.form_submit_button("Add exercise", type="primary")

    if not submitted:
        return

    if not (name.strip() and muscle_group.strip() and equipment.strip()):
        st.error("Name, muscle group and equipment are required.")
        return

    ok, created = ui.call(
        api_client.create_exercise,
        token,
        {
            "name": name.strip(),
            "muscle_group": muscle_group.strip(),
            "equipment": equipment.strip(),
            "description": description.strip() or None,
        },
    )
    if ok:
        st.session_state["flash_success"] = f"Added '{created['name']}'."
        st.rerun()


def _manage_tab(token: str, exercises: list[dict]) -> None:
    own = [e for e in exercises if e["user_id"] is not None]
    if not own:
        st.info(
            "You have no custom exercises yet. Add one in the 'Add custom' section."
        )
        return

    chosen = st.selectbox(
        "Choose an exercise",
        own,
        format_func=lambda e: f"{e['name']} ({e['muscle_group']})",
    )

    with st.form(f"edit_exercise_{chosen['exercise_id']}"):
        name = st.text_input("Name", value=chosen["name"], max_chars=100)
        muscle_group = st.text_input(
            "Muscle group", value=chosen["muscle_group"], max_chars=100
        )
        equipment = st.text_input("Equipment", value=chosen["equipment"], max_chars=100)
        description = st.text_area(
            "Description", value=chosen["description"] or "", max_chars=2000
        )
        saved = st.form_submit_button("Save changes", type="primary")

    if saved:
        if not (name.strip() and muscle_group.strip() and equipment.strip()):
            st.error("Name, muscle group and equipment are required.")
        else:
            ok, _ = ui.call(
                api_client.update_exercise,
                token,
                chosen["exercise_id"],
                {
                    "name": name.strip(),
                    "muscle_group": muscle_group.strip(),
                    "equipment": equipment.strip(),
                    "description": description.strip() or None,
                },
            )
            if ok:
                st.success("Saved.")
                st.rerun()

    st.divider()
    confirm = st.checkbox(
        f"Yes, delete '{chosen['name']}'", key=f"confirm_{chosen['exercise_id']}"
    )
    if st.button("Delete exercise", disabled=not confirm):
        ok, _ = ui.call(api_client.delete_exercise, token, chosen["exercise_id"])
        if ok:
            st.success("Deleted.")
            st.rerun()


def render() -> None:
    st.title("Exercise library")

    token = ui.get_token()

    message = st.session_state.pop("flash_success", None)
    if message:
        st.success(message)

    ok, exercises = ui.call(api_client.list_exercises, token)
    if not ok:
        return

    # A selector (not st.tabs) so the chosen section survives reruns:
    # after a form is submitted the user stays where they were.
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

    if section == "Browse":
        _browse_tab(exercises)
    elif section == "Add custom":
        _add_tab(token)
    else:
        _manage_tab(token, exercises)
