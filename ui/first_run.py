"""The first-run page: what is missing before DevLoop can work.

Shown instead of the page while something required is missing
-- git, Node.js or the Anthropic key -- so a new install finds
out here, not from a failed run. It can be passed over: the
page still opens, and the checks are made again next start.
"""

import os

import streamlit as st

from services import first_run
from ui.settings_view import setting_form
from ui.shared import t

# The keys the page can set right here.
FORMS = {
    "ANTHROPIC_API_KEY": ("settings.anthropic", "settings.anthropic_help"),
    "GITHUB_PAT": ("settings.github", "settings.github_help"),
}


def first_run_page() -> None:
    """The checks, and forms for the missing keys; stops the page until passed."""

    # The test suites check their own pages, not this one.
    if st.session_state.get("first_run_done") or os.getenv("DEVLOOP_FIRST_RUN", "").lower() == "off":
        return

    found = first_run.checks()

    if first_run.ready(found):
        st.session_state.first_run_done = True
        return

    st.subheader(t("first_run.heading"))

    st.caption(t("first_run.caption"))

    for check in found:

        mark = "✅" if check.ok else ("❌" if check.required else "➖")

        need = t("first_run.required") if check.required else t("first_run.optional")

        st.markdown(f"{mark} **{t('first_run.' + check.key)}** ({need}) · {check.detail}")

        if not check.ok and check.key in FORMS:
            label, help_key = FORMS[check.key]
            setting_form(check.key, label, help_key)

        elif not check.ok and check.link:
            st.caption(t("first_run.get_it", link=check.link))

    st.info(t("first_run.next"))

    if st.button(t("first_run.anyway"), key="first-run-anyway"):
        st.session_state.first_run_done = True
        st.rerun()

    st.stop()
