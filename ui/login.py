"""The sign-in screen, shown instead of the page until it is passed."""

import streamlit as st

from services import auth
from ui.shared import t


def require_login() -> None:
    """Stops the page here until the password is given.

    Nothing below runs before that: no database read, no
    GitHub call, no repository listed. Without a password
    in .env the page is open, as it always was.
    """

    if not auth.required() or st.session_state.get("signed_in"):
        return

    st.title(t("login.heading"))

    locked = auth.seconds_locked()

    if locked:
        st.warning(t("login.locked", seconds=locked))

    with st.form("login"):

        password = st.text_input(t("login.password"), type="password")

        submitted = st.form_submit_button(t("login.submit"), type="primary")

    if submitted:

        if auth.sign_in(password):

            st.session_state.signed_in = True

            st.rerun()

        st.error(
            t("login.locked", seconds=auth.seconds_locked())
            if auth.seconds_locked()
            else t("login.wrong")
        )

    st.stop()


def logout_button() -> None:
    """Signing out, in the sidebar, when there is a password."""

    if not auth.required():
        return

    if st.sidebar.button(t("login.logout"), key="logout", use_container_width=True):

        # Everything the session held goes with it: the open
        # task, plan and requirement included.
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.rerun()
