from datetime import datetime, date

import plotly.graph_objects as go


def parse_priority_date_for_chart(pd_str, bulletin_month=None):
    """Convert a priority date string to a date for plotting.
    'C' → first of the bulletin month (current means that month), 'U' → None (gap).
    """
    if pd_str == "C":
        if bulletin_month:
            try:
                return datetime.strptime(bulletin_month + "-01", "%Y-%m-%d").date()
            except ValueError:
                pass
        return date.today()
    if pd_str == "U":
        return None
    try:
        return datetime.strptime(pd_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _apply_common_layout(fig, title):
    """Apply shared axis formatting to a figure."""
    fig.update_layout(
        title=title,
        xaxis_title="Bulletin Month",
        yaxis_title="Priority Date",
        hovermode="x unified",
        template="plotly_white",
        height=500,
    )
    # X-axis: treat bulletin months as categories, 1 tick per month
    fig.update_xaxes(type="category", tickangle=45)
    # Y-axis: date only, no time
    fig.update_yaxes(tickformat="%Y-%m-%d")


def plot_trend(trend_data, title="Priority Date Trend"):
    """Create a Plotly line chart from trend data.

    trend_data: list of dicts with 'bulletin_month' and 'priority_date' keys.
    """
    months = []
    dates = []
    current_markers = []  # indices where date is 'C'

    for row in trend_data:
        bm = row["bulletin_month"]
        pd_val = row["priority_date"]
        chart_date = parse_priority_date_for_chart(pd_val, bm)
        if chart_date is not None:
            months.append(bm)
            dates.append(chart_date)
            if pd_val == "C":
                current_markers.append(len(months) - 1)

    if not months:
        fig = go.Figure()
        fig.add_annotation(text="No data available", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=16))
        fig.update_layout(title=title)
        return fig

    fig = go.Figure()

    # Main line
    fig.add_trace(go.Scatter(
        x=months,
        y=dates,
        mode="lines+markers",
        name="Priority Date",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=5),
        connectgaps=False,
    ))

    # Highlight 'Current' points
    if current_markers:
        fig.add_trace(go.Scatter(
            x=[months[i] for i in current_markers],
            y=[dates[i] for i in current_markers],
            mode="markers",
            name="Current",
            marker=dict(color="green", size=10, symbol="star"),
        ))

    _apply_common_layout(fig, title)
    return fig


def plot_multi_trend(trend_data_dict, title="Priority Date Comparison"):
    """Plot multiple series on one chart.

    trend_data_dict: dict of {label: trend_data} where trend_data is list of
    dicts with 'bulletin_month' and 'priority_date'.
    """
    fig = go.Figure()

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
              "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

    for i, (label, data) in enumerate(trend_data_dict.items()):
        months = []
        dates = []
        for row in data:
            chart_date = parse_priority_date_for_chart(row["priority_date"], row["bulletin_month"])
            if chart_date is not None:
                months.append(row["bulletin_month"])
                dates.append(chart_date)

        if months:
            fig.add_trace(go.Scatter(
                x=months,
                y=dates,
                mode="lines+markers",
                name=label,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=4),
                connectgaps=False,
            ))

    _apply_common_layout(fig, title)
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig
