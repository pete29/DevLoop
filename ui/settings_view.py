"""The settings panel: keys, the monthly limit and the password, from the page."""

import streamlit as st

from config.settings import Settings
from services import auth, env_file
from services.translations import LANGUAGES
from ui import shared
from ui.shared import t

# Label and help per setting, in the order shown.
SHOWN = (
    ("ANTHROPIC_API_KEY", "settings.anthropic", "settings.anthropic_help"),
    ("GITHUB_PAT", "settings.github", "settings.github_help"),
    ("GITHUB_ADMIN_PAT", "settings.github_admin", "settings.github_admin_help"),
    ("DEVLOOP_MONTH_LIMIT", "settings.month_limit", "settings.month_limit_help"),
)


def settings_view() -> None:
    """Every setting with what it is now, and a field to change it.

    A key is never shown back: the field is empty, and the
    line above it says only whether one is set, how it
    starts and how long it is.
    """

    st.subheader(t("settings.heading"))

    st.caption(t("settings.caption"))

    if Settings.PASSWORD_IN_SETTINGS and not auth.required():
        st.warning(t("settings.no_password"))

    language_choice()

    for name, label, help_key in SHOWN:
        setting_form(name, label, help_key)

    if Settings.PASSWORD_IN_SETTINGS:
        password_form()

    if st.button(t("settings.close"), key="settings-close"):
        st.session_state.show_settings = False
        st.rerun()

    st.divider()


def language_choice() -> None:
    """The interface's language, remembered for the next session."""

    st.session_state.language_select = st.session_state.language

    st.selectbox(
        t("app.language"),
        tuple(LANGUAGES),
        format_func=lambda code: LANGUAGES[code],
        key="language_select",
        on_change=lambda: shared.select_language(st.session_state.language_select),
    )


def setting_form(name: str, label: str, help_key: str) -> None:
    """One setting: what it is now, and a field to replace or clear it."""

    with st.form(f"setting-{name}", clear_on_submit=True, border=True):

        shown = env_file.describe(name)

        st.markdown(f"**{t(label)}** · `{name}`")

        st.caption(t("settings.now", value=shown) if shown else t("settings.unset"))

        value = st.text_input(
            t(label),
            type="password" if env_file.FIELDS[name].secret else "default",
            help=t(help_key),
            label_visibility="collapsed",
            placeholder=t("settings.placeholder"),
        )

        save, clear = st.columns(2)

        with save:
            saved = st.form_submit_button(t("settings.save"), use_container_width=True)

        with clear:
            cleared = st.form_submit_button(
                t("settings.clear"),
                use_container_width=True,
                disabled=not shown,
            )

    if not saved and not cleared:
        return

    try:
        stored = env_file.save(name, "" if cleared else value)

    except env_file.SettingError as error:
        st.error(str(error))
        return

    if name == "DEVLOOP_MONTH_LIMIT":
        Settings.MONTH_COST_LIMIT = float(stored or 0)

    st.session_state.git_message = (
        "success",
        t("settings.saved", name=name) if stored else t("settings.cleared", name=name),
    )

    st.rerun()


def password_form() -> None:
    """Setting, changing or removing the page's password.

    The current one is asked for whenever there is one: an
    open tab must not be enough to lock its owner out.
    """

    with st.form("setting-password", clear_on_submit=True, border=True):

        st.markdown(f"**{t('settings.password')}** · `{auth.VARIABLE}`")

        st.caption(t("settings.password_set") if auth.required() else t("settings.password_unset"))

        old = (
            st.text_input(t("settings.password_current"), type="password")
            if auth.required()
            else ""
        )

        new = st.text_input(t("settings.password_new"), type="password")

        again = st.text_input(t("settings.password_again"), type="password")

        save, remove = st.columns(2)

        with save:
            saved = st.form_submit_button(t("settings.save"), use_container_width=True)

        with remove:
            removed = st.form_submit_button(
                t("settings.password_remove"),
                use_container_width=True,
                disabled=not auth.required(),
            )

    if not saved and not removed:
        return

    if auth.required() and not auth.matches(old, auth.stored_hash()):
        st.error(t("settings.password_wrong"))
        return

    if removed:
        env_file.write(auth.VARIABLE, "")
        st.session_state.git_message = ("success", t("settings.password_removed"))
        st.rerun()

    if len(new) < 8:
        st.error(t("settings.password_short"))
        return

    if new != again:
        st.error(t("settings.password_mismatch"))
        return

    env_file.write(auth.VARIABLE, auth.hash_password(new))

    # Signed in already: changing the password does not
    # throw out the session that changed it.
    st.session_state.signed_in = True

    st.session_state.git_message = ("success", t("settings.password_saved"))

    st.rerun()
