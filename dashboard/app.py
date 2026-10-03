import os
from datetime import datetime, timedelta, timezone

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html
from dotenv import load_dotenv
from pymongo import MongoClient
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

load_dotenv("config/.env")

mongo = MongoClient(
    os.getenv("MONGODB_STRING", "mongodb://localhost:27017/")
)["incidentiq"]["unified_posts"]

qdrant = QdrantClient(host="127.0.0.1", port=6333)
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
QCOL = "post_vectors"

CRISIS_META = {
    "war": {"icon": "🚨", "label": "War", "accent": "#ef4444"},
    "pandemic": {"icon": "🦠", "label": "Pandemic", "accent": "#8b5cf6"},
    "cyberattack": {"icon": "💻", "label": "Cyberattack", "accent": "#3b82f6"},
    "terrorist_attack": {"icon": "⚠️", "label": "Terrorist Attack", "accent": "#f97316"},
    "natural_disaster": {"icon": "🌪️", "label": "Natural Disaster", "accent": "#eab308"},
    "civil_unrest": {"icon": "🔥", "label": "Civil Unrest", "accent": "#f59e0b"},
    "crime": {"icon": "🚓", "label": "Crime", "accent": "#64748b"},
    "financial_crisis": {"icon": "📉", "label": "Financial Crisis", "accent": "#06b6d4"},
    "infrastructure_failure": {"icon": "🏗️", "label": "Infrastructure Failure", "accent": "#a855f7"},
    "environmental_crisis": {"icon": "🌿", "label": "Environmental Crisis", "accent": "#22c55e"},
}

BG = "#0b1020"
PANEL = "#111827"
PANEL_2 = "#0f172a"
BORDER = "#243047"
TEXT = "#f8fafc"
MUTED = "#94a3b8"
GRID = "rgba(148,163,184,0.12)"
BLUE = "#60a5fa"

GRAPH_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
}


def crisis_label(value: str) -> str:
    return CRISIS_META.get(value, {}).get(
        "label",
        value.replace("_", " ").title()
    )


def crisis_icon(value: str) -> str:
    return CRISIS_META.get(value, {}).get("icon", "⚠️")


def crisis_accent(value: str) -> str:
    return CRISIS_META.get(value, {}).get("accent", "#64748b")


def format_timestamp(value):
    if not value:
        return "Unknown time"

    try:
        dt = pd.to_datetime(value, utc=True)
        return dt.strftime("%b %d · %I:%M %p UTC")
    except Exception:
        return str(value)


def style_figure(fig, height=300, margin=None):
    fig.update_layout(
        template=None,
        height=height,
        margin=margin or dict(l=42, r=20, t=48, b=40),
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(
            color=TEXT,
            family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
        ),
        title_font=dict(size=16, color=TEXT),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED)
        ),
        hoverlabel=dict(
            bgcolor="#0f172a",
            font_color=TEXT
        ),
    )

    fig.update_xaxes(
        color=MUTED,
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        linecolor="rgba(148,163,184,0.18)",
    )

    fig.update_yaxes(
        color=MUTED,
        showgrid=True,
        gridcolor=GRID,
        zeroline=False,
        linecolor="rgba(148,163,184,0.18)",
    )

    return fig


