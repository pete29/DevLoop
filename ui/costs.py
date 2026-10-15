"""The cost history: what was spent per day, and per plan."""

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from services import costs
from ui.shared import plan_store, repository, t


def cost_view() -> None:
    """Spending per day for 30 days, then per plan.

    One series, so one colour and no legend: the heading
    names it. The plan table is also the chart's numbers in
    a form that can be read without the chart.
    """

    tasks = repository.get_all()

    plans = plan_store.get_all()

    days = costs.daily(tasks, plans, datetime.now(UTC).date())

    st.subheader(t("cost.history_heading"))

    day_column = t("cost.column_day")

    usd_column = t("cost.column_usd")

    frame = pd.DataFrame(days, columns=[day_column, usd_column]).set_index(day_column)

    st.bar_chart(frame, y=usd_column, height=220)

    st.caption(t("cost.history_total", spent=f"{sum(value for _, value in days):.2f}"))

    st.markdown(f"**{t('cost.per_plan')}**")

    st.dataframe(
        pd.DataFrame(
            costs.per_plan(tasks, plans),
            columns=[t("cost.column_plan"), day_column, usd_column],
        ),
        hide_index=True,
        use_container_width=True,
    )

    if st.button(t("cost.close"), key="cost-close"):
        st.session_state.show_costs = False
        st.rerun()

    st.divider()
