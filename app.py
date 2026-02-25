import streamlit as st
import pandas as pd

from database import (
    init_db, bulletin_exists, save_bulletin, get_available_months,
    get_dates_for_month, get_trend_data, get_latest_bulletin_month,
    get_all_categories, get_all_countries,
)
from scraper import (
    fetch_bulletin_page, parse_bulletin, check_latest_bulletin,
    generate_month_range,
)
from charts import plot_trend, plot_multi_trend

st.set_page_config(page_title="Visa Bulletin Tracker", layout="wide")

# Initialize database
init_db()

# ── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("Visa Bulletin Tracker")
st.sidebar.markdown("<div style='margin-bottom: 1.5rem'></div>", unsafe_allow_html=True)

# Navigation buttons — full width edge-to-edge, no gaps
st.sidebar.markdown("""
<style>
/* Kill gaps between button wrappers */
section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
section[data-testid="stSidebar"] [data-testid="stElementContainer"] {
    gap: 0 !important;
}
/* Negative margins to break out of sidebar padding */
section[data-testid="stSidebar"] button[kind] {
    border-radius: 0 !important;
    border: none !important;
    border-bottom: 1px solid rgba(150, 150, 150, 0.2) !important;
    margin-left: -1rem !important;
    margin-right: -1rem !important;
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    padding: 0.75rem 1.5rem !important;
    width: calc(100% + 2rem) !important;
}
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "Monthly View"

for label in ["Monthly View", "Trend", "Compare"]:
    if st.sidebar.button(label, key=f"nav_{label}", use_container_width=True,
                         type="primary" if st.session_state.page == label else "secondary"):
        st.session_state.page = label
        st.rerun()

page = st.session_state.page

st.sidebar.markdown("---")

# Refresh latest bulletin
if st.sidebar.button("Refresh Latest Bulletin"):
    with st.sidebar.status("Checking for new bulletins..."):
        try:
            available = check_latest_bulletin()
            if not available:
                st.sidebar.warning("Could not find any bulletins on the index page.")
            else:
                new_count = 0
                for year, month, month_str in available[:3]:
                    if not bulletin_exists(month_str):
                        st.sidebar.write(f"Fetching {month_str}...")
                        html = fetch_bulletin_page(year, month)
                        records = parse_bulletin(html)
                        if records:
                            save_bulletin(month_str, records)
                            new_count += 1
                        else:
                            st.sidebar.warning(f"No data parsed for {month_str}")
                if new_count > 0:
                    st.sidebar.success(f"Imported {new_count} new bulletin(s).")
                    st.rerun()
                else:
                    st.sidebar.info("All recent bulletins already imported.")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

# Bulk import
with st.sidebar.expander("Bulk Import"):
    col1, col2 = st.columns(2)
    with col1:
        start_year = st.number_input("Start Year", min_value=2002, max_value=2026, value=2006)
        start_month = st.number_input("Start Month", min_value=1, max_value=12, value=1)
    with col2:
        end_year = st.number_input("End Year", min_value=2002, max_value=2026, value=2026)
        end_month = st.number_input("End Month", min_value=1, max_value=12, value=2)

    if st.button("Import Range"):
        months_to_fetch = list(generate_month_range(start_year, start_month, end_year, end_month))
        progress = st.progress(0)
        imported = 0
        skipped = 0
        errors = []

        for i, (y, m) in enumerate(months_to_fetch):
            month_str = f"{y}-{m:02d}"
            progress.progress((i + 1) / len(months_to_fetch))

            if bulletin_exists(month_str):
                skipped += 1
                continue

            try:
                html = fetch_bulletin_page(y, m)
                records = parse_bulletin(html)
                if records:
                    save_bulletin(month_str, records)
                    imported += 1
                else:
                    errors.append(f"{month_str}: no data parsed")
            except Exception as e:
                errors.append(f"{month_str}: {e}")

        st.success(f"Done! Imported: {imported}, Skipped: {skipped}, Errors: {len(errors)}")
        if errors:
            with st.expander("Errors"):
                for err in errors:
                    st.text(err)
        if imported > 0:
            st.rerun()

# ── Main Content ─────────────────────────────────────────────────────────────

available_months = get_available_months()

if not available_months:
    st.info("No bulletin data yet. Use the sidebar to refresh or import bulletins.")
    st.stop()

# ── Monthly View ─────────────────────────────────────────────────────────────

if page == "Monthly View":
    st.header("Monthly View")

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_month = st.selectbox("Bulletin Month", available_months)
    with col2:
        table_type = st.radio("Table Type", ["Final Action", "Filing"], horizontal=True)
    with col3:
        visa_type = st.radio("Visa Type", ["Employment", "Family"], horizontal=True)

    table_type_key = "final_action" if table_type == "Final Action" else "filing"
    visa_type_key = visa_type.lower()

    data = get_dates_for_month(selected_month)
    filtered = [
        r for r in data
        if r["table_type"] == table_type_key and r["visa_type"] == visa_type_key
    ]

    if not filtered:
        st.warning("No data for this selection.")
    else:
        country_order = [
            "All Chargeability Areas", "China", "India", "Mexico", "Philippines"
        ]
        actual_countries = sorted(set(r["country"] for r in filtered))
        ordered_countries = [c for c in country_order if c in actual_countries]
        ordered_countries += [c for c in actual_countries if c not in ordered_countries]

        if visa_type_key == "employment":
            cat_order = [
                "EB-1", "EB-2", "EB-3", "EB-3 Other Workers", "EB-4",
                "EB-4 Religious Workers", "EB-5 Unreserved", "EB-5 Rural",
                "EB-5 High Unemployment", "EB-5 Infrastructure",
            ]
        else:
            cat_order = ["F1", "F2A", "F2B", "F3", "F4"]

        actual_cats = sorted(set(r["category"] for r in filtered))
        ordered_cats = [c for c in cat_order if c in actual_cats]
        ordered_cats += [c for c in actual_cats if c not in ordered_cats]

        lookup = {}
        for r in filtered:
            lookup[(r["category"], r["country"])] = r["priority_date"]

        rows = []
        for cat in ordered_cats:
            row = {"Category": cat}
            for country in ordered_countries:
                val = lookup.get((cat, country), "")
                row[country] = val
            rows.append(row)

        df = pd.DataFrame(rows).set_index("Category")
        st.dataframe(df, use_container_width=True)

# ── Trend ────────────────────────────────────────────────────────────────────

elif page == "Trend":
    st.header("Trend Analysis")

    all_countries = get_all_countries()
    all_eb_cats = get_all_categories("employment")
    all_fam_cats = get_all_categories("family")
    all_cats = all_eb_cats + all_fam_cats

    if not all_cats:
        st.info("Import some bulletins first to see trends.")
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        trend_visa_type = st.selectbox("Visa Type", ["Employment", "Family"], key="trend_visa")
    with col2:
        cats_for_type = all_eb_cats if trend_visa_type == "Employment" else all_fam_cats
        default_cat = ["EB-2"] if "EB-2" in cats_for_type else cats_for_type[:1]
        selected_cats = st.multiselect("Categories", cats_for_type, default=default_cat if cats_for_type else [])
    with col3:
        default_country = ["India"] if "India" in all_countries else all_countries[:1]
        selected_countries = st.multiselect("Countries", all_countries, default=default_country if all_countries else [])

    trend_table = st.radio("Table Type", ["Final Action", "Filing"], horizontal=True, key="trend_table")
    trend_table_key = "final_action" if trend_table == "Final Action" else "filing"
    trend_visa_key = trend_visa_type.lower()

    if selected_cats and selected_countries:
        series = {}
        for cat in selected_cats:
            for country in selected_countries:
                label = f"{cat} - {country}" if len(selected_cats) > 1 or len(selected_countries) > 1 else cat
                data = get_trend_data(cat, country, trend_table_key, trend_visa_key)
                if data:
                    series[label] = data

        if series:
            if len(series) == 1:
                label, data = next(iter(series.items()))
                fig = plot_trend(data, title=f"{label} ({trend_table} Dates)")
            else:
                fig = plot_multi_trend(series, title=f"Priority Date Comparison ({trend_table} Dates)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data for this selection.")
    else:
        st.info("Select at least one category and one country.")

# ── Compare ──────────────────────────────────────────────────────────────────

elif page == "Compare":
    from datetime import datetime as dt

    st.header("Compare Months")

    cmp_countries = get_all_countries()
    cmp_eb_cats = get_all_categories("employment")
    cmp_fam_cats = get_all_categories("family")

    if not cmp_eb_cats and not cmp_fam_cats:
        st.info("Import some bulletins first to compare.")
        st.stop()

    col1, col2 = st.columns(2)
    with col1:
        month_a = st.selectbox("Month A", available_months, index=min(1, len(available_months) - 1), key="cmp_month_a")
    with col2:
        month_b = st.selectbox("Month B", available_months, index=0, key="cmp_month_b")

    col1, col2, col3 = st.columns(3)
    with col1:
        cmp_visa_type = st.selectbox("Visa Type", ["Employment", "Family"], key="cmp_visa")
    with col2:
        default_cmp_country = cmp_countries.index("India") if "India" in cmp_countries else 0
        cmp_country = st.selectbox("Country", cmp_countries, index=default_cmp_country, key="cmp_country")
    with col3:
        cmp_table_type = st.radio("Table Type", ["Final Action", "Filing"], horizontal=True, key="cmp_table")

    cmp_table_key = "final_action" if cmp_table_type == "Final Action" else "filing"
    cmp_visa_key = cmp_visa_type.lower()

    data_a = get_dates_for_month(month_a)
    data_b = get_dates_for_month(month_b)

    def find_date(data, table_type, visa_type, category, country):
        for r in data:
            if (r["table_type"] == table_type and r["visa_type"] == visa_type
                    and r["category"] == category and r["country"] == country):
                return r["priority_date"]
        return None

    def calc_movement(val_a, val_b):
        """Return movement string: +N days, -N days, or descriptive text."""
        if not val_a or not val_b:
            return ""
        if val_a not in ("C", "U") and val_b not in ("C", "U"):
            try:
                da = dt.strptime(val_a, "%Y-%m-%d")
                db = dt.strptime(val_b, "%Y-%m-%d")
                delta = (db - da).days
                sign = "+" if delta > 0 else ""
                return f"{sign}{delta}"
            except ValueError:
                return ""
        if val_a == "C" and val_b == "C":
            return "Current"
        if val_b == "C":
            return "Became Current"
        if val_a == "C":
            return "Retrogressed"
        return ""

    cmp_cats_list = cmp_eb_cats if cmp_visa_type == "Employment" else cmp_fam_cats
    if cmp_visa_key == "employment":
        cat_order = [
            "EB-1", "EB-2", "EB-3", "EB-3 Other Workers", "EB-4",
            "EB-4 Religious Workers", "EB-5 Unreserved", "EB-5 Rural",
            "EB-5 High Unemployment", "EB-5 Infrastructure",
        ]
    else:
        cat_order = ["F1", "F2A", "F2B", "F3", "F4"]

    ordered_cats = [c for c in cat_order if c in cmp_cats_list]
    ordered_cats += [c for c in cmp_cats_list if c not in ordered_cats]

    st.markdown(f"### {cmp_country} — {cmp_table_type} Dates")

    rows = []
    for cat in ordered_cats:
        da_val = find_date(data_a, cmp_table_key, cmp_visa_key, cat, cmp_country) or ""
        db_val = find_date(data_b, cmp_table_key, cmp_visa_key, cat, cmp_country) or ""
        movement = calc_movement(da_val, db_val)
        rows.append({"Category": cat, month_a: da_val, month_b: db_val, "Movement (days)": movement})

    if rows:
        df = pd.DataFrame(rows).set_index("Category")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No data for this selection.")