def get_count_by_type_over_time(from_date=None, to_date=None, unit="minute"):
    match_stage = {}

    if from_date or to_date:
        match_stage["timestamp"] = {}

        if from_date:
            if isinstance(from_date, datetime):
                from_date = from_date.isoformat()
            match_stage["timestamp"]["$gte"] = from_date

        if to_date:
            if isinstance(to_date, datetime):
                to_date = to_date.isoformat()
            match_stage["timestamp"]["$lte"] = to_date

    date_format = {
        "minute": "%Y-%m-%d %H:%M:00",
        "hour": "%Y-%m-%d %H:00:00",
        "day": "%Y-%m-%d 00:00:00",
    }

    pipeline = [
        {"$match": match_stage} if match_stage else {"$match": {}},

        {
            "$addFields": {
                "timestamp_date": {
                    "$dateFromString": {
                        "dateString": "$timestamp",
                        "timezone": "UTC",
                    }
                }
            }
        },

        {
            "$project": {
                "crisis_type": 1,
                "date_str": {
                    "$dateToString": {
                        "format": date_format.get(
                            unit,
                            "%Y-%m-%d %H:%M:00"
                        ),
                        "date": "$timestamp_date",
                    }
                },
            }
        },

        {
            "$group": {
                "_id": {
                    "crisis_type": "$crisis_type",
                    "date": "$date_str"
                },
                "count": {"$sum": 1},
            }
        },

        {"$sort": {"_id.date": 1}},

        {
            "$project": {
                "_id": 0,
                "crisis_type": "$_id.crisis_type",
                "date": "$_id.date",
                "count": "$count",
            }
        },
    ]

    try:
        result = list(mongo.aggregate(pipeline))
        df = pd.DataFrame(result)

        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["crisis_type"].notna()]
            df = df[~df["crisis_type"].isin(["none", ""])]

        return df

    except Exception as exc:
        print(f"Error in get_count_by_type_over_time: {exc}")
        return pd.DataFrame()


def draw_initial_time_series():
    end_time = datetime.now(timezone.utc).replace(
        second=0,
        microsecond=0
    )
    start_time = end_time - timedelta(hours=12)

    df = get_count_by_type_over_time(
        from_date=start_time.isoformat(),
        to_date=end_time.isoformat(),
        unit="minute",
    )

    fig = go.Figure()

    if not df.empty:
        total_by_time = (
            df.groupby("date")["count"]
            .sum()
            .reset_index()
        )

        if len(total_by_time) > 10:
            total_by_time = (
                total_by_time
                .set_index("date")
                .resample("30min")
                .sum()
                .reset_index()
            )

        total_by_time = total_by_time.sort_values("date")

        fig.add_trace(
            go.Scatter(
                x=total_by_time["date"],
                y=total_by_time["count"],
                mode="lines",
                line=dict(
                    color=BLUE,
                    width=2.5,
                    shape="spline",
                    smoothing=1.1,
                ),
                fill="tozeroy",
                fillcolor="rgba(96,165,250,0.10)",
                hovertemplate=(
                    "%{x|%I:%M %p}<br>"
                    "<b>%{y}</b> reports"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title="Incident volume over time",
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        hovermode="x unified",
    )

    fig.update_xaxes(tickformat="%H:%M")

    return style_figure(fig, height=280)


def draw_crisis_distribution_bar():
    from_date = datetime.now(timezone.utc) - timedelta(hours=6)
    to_date = datetime.now(timezone.utc)

    df = get_count_by_type_over_time(
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        unit="hour",
    )

    if df.empty:
        fig = go.Figure()

        fig.add_annotation(
            text="No recent classified incidents",
            showarrow=False,
            font=dict(
                color=MUTED,
                size=15
            ),
        )

        fig.update_layout(
            title="Incident mix · last 6 hours"
        )

        return style_figure(
            fig,
            height=300
        )

    total_df = (
        df.groupby("crisis_type")["count"]
        .sum()
        .reset_index()
        .sort_values("count", ascending=True)
    )

    total_df["label"] = total_df["crisis_type"].map(
        crisis_label
    )

    total_df["accent"] = total_df["crisis_type"].map(
        crisis_accent
    )

    fig = go.Figure(
        go.Bar(
            x=total_df["count"],
            y=total_df["label"],
            orientation="h",
            marker=dict(
                color=total_df["accent"],
                line=dict(width=0)
            ),
            text=total_df["count"],
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{x} mentions"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title="Incident mix · last 6 hours",
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        bargap=0.35,
    )

    fig.update_xaxes(
        showgrid=False,
        showticklabels=False
    )

    return style_figure(
        fig,
        height=300,
        margin=dict(
            l=120,
            r=32,
            t=48,
            b=20
        )
    )


def draw_crisis_heatmap():
    from_date = datetime.now(timezone.utc) - timedelta(days=1)
    to_date = datetime.now(timezone.utc)

    df = get_count_by_type_over_time(
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        unit="hour",
    )

    if df.empty:
        fig = go.Figure()

        fig.add_annotation(
            text="No heatmap data available",
            showarrow=False,
            font=dict(
                color=MUTED,
                size=15
            ),
        )

        fig.update_layout(
            title="Activity by type · last 24 hours"
        )

        return style_figure(
            fig,
            height=300
        )

    df["hour"] = df["date"].dt.strftime("%H:%M")
    df["label"] = df["crisis_type"].map(crisis_label)

    df = (
        df.groupby(["label", "hour"])["count"]
        .sum()
        .reset_index()
    )

    pivot = df.pivot(
        index="label",
        columns="hour",
        values="count"
    ).fillna(0)

    fig = px.imshow(
        pivot,
        labels=dict(
            x="Hour",
            y="",
            color="Mentions"
        ),
        aspect="auto",
        color_continuous_scale=[
            [0.0, "#111827"],
            [0.25, "#1d4ed8"],
            [0.55, "#0ea5e9"],
            [1.0, "#f59e0b"],
        ],
    )

    fig.update_layout(
        title="Activity by type · last 24 hours",
        coloraxis_colorbar=dict(
            title="",
            thickness=8,
            len=0.6,
            tickfont=dict(color=MUTED),
        ),
    )

    fig.update_xaxes(tickangle=0)

    return style_figure(
        fig,
        height=300,
        margin=dict(
            l=130,
            r=24,
            t=48,
            b=40
        )
    )


app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    suppress_callback_exceptions=True,
)

app.title = "IncidentIQ"

app.index_string = f"""
<!DOCTYPE html>
<html>
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        {{%favicon%}}
        {{%css%}}

        <style>
            :root {{
                --bg: {BG};
                --panel: {PANEL};
                --panel2: {PANEL_2};
                --border: {BORDER};
                --text: {TEXT};
                --muted: {MUTED};
            }}

            * {{
                box-sizing: border-box;
            }}

            html, body {{
                background: var(--bg);
                color: var(--text);
                margin: 0;
                font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }}

            body {{
                min-height: 100vh;
            }}

            a {{
                color: #93c5fd;
                text-decoration: none;
            }}

            a:hover {{
                color: #bfdbfe;
            }}

            .app-shell {{
                max-width: 1500px;
                margin: 0 auto;
                padding: 20px 24px 28px;
            }}

            .topbar {{
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                padding: 4px 0 18px;
            }}

            .brand-row {{
                display: flex;
                align-items: center;
                gap: 12px;
            }}

            .brand-mark {{
                width: 38px;
                height: 38px;
                border-radius: 12px;
                background: linear-gradient(
                    135deg,
                    #2563eb,
                    #06b6d4
                );
                display: grid;
                place-items: center;
                font-size: 20px;
                box-shadow: 0 8px 24px rgba(37,99,235,.25);
            }}

            .brand-title {{
                font-size: 22px;
                font-weight: 700;
                letter-spacing: -0.02em;
                line-height: 1.1;
            }}

            .brand-subtitle {{
                color: var(--muted);
                font-size: 13px;
                margin-top: 3px;
            }}

            .live-pill {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 11px;
                border: 1px solid #1f3b2b;
                border-radius: 999px;
                background: rgba(34,197,94,.08);
                color: #86efac;
                font-size: 12px;
                font-weight: 600;
            }}

            .live-dot {{
                width: 7px;
                height: 7px;
                border-radius: 50%;
                background: #22c55e;
                box-shadow: 0 0 0 4px rgba(34,197,94,.12);
            }}

            .nav-tabs {{
                margin-bottom: 18px;
            }}

            .nav-tabs .tab {{
                background: transparent !important;
                border: none !important;
                color: var(--muted) !important;
                padding: 10px 14px !important;
                font-weight: 600;
            }}

            .nav-tabs .tab--selected {{
                color: var(--text) !important;
                border-bottom: 2px solid #60a5fa !important;
            }}

            .section-title {{
                font-size: 15px;
                font-weight: 700;
                letter-spacing: .01em;
                margin: 0 0 12px;
            }}

            .muted {{
                color: var(--muted);
            }}

            .panel {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 12px 30px rgba(0,0,0,.14);
            }}

            .panel-pad {{
                padding: 16px;
            }}

            .feed-scroll {{
                display: flex;
                flex-direction: column;
                gap: 12px;
                max-height: calc(100vh - 165px);
                overflow-y: auto;
                padding-right: 4px;
            }}

            .feed-scroll::-webkit-scrollbar {{
                width: 6px;
            }}

            .feed-scroll::-webkit-scrollbar-thumb {{
                background: #334155;
                border-radius: 999px;
            }}

            .incident-card {{
                position: relative;
                background: var(--panel2);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 16px 15px 13px 17px;
                transition:
                    transform .14s ease,
                    border-color .14s ease,
                    background .14s ease;
                overflow: visible;
            }}

            .incident-card:hover {{
                transform: translateY(-1px);
                border-color: #334155;
                background: #131d31;
            }}

            .incident-accent {{
                position: absolute;
                left: 0;
                top: 0;
                bottom: 0;
                width: 4px;
                border-radius: 14px 0 0 14px;
            }}

            .incident-title {{
                font-size: 15px;
                line-height: 1.45;
                font-weight: 650;
                color: var(--text);
                margin: 0 0 12px;
            }}

            .incident-meta {{
                display: flex;
                flex-wrap: wrap;
                align-items: center;
                gap: 8px;
                color: var(--muted);
                font-size: 12px;
            }}

            .type-chip {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                border-radius: 999px;
                padding: 4px 8px;
                font-weight: 700;
                font-size: 11px;
            }}

            .source-link {{
                margin-left: auto;
                font-size: 12px;
                font-weight: 600;
            }}

            .chart-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 16px;
                overflow: hidden;
                margin-bottom: 12px;
            }}

            .chart-card .js-plotly-plot,
            .chart-card .plot-container {{
                border-radius: 16px;
            }}

            .search-wrap {{
                max-width: 960px;
                margin: 0 auto;
            }}

            .search-input {{
                width: 100%;
                background: var(--panel2);
                color: var(--text);
                border: 1px solid var(--border);
                border-radius: 12px;
                padding: 13px 14px;
                outline: none;
            }}

            .search-input:focus {{
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59,130,246,.12);
            }}

            .search-card {{
                background: var(--panel);
                border: 1px solid var(--border);
                border-radius: 14px;
                padding: 15px;
                margin-top: 10px;
            }}

            @media (max-width: 992px) {{
                .feed-scroll {{
                    max-height: none;
                    overflow: visible;
                }}
            }}
        </style>
    </head>

    <body>
        {{%app_entry%}}

        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>
"""


def feed_panel():
    return html.Div(
        className="panel panel-pad",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.Div(
                                "Live incident feed",
                                className="section-title"
                            ),
                            html.Div(
                                "Classified in real time from incoming sources",
                                className="muted",
                                style={"fontSize": "12px"},
                            ),
                        ]
                    ),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "end",
                    "marginBottom": "14px",
                },
            ),

            html.Div(
                id="feed-container",
                className="feed-scroll"
            ),

            dcc.Interval(
                id="feed-interval",
                interval=10 * 1000,
                n_intervals=0
            ),
        ],
    )


def analytics_panel():
    return html.Div(
        [
            html.Div(
                dcc.Graph(
                    id="crisis-bar-chart",
                    config=GRAPH_CONFIG,
                    style={"height": "300px"},
                ),
                className="chart-card",
            ),

            html.Div(
                dcc.Graph(
                    id="time-series",
                    figure=draw_initial_time_series(),
                    config=GRAPH_CONFIG,
                    style={"height": "280px"},
                ),
                className="chart-card",
            ),

            html.Div(
                dcc.Graph(
                    id="crisis-heatmap",
                    config=GRAPH_CONFIG,
                    style={"height": "300px"},
                ),
                className="chart-card",
            ),

            dcc.Interval(
                id="analytics-interval",
                interval=20 * 1000,
                n_intervals=0
            ),

            dcc.Interval(
                id="time-series-interval",
                interval=20 * 1000,
                n_intervals=0
            ),

            dcc.Interval(
                id="heatmap-interval",
                interval=20 * 1000,
                n_intervals=0
            ),
        ]
    )


app.layout = html.Div(
    className="app-shell",
    children=[
        html.Div(
            className="topbar",
            children=[
                html.Div(
                    className="brand-row",
                    children=[
                        html.Div(
                            "IQ",
                            className="brand-mark"
                        ),

                        html.Div(
                            [
                                html.Div(
                                    "IncidentIQ",
                                    className="brand-title"
                                ),

                                html.Div(
                                    "Live crisis intelligence",
                                    className="brand-subtitle",
                                ),
                            ]
                        ),
                    ],
                ),

                html.Div(
                    className="live-pill",
                    children=[
                        html.Span(className="live-dot"),
                        html.Span("Pipeline live"),
                    ],
                ),
            ],
        ),

        dcc.Tabs(
            className="nav-tabs",
            children=[
                dcc.Tab(
                    label="Live Feed",
                    className="tab",
                    selected_className="tab--selected",
                    children=[
                        dbc.Row(
                            [
                                dbc.Col(
                                    feed_panel(),
                                    lg=6,
                                    md=12,
                                    className="mb-3"
                                ),

                                dbc.Col(
                                    analytics_panel(),
                                    lg=6,
                                    md=12,
                                    className="mb-3"
                                ),
                            ],
                            className="g-3",
                        )
                    ],
                ),

                dcc.Tab(
                    label="Semantic Search",
                    className="tab",
                    selected_className="tab--selected",
                    children=[
                        html.Div(
                            className="search-wrap",
                            children=[
                                html.Div(
                                    "Search incidents semantically",
                                    className="section-title",
                                    style={
                                        "fontSize": "18px",
                                        "marginTop": "18px"
                                    },
                                ),

                                html.Div(
                                    "Query the vector index by meaning, not only exact keywords.",
                                    className="muted",
                                    style={
                                        "fontSize": "13px",
                                        "marginBottom": "14px"
                                    },
                                ),

                                dcc.Input(
                                    id="search-input",
                                    placeholder="Try: infrastructure failures in Europe",
                                    type="text",
                                    debounce=True,
                                    className="search-input",
                                ),

                                html.Div(
                                    id="search-results"
                                ),
                            ],
                        )
                    ],
                ),
            ],
        ),
    ],
)


@app.callback(
    Output("feed-container", "children"),
    Input("feed-interval", "n_intervals"),
)
def update_feed(_):
    raw = list(
        mongo.find(
            {"crisis_type": {"$ne": "none"}}
        )
        .sort("timestamp", -1)
        .limit(50)
    )

    seen_titles = set()
    unique = []

    for doc in raw:
        title = doc.get(
            "title",
            ""
        ).strip().lower()

        if title and title not in seen_titles:
            seen_titles.add(title)
            unique.append(doc)

        if len(unique) >= 10:
            break

    cards = []

    for doc in unique:
        crisis = doc.get(
            "crisis_type",
            "none"
        )

        accent = crisis_accent(crisis)
        label = crisis_label(crisis)
        icon = crisis_icon(crisis)

        cards.append(
            html.Div(
                className="incident-card",
                children=[
                    html.Div(
                        className="incident-accent",
                        style={"background": accent},
                    ),

                    html.Div(
                        doc.get(
                            "title",
                            "(untitled)"
                        ),
                        className="incident-title",
                    ),

                    html.Div(
                        className="incident-meta",
                        children=[
                            html.Span(
                                [
                                    html.Span(icon),
                                    html.Span(label),
                                ],
                                className="type-chip",
                                style={
                                    "background": f"{accent}1A",
                                    "color": accent,
                                    "border": f"1px solid {accent}33",
                                },
                            ),

                            html.Span(
                                format_timestamp(
                                    doc.get("timestamp")
                                )
                            ),

                            html.Span("•"),

                            html.Span(
                                doc.get(
                                    "source",
                                    "Unknown source"
                                )
                            ),

                            html.A(
                                "Open source ↗",
                                href=doc.get(
                                    "url",
                                    "#"
                                ),
                                target="_blank",
                                className="source-link",
                            ),
                        ],
                    ),
                ],
            )
        )

    if not cards:
        return [
            html.Div(
                "No classified incidents available yet.",
                className="muted",
                style={"padding": "18px 4px"},
            )
        ]

    return cards


@app.callback(
    Output("search-results", "children"),
    Input("search-input", "value"),
)
def run_search(q):
    if not q:
        return ""

    vec = embed_model.encode(q).tolist()

    raw_hits = qdrant.search(
        collection_name=QCOL,
        query_vector=vec,
        limit=20,
    )

    seen_titles = set()
    unique_hits = []

    for hit in raw_hits:
        title = hit.payload.get(
            "title",
            ""
        ).strip().lower()

        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_hits.append(hit)

        if len(unique_hits) >= 5:
            break

    results = []

    for i, hit in enumerate(
        unique_hits,
        1
    ):
        payload = hit.payload

        crisis = payload.get(
            "crisis_type",
            "none"
        )

        accent = crisis_accent(crisis)

        results.append(
            html.Div(
                className="search-card",
                children=[
                    html.Div(
                        [
                            html.Span(
                                f"{i:02d}",
                                style={
                                    "color": MUTED,
                                    "fontSize": "11px",
                                    "marginRight": "10px",
                                },
                            ),

                            html.Span(
                                f"{crisis_icon(crisis)} {crisis_label(crisis)}",
                                style={
                                    "color": accent,
                                    "fontWeight": "700",
                                    "fontSize": "12px",
                                },
                            ),

                            html.Span(
                                f"Similarity {hit.score:.2f}",
                                style={
                                    "color": MUTED,
                                    "fontSize": "11px",
                                    "float": "right",
                                },
                            ),
                        ],
                        style={
                            "marginBottom": "8px"
                        },
                    ),

                    html.Div(
                        payload.get(
                            "title",
                            "(no title)"
                        ),
                        style={
                            "fontSize": "15px",
                            "fontWeight": "650",
                            "lineHeight": "1.4",
                        },
                    ),

                    html.A(
                        "Open source ↗",
                        href=payload.get(
                            "url",
                            "#"
                        ),
                        target="_blank",
                        style={
                            "display": "inline-block",
                            "marginTop": "8px",
                            "fontSize": "12px",
                            "fontWeight": "600",
                        },
                    ),
                ],
            )
        )

    if not results:
        return html.Div(
            "No semantic matches found.",
            className="muted",
            style={"marginTop": "14px"},
        )

    return results


@app.callback(
    Output("time-series", "figure"),
    Input("time-series-interval", "n_intervals"),
)
def update_time_series(_):
    return draw_initial_time_series()


@app.callback(
    Output("crisis-bar-chart", "figure"),
    Input("analytics-interval", "n_intervals"),
)
def update_crisis_bar_chart(_):
    return draw_crisis_distribution_bar()


@app.callback(
    Output("crisis-heatmap", "figure"),
    Input("heatmap-interval", "n_intervals"),
)
def update_crisis_heatmap(_):
    return draw_crisis_heatmap()


if __name__ == "__main__":
    app.run(
        debug=False,
        port=4567
    )