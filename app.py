"""DevLoop: the Streamlit page.

The page runs top to bottom on every click; each step below
draws one part of it. The parts live in ui/.
"""

import streamlit as st
from dotenv import load_dotenv

from config.paths import env_path
from config.settings import Settings
from services import build_info, plan_runner
from ui import shared
from ui.costs import cost_view
from ui.first_run import first_run_page
from ui.login import logout_button, require_login
from ui.page import quick_task_panel, status_line, task_window
from ui.plans import plan_view
from ui.requirements import requirement_view
from ui.shared import init_session, run_store, show_message, t
from ui.settings_view import settings_view
from ui.sidebar import sidebar

load_dotenv(env_path())

init_session()

# Before anything is read or shown.
require_login()

# git, Node.js and the key, before the first run can fail on them.
first_run_page()

shared.refresh()

# A worker that died says nothing; its process being gone
# is the only evidence, so every page load looks.
plan_runner.detect_interrupted(run_store)

st.title(Settings.PAGE_TITLE)

st.caption(t("app.version", label=build_info.label()))

# With the task window open, the message is shown in it.
if st.session_state.task is None:
    show_message()

sidebar()

logout_button()

if st.session_state.get("show_settings"):
    settings_view()

if st.session_state.get("show_costs"):
    cost_view()

status_line()

requirement_view()

plan_view()

quick_task_panel()

task_window()
