"""Things in the data that look wrong or out of date."""

import streamlit as st

from portfolio.core.analytics import checks
from portfolio.ui import common


def render() -> None:
    st.title("Checks")
    loaded = common.portfolio()
    found = checks.run_checks(loaded.data, loaded.today)
    st.caption(
        "Looked for in the active instruments every time this page opens. Nothing is "
        "changed; correct what is really wrong in Transactions. A finding can also be fine "
        "as it is."
    )
    if not found:
        st.success("Nothing found.")
    for name, explanation in checks.EXPLANATIONS.items():
        rows = [f for f in found if f.check == name]
        if not rows:
            continue
        st.subheader(f"{name} ({len(rows)})")
        st.caption(explanation)
        st.dataframe(
            [{"Ticker": f.ticker, "Date": f.date, "What": f.detail} for f in rows],
            hide_index=True,
            width="content",
        )
    quiet = [name for name in checks.EXPLANATIONS if all(f.check != name for f in found)]
    if found and quiet:
        st.caption("Nothing found for: " + ", ".join(name.lower() for name in quiet) + ".")
