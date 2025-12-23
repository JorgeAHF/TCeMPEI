import os
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
import httpx
from dash import Input, Output, State, dash_table, dcc, html
import base64
import json
import plotly.express as px
import pandas as pd

"""
UI simple para visualizar el avance:
- Catálogo: alta de puente, tipo de torón y tirante + tablas.
- Adquisiciones: alta de campaña.
- Pesajes: alta de campaña.
- Análisis: alta de run y guardar resultado de tirante.
- Semáforo: consulta básica por puente/campaña.
BACKEND_URL configurable (default http://localhost:8000).
"""

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY], suppress_callback_exceptions=True)


def call_api(method: str, path: str, **kwargs):
    url = f"{BACKEND_URL}{path}"
    token = os.getenv("DASH_TOKEN") or kwargs.pop("token", None)
    headers = kwargs.pop("headers", {}) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


sidebar = dbc.Nav(
    [
        dbc.NavLink("Home", href="/", active="exact"),
        dbc.NavLink("Catálogo", href="/catalogo", active="exact"),
        dbc.NavLink("Adquisiciones", href="/adquisiciones", active="exact"),
        dbc.NavLink("Pesajes directos", href="/pesajes", active="exact"),
        dbc.NavLink("Análisis", href="/analisis", active="exact"),
        dbc.NavLink("Histórico", href="/historico", active="exact"),
        dbc.NavLink("Semáforo", href="/semaforo", active="exact"),
        dbc.NavLink("Admin", href="/admin", active="exact"),
    ],
    vertical=True,
    pills=True,
)


def home_page():
    return dbc.Container(
        [
            html.H3("TCeMPEI"),
            html.P("Plataforma interna para gestión histórica y análisis de tirantes."),
            html.Ul(
                [
                    html.Li("Usa el menú para acceder a Catálogo, Adquisiciones, Pesajes, Análisis, Histórico y Semáforo."),
                    html.Li("Requiere login (token JWT) para operaciones de alta (roles admin/analyst)."),
                ]
            ),
            html.H5("Login"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="login-user", placeholder="usuario", type="text"), md=4),
                    dbc.Col(dbc.Input(id="login-pass", placeholder="contraseña", type="password"), md=4),
                    dbc.Col(dbc.Button("Ingresar", id="login-submit", color="primary"), md=2),
                ],
                className="gy-2",
            ),
            html.Div(id="token-status", className="mt-2"),
        ],
        fluid=True,
    )


def catalogo_page():
    return dbc.Container(
        [
            html.H3("Catálogo"),
            html.P("Wizard rápido: selecciona/crea puente → renombra tirantes → define estado por tirante."),
            dbc.Button("Cargar catálogo", id="refresh-catalogo", color="secondary", className="mb-2"),
            html.Div(id="catalogo-status", className="mb-2"),
            html.H5("Paso 1: Puentes (editable)"),
            dash_table.DataTable(
                id="bridges-table",
                columns=[
                    {"name": "id", "id": "id"},
                    {"name": "nombre", "id": "nombre", "editable": True},
                    {"name": "clave", "id": "clave_interna", "editable": True},
                    {"name": "num_tirantes", "id": "num_tirantes", "editable": True},
                    {"name": "notas", "id": "notas", "editable": True},
                ],
                editable=True,
                row_selectable="single",
                style_table={"maxHeight": "300px", "overflowY": "auto"},
            ),
            html.Button("Agregar fila de puente", id="bridge-add-row", n_clicks=0, className="btn btn-secondary btn-sm my-2"),
            dbc.Button("Guardar cambios de puentes", id="bridges-save", color="primary", className="mb-3"),
            html.Div(id="br-edit-status", className="mb-3"),
            html.Hr(),
            html.P("Una vez creado el puente, define tirantes y sus estados."),
            html.H5("Paso 2: Tirantes del puente seleccionado"),
            dash_table.DataTable(
                id="cables-table",
                columns=[
                    {"name": "id", "id": "id"},
                    {"name": "nombre_en_puente", "id": "nombre_en_puente"},
                    {"name": "notas", "id": "notas"},
                ],
                row_selectable="single",
                style_table={"maxHeight": "240px", "overflowY": "auto"},
            ),
            html.Br(),
            html.H6("Edición rápida de tirantes (nombre/notas)"),
            dash_table.DataTable(
                id="cables-edit-table",
                columns=[
                    {"name": "id", "id": "id"},
                    {"name": "nombre_en_puente", "id": "nombre_en_puente", "editable": True},
                    {"name": "notas", "id": "notas", "editable": True},
                ],
                editable=True,
                style_table={"maxHeight": "240px", "overflowY": "auto"},
            ),
            dbc.Button("Guardar tirantes editados", id="cables-edit-save", color="secondary", className="mt-2"),
            html.Div(id="cables-edit-status", className="mb-3"),
            html.H5("Tipo de torón"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="st-nombre", placeholder="Nombre"), md=2),
                    dbc.Col(dbc.Input(id="st-diam", placeholder="diametro_mm", type="number"), md=2),
                    dbc.Col(dbc.Input(id="st-area", placeholder="area_mm2", type="number"), md=2),
                    dbc.Col(dbc.Input(id="st-e", placeholder="E_MPa", type="number"), md=2),
                    dbc.Col(dbc.Input(id="st-fu", placeholder="Fu_default", type="number"), md=2),
                    dbc.Col(dbc.Input(id="st-mu", placeholder="mu_por_toron_kg_m", type="number"), md=2),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="st-notas", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear tipo torón", id="st-submit", color="primary", className="mb-3"),
            html.Div(id="st-status", className="mb-3"),
            html.H5("Tirante"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="cb-bridge", placeholder="bridge_id", type="number"), md=4),
                    dbc.Col(dbc.Input(id="cb-nombre", placeholder="nombre_en_puente"), md=4),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="cb-notas", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear tirante", id="cb-submit", color="primary", className="mb-3"),
            html.Div(id="cb-status", className="mb-3"),
            html.H6("Renombrar tirante (placeholders T-XX)"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="cb-id-edit", placeholder="cable_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="cb-nombre-edit", placeholder="Nuevo nombre en puente"), md=5),
                    dbc.Col(dbc.Button("Guardar nombre", id="cb-edit-submit", color="secondary"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            html.Div(id="cb-edit-status", className="mb-3"),
            html.H5("Versión de estado de tirante"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="stv-cable", placeholder="cable_id", type="number"), md=2),
                    dbc.Col(dbc.Input(id="stv-from", placeholder="valid_from (YYYY-MM-DD HH:MM)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="stv-to", placeholder="valid_to (opcional)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="stv-strand-type", placeholder="strand_type_id", type="number"), md=2),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="stv-length", placeholder="length_effective_m", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-strands-total", placeholder="strands_total", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-strands-active", placeholder="strands_active", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-fu-ovr", placeholder="Fu_override (opcional)", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="stv-mu-total", placeholder="mu_total_kg_m", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-mu-active", placeholder="mu_active_basis_kg_m", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-E", placeholder="E_MPa", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-area", placeholder="area_mm2", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="stv-diam", placeholder="diametro_mm", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-design", placeholder="design_tension_tf", type="number"), md=3),
                    dbc.Col(dbc.Input(id="stv-anti", placeholder="antivandalic_length_m (opcional)", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="stv-notes", placeholder="Notas / source", className="mb-2"),
            dbc.Button("Crear versión", id="stv-submit", color="primary", className="mb-3"),
            html.Div(id="stv-status", className="mb-3"),
            html.Hr(),
            dbc.Button("Refrescar tablas", id="refresh-catalogo", color="secondary", className="mb-2"),
            html.Div(id="catalogo-tables"),
        ],
        fluid=True,
    )


def acquisition_page():
    return dbc.Container(
        [
            html.H3("Adquisición"),
            dcc.Store(id="raw-headers-store"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="acq-bridge", placeholder="bridge_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="acq-date", placeholder="YYYY-MM-DD HH:MM", type="text"), md=3),
                    dbc.Col(dbc.Input(id="acq-operator", placeholder="operator_user_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="acq-fs", placeholder="Fs_Hz", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="acq-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear adquisición", id="acq-submit", color="primary"),
            html.Div(id="acq-status", className="mt-2"),
            html.Hr(),
            html.H5("Paso 2: subir CSV crudo (DATA_START)"),
            dcc.Upload(id="raw-upload", children=html.Div(["Arrastra o haz click para subir CSV"]), multiple=False),
            dbc.Input(id="raw-parser", placeholder="parser_version", value="v1", className="mt-2"),
            dbc.Input(id="raw-acq-id", placeholder="acquisition_id", type="number", className="mt-2"),
            dbc.Button("Guardar raw", id="raw-submit", color="primary", className="mt-2"),
            html.Div(id="raw-status", className="mt-2"),
            html.H5("Paso 3-4: mapeo y normalizado"),
            html.P("Completa tirante, sensor y altura por columna. El sistema precarga encabezados del CSV."),
            dash_table.DataTable(
                id="map-table",
                columns=[
                    {"name": "csv_column_name", "id": "csv_column_name", "editable": False},
                    {"name": "sensor_id", "id": "sensor_id", "editable": True},
                    {"name": "cable_id", "id": "cable_id", "editable": True},
                    {"name": "height_m", "id": "height_m", "editable": True},
                ],
                data=[],
                editable=True,
            ),
            dbc.Input(id="norm-parser", placeholder="parser_version", value="v1", className="mt-2"),
            dbc.Input(id="norm-acq-id", placeholder="acquisition_id", type="number", className="mt-2"),
            dbc.Button("Generar normalizado", id="norm-submit", color="success", className="mt-2"),
            html.Div(id="norm-status", className="mt-2"),
        ],
        fluid=True,
    )


def pesaje_page():
    return dbc.Container(
        [
            html.H3("Pesaje directo"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="w-bridge", placeholder="bridge_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="w-date", placeholder="YYYY-MM-DD HH:MM", type="text"), md=3),
                    dbc.Col(dbc.Input(id="w-by", placeholder="Responsable", type="text"), md=3),
                    dbc.Col(dbc.Input(id="w-method", placeholder="Método", type="text"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="w-equip", placeholder="Equipo", type="text"), md=4),
                    dbc.Col(dbc.Input(id="w-temp", placeholder="Temp C (opcional)", type="number"), md=4),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="w-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear pesaje", id="w-submit", color="primary"),
            html.Div(id="w-status", className="mt-2"),
            html.Hr(),
            html.H5("Paso 2: medición por tirante"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="wm-campaign", placeholder="weighing_campaign_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="wm-cable", placeholder="cable_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="wm-tension", placeholder="measured_tension_tf", type="number"), md=3),
                    dbc.Col(dbc.Input(id="wm-temp", placeholder="Temp C (opcional)", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="wm-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Guardar medición", id="wm-submit", color="primary"),
            html.Div(id="wm-status", className="mt-2"),
            html.Hr(),
            html.H5("Paso 3: snapshot para K"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="snap-cable", placeholder="cable_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="snap-state", placeholder="source_state_version_id (opcional)", type="number"), md=3),
                    dbc.Col(dbc.Input(id="snap-L", placeholder="effective_length_m", type="number"), md=3),
                    dbc.Col(dbc.Input(id="snap-mu", placeholder="mu_value_kg_m", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="snap-mu-basis", placeholder="mu_basis (active/total/custom)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="snap-sa", placeholder="strands_active", type="number"), md=3),
                    dbc.Col(dbc.Input(id="snap-st", placeholder="strands_total", type="number"), md=3),
                    dbc.Col(dbc.Input(id="snap-strand-type", placeholder="strand_type_id (opcional)", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="snap-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear snapshot", id="snap-submit", color="primary"),
            html.Div(id="snap-status", className="mt-2"),
            html.Hr(),
            html.H5("Paso 4: calibración K"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="kc-cable", placeholder="cable_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="kc-meas", placeholder="derived_from_weighing_measurement_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="kc-snap", placeholder="config_snapshot_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="kc-value", placeholder="k_value", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="kc-from", placeholder="valid_from (YYYY-MM-DD HH:MM)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="kc-to", placeholder="valid_to (opcional)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="kc-algo", placeholder="algorithm_version", value="v1.0", type="text"), md=3),
                    dbc.Col(dbc.Input(id="kc-user", placeholder="computed_by_user_id (opcional)", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="kc-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear K", id="kc-submit", color="success"),
            html.Div(id="kc-status", className="mt-2"),
        ],
        fluid=True,
    )


def analisis_page():
    return dbc.Container(
        [
            html.H3("Análisis"),
            html.H5("Nueva sesión"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="an-acq", placeholder="acquisition_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="an-user", placeholder="created_by_user_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="an-algo", placeholder="algorithm_version", type="text", value="v1.0"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Textarea(id="an-notes", placeholder="Notas", className="mb-2"),
            dbc.Button("Crear run", id="an-submit", color="primary"),
            html.Div(id="an-status", className="mt-2"),
            html.Hr(),
            html.H5("Resultado de tirante (K se selecciona automáticamente por fecha de acquisition)"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="res-run", placeholder="analysis_run_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="res-cable", placeholder="cable_id", type="number"), md=3),
                    dbc.Col(dbc.Input(id="res-f0", placeholder="f0_hz", type="number"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="res-df", placeholder="df_hz (opcional)", type="number"), md=4),
                    dbc.Col(dbc.Input(id="res-snr", placeholder="snr_metric (opcional)", type="number"), md=4),
                    dbc.Col(dbc.Input(id="res-qual", placeholder="quality_flag (ok/doubtful/bad)", type="text", value="ok"), md=4),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Button("Guardar resultado", id="res-submit", color="success"),
            html.Div(id="res-status", className="mt-2"),
            html.Hr(),
            html.H5("Resultados del run"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="res-run-query", placeholder="analysis_run_id", type="number"), md=4),
                    dbc.Col(dbc.Button("Consultar resultados", id="res-query-btn", color="secondary"), md=2),
                ],
                className="gy-2 mb-2",
            ),
            html.Div(id="res-table"),
        ],
        fluid=True,
    )


def semaforo_page():
    return dbc.Container(
        [
            html.H3("Semáforo"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="sem-bridge", placeholder="bridge_id", type="number"), md=4),
                    dbc.Col(dbc.Input(id="sem-acq", placeholder="acquisition_id", type="number"), md=4),
                    dbc.Col(dbc.Input(id="sem-topn", placeholder="top_n (opcional)", type="number"), md=3),
                    dbc.Col(dbc.Button("Consultar", id="sem-submit", color="primary"), md=2),
                ],
                className="gy-2 mb-3",
            ),
            html.Div(id="sem-status"),
            html.Div(id="sem-table"),
        ],
        fluid=True,
    )


def historico_page():
    return dbc.Container(
        [
            html.H3("Histórico"),
            dbc.Row(
                [
                    dbc.Col(dbc.Input(id="hist-bridge", placeholder="bridge_id (opcional)", type="number"), md=3),
                    dbc.Col(dbc.Input(id="hist-cable", placeholder="cable_id (opcional)", type="number"), md=3),
                    dbc.Col(dbc.Input(id="hist-from", placeholder="date_from YYYY-MM-DD (opcional)", type="text"), md=3),
                    dbc.Col(dbc.Input(id="hist-to", placeholder="date_to YYYY-MM-DD (opcional)", type="text"), md=3),
                ],
                className="gy-2 mb-2",
            ),
            dbc.Button("Consultar histórico", id="hist-submit", color="primary"),
            html.Div(id="hist-status", className="mt-2"),
            dcc.Graph(id="hist-graph-tension"),
            dcc.Graph(id="hist-graph-f0"),
            html.Div(id="hist-table"),
        ],
        fluid=True,
    )


content = html.Div(id="page-content", className="p-4")

app.layout = dbc.Container(
    [
        dcc.Location(id="url"),
        dcc.Store(id="token-store"),
        dcc.Store(id="user-info"),
        dcc.Store(id="selected-bridge-store"),
        dcc.Store(id="cables-store"),
        dcc.Store(id="cables-edit-store"),
        dbc.Row(
            [
                dbc.Col(sidebar, width=2, style={"borderRight": "1px solid #eaeaea", "minHeight": "100vh"}),
                dbc.Col(content, width=10),
            ],
            className="g-0",
        ),
    ],
    fluid=True,
)


@app.callback(Output("page-content", "children"), Input("url", "pathname"))
def render_page(pathname: str):
    pages = {
        "/": home_page(),
        "/catalogo": catalogo_page(),
        "/adquisiciones": acquisition_page(),
        "/pesajes": pesaje_page(),
        "/analisis": analisis_page(),
        "/historico": historico_page(),
        "/semaforo": semaforo_page(),
        "/admin": html.Div([html.H3("Admin"), html.P("Gestión de usuarios via /users y /auth/login")]),
    }
    return pages.get(pathname, home_page())


@app.callback(
    Output("token-store", "data"),
    Output("user-info", "data"),
    Output("token-status", "children"),
    Input("login-submit", "n_clicks"),
    State("login-user", "value"),
    State("login-pass", "value"),
    prevent_initial_call=True,
)
def do_login(_, username, password):
    if not username or not password:
        return None, None, "Usuario o contraseña vacíos"
    try:
        resp = call_api(
            "POST",
            "/auth/token",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if isinstance(resp, dict) and resp.get("access_token"):
            return resp["access_token"], resp.get("user"), f"Login ok como {resp.get('user', {}).get('username')}"
        return None, None, str(resp)
    except Exception as e:
        return None, None, f"Error login: {e}"


@app.callback(
    Output("stv-status", "children"),
    Input("stv-submit", "n_clicks"),
    State("stv-cable", "value"),
    State("stv-from", "value"),
    State("stv-to", "value"),
    State("stv-strand-type", "value"),
    State("stv-length", "value"),
    State("stv-strands-total", "value"),
    State("stv-strands-active", "value"),
    State("stv-fu-ovr", "value"),
    State("stv-mu-total", "value"),
    State("stv-mu-active", "value"),
    State("stv-E", "value"),
    State("stv-area", "value"),
    State("stv-diam", "value"),
    State("stv-design", "value"),
    State("stv-anti", "value"),
    State("stv-notes", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def submit_state(_, cable_id, v_from, v_to, strand_type_id, length, stotal, sactive, fu_ovr, mu_total, mu_active, e, area, diam, design, anti, notes, token):
    payload = {
        "cable_id": cable_id,
        "valid_from": datetime.fromisoformat(v_from) if v_from else None,
        "valid_to": datetime.fromisoformat(v_to) if v_to else None,
        "length_effective_m": length,
        "length_total_m": length,
        "strands_total": stotal,
        "strands_active": sactive,
        "strands_inactive": max(0, (stotal or 0) - (sactive or 0)),
        "strand_type_id": strand_type_id,
        "diametro_mm": diam,
        "area_mm2": area,
        "E_MPa": e,
        "mu_total_kg_m": mu_total,
        "mu_active_basis_kg_m": mu_active,
        "design_tension_tf": design,
        "Fu_override": fu_ovr,
        "antivandalic_enabled": bool(anti),
        "antivandalic_length_m": anti,
        "source": notes,
        "notes": notes,
    }
    res = call_api("POST", "/cable-states", json=payload, token=token)
    return str(res)


@app.callback(
    Output("br-status", "children"),
    Input("br-submit", "n_clicks"),
    State("br-nombre", "value"),
    State("br-clave", "value"),
    State("br-num", "value"),
    State("br-notas", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def submit_bridge(_, nombre, clave, num, notas, token):
    payload = {"nombre": nombre, "clave_interna": clave, "num_tirantes": num, "notas": notas}
    res = call_api("POST", "/bridges", json=payload, token=token)
    return str(res)


@app.callback(
    Output("st-status", "children"),
    Input("st-submit", "n_clicks"),
    State("st-nombre", "value"),
    State("st-diam", "value"),
    State("st-area", "value"),
    State("st-e", "value"),
    State("st-fu", "value"),
    State("st-mu", "value"),
    State("st-notas", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def submit_strand(_, nombre, diam, area, e, fu, mu, notas, token):
    payload = {
        "nombre": nombre,
        "diametro_mm": diam,
        "area_mm2": area,
        "E_MPa": e,
        "Fu_default": fu,
        "mu_por_toron_kg_m": mu,
        "notas": notas,
    }
    res = call_api("POST", "/strand-types", json=payload, token=token)
    return str(res)


@app.callback(
    Output("cb-status", "children"),
    Input("cb-submit", "n_clicks"),
    State("cb-bridge", "value"),
    State("cb-nombre", "value"),
    State("cb-notas", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def submit_cable(_, bridge_id, nombre, notas, token):
    payload = {"bridge_id": bridge_id, "nombre_en_puente": nombre, "notas": notas}
    res = call_api("POST", "/cables", json=payload, token=token)
    return str(res)


@app.callback(
    Output("cb-edit-status", "children"),
    Input("cb-edit-submit", "n_clicks"),
    State("cb-id-edit", "value"),
    State("cb-nombre-edit", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def rename_cable(_, cable_id, new_name, token):
    if not cable_id or not new_name:
        return "Falta cable_id o nuevo nombre"
    res = call_api("PUT", f"/cables/{cable_id}", json={"nombre_en_puente": new_name}, token=token)
    return str(res)


@app.callback(
    Output("bridges-table", "data", allow_duplicate=True),
    Output("cables-store", "data"),
    Output("catalogo-status", "children"),
    Output("catalogo-tables", "children"),
    Input("refresh-catalogo", "n_clicks"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def refresh_catalogo(_, token):
    bridges = call_api("GET", "/bridges", token=token)
    cables = call_api("GET", "/cables", token=token)
    strands = call_api("GET", "/strand-types", token=token)
    status = ""
    if isinstance(bridges, dict) and bridges.get("error"):
        status = f"Error puentes: {bridges}"
    elif isinstance(cables, dict) and cables.get("error"):
        status = f"Error tirantes: {cables}"
    else:
        status = "Catálogo cargado."
    strands_table = dash_table.DataTable(data=strands, page_size=5) if isinstance(strands, list) else html.Div("")
    return (
        bridges if isinstance(bridges, list) else [],
        cables if isinstance(cables, list) else [],
        status,
        html.Div([html.H6("Tipos de torón"), strands_table]),
    )


@app.callback(
    Output("bridges-table", "data", allow_duplicate=True),
    Output("br-edit-status", "children", allow_duplicate=True),
    Input("bridge-add-row", "n_clicks"),
    State("bridges-table", "data"),
    prevent_initial_call=True,
)
def add_bridge_row(_, current_rows):
    rows = current_rows or []
    rows.append({"id": None, "nombre": "", "clave_interna": "", "num_tirantes": None, "notas": ""})
    return rows, "Fila nueva agregada (edita y presiona Guardar cambios de puentes)"


@app.callback(
    Output("selected-bridge-store", "data"),
    Output("cables-table", "data"),
    Input("bridges-table", "selected_rows"),
    State("bridges-table", "data"),
    State("cables-store", "data"),
    prevent_initial_call=True,
)
def select_bridge(selected_rows, bridges_data, cables_data):
    if not selected_rows or not bridges_data:
        return None, []
    row = bridges_data[selected_rows[0]]
    bridge_id = row.get("id")
    cables = [c for c in (cables_data or []) if c.get("bridge_id") == bridge_id]
    return bridge_id, cables


@app.callback(
    Output("cables-edit-table", "data"),
    Input("selected-bridge-store", "data"),
    State("cables-store", "data"),
)
def load_cables_for_edit(bridge_id, cables_data):
    if not bridge_id:
        return []
    return [c for c in (cables_data or []) if c.get("bridge_id") == bridge_id]


@app.callback(
    Output("cables-edit-status", "children"),
    Input("cables-edit-save", "n_clicks"),
    State("cables-edit-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def save_cable_edits(_, rows, token):
    if not rows:
        return "No hay tirantes para guardar."
    messages = []
    for r in rows:
        cid = r.get("id")
        if not cid:
            continue
        payload = {
            "nombre_en_puente": r.get("nombre_en_puente"),
            "notas": r.get("notas"),
        }
        res = call_api("PUT", f"/cables/{cid}", json=payload, token=token)
        if isinstance(res, dict) and res.get("error"):
            messages.append(f"Error cable {cid}: {res}")
    return "Cambios guardados" if not messages else "; ".join(messages)


@app.callback(
    Output("bridges-table", "data"),
    Output("br-edit-status", "children"),
    Input("bridges-save", "n_clicks"),
    State("bridges-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def save_bridges(_, rows, token):
    if not rows:
        return [], "No hay puentes para guardar."
    updated = []
    messages = []
    for r in rows:
        bid = r.get("id")
        payload = {
            "nombre": r.get("nombre"),
            "clave_interna": r.get("clave_interna"),
            "num_tirantes": r.get("num_tirantes"),
            "notas": r.get("notas"),
        }
        if not bid:
            res = call_api("POST", "/bridges", json=payload, token=token)
        else:
            res = call_api("PUT", f"/bridges/{bid}", json=payload, token=token)
        if isinstance(res, dict) and res.get("id"):
            updated.append(res)
        else:
            messages.append(f"Error puente {bid or 'nuevo'}: {res}")
    # Refrescar desde API para evitar IDs locales/duplicados
    refreshed = call_api("GET", "/bridges", token=token)
    table_data = refreshed if isinstance(refreshed, list) else rows
    return table_data, "Guardado" if not messages else "; ".join(messages)

@app.callback(
    Output("acq-status", "children"),
    Input("acq-submit", "n_clicks"),
    State("acq-bridge", "value"),
    State("acq-date", "value"),
    State("acq-operator", "value"),
    State("acq-fs", "value"),
    State("acq-notes", "value"),
    prevent_initial_call=True,
)
def submit_acquisition(_, bridge_id, date_str, operator_id, fs, notes):
    payload = {
        "bridge_id": bridge_id,
        "acquired_at": datetime.fromisoformat(date_str) if date_str else None,
        "operator_user_id": operator_id,
        "Fs_Hz": fs,
        "notes": notes,
    }
    token = dash.callback_context.states.get("token-store.data") if dash.callback_context else None
    res = call_api("POST", "/acquisitions", json=payload, token=token)
    return str(res)


@app.callback(
    Output("raw-status", "children"),
    Output("raw-headers-store", "data"),
    Input("raw-submit", "n_clicks"),
    State("raw-upload", "contents"),
    State("raw-upload", "filename"),
    State("raw-parser", "value"),
    State("raw-acq-id", "value"),
    prevent_initial_call=True,
)
def submit_raw(_, contents, filename, parser_version, acq_id):
    if not contents:
        return "Sube un archivo", None
    header, b64data = contents.split(",", 1)
    data = base64.b64decode(b64data)
    files = {"file": (filename, data, "text/csv")}
    token = dash.callback_context.states.get("token-store.data") if dash.callback_context else None
    res = call_api("POST", f"/acquisitions/{acq_id}/raw-upload", files=files, params={"parser_version": parser_version}, token=token)
    headers = []
    try:
        txt = data.decode("utf-8").splitlines()
        idx = next(i for i, line in enumerate(txt) if "DATA_START" in line) + 1
        headers = [h.strip() for h in txt[idx].split(",") if h.strip()]
    except Exception as e:
        pass
    return str(res), headers


@app.callback(
    Output("map-table", "data"),
    Input("raw-headers-store", "data"),
    prevent_initial_call=True,
)
def populate_map_table(headers):
    if not headers:
        return []
    return [{"csv_column_name": h, "sensor_id": None, "cable_id": None, "height_m": None} for h in headers if h]


@app.callback(
    Output("norm-status", "children"),
    Input("norm-submit", "n_clicks"),
    State("map-table", "data"),
    State("norm-parser", "value"),
    State("norm-acq-id", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def submit_norm(_, map_rows, parser_version, acq_id, token):
    mapping = map_rows or []
    res = call_api(
        "POST",
        f"/acquisitions/{acq_id}/normalize",
        params={"parser_version": parser_version},
        json=mapping,
        token=token,
    )
    return str(res)


@app.callback(
    Output("w-status", "children"),
    Input("w-submit", "n_clicks"),
    State("w-bridge", "value"),
    State("w-date", "value"),
    State("w-by", "value"),
    State("w-method", "value"),
    State("w-equip", "value"),
    State("w-temp", "value"),
    State("w-notes", "value"),
    prevent_initial_call=True,
)
def submit_weighing(_, bridge_id, date_str, by, method, equip, temp, notes):
    payload = {
        "bridge_id": bridge_id,
        "performed_at": datetime.fromisoformat(date_str) if date_str else None,
        "performed_by": by,
        "method": method,
        "equipment": equip,
        "temperature_C": temp,
        "notes": notes,
    }
    res = call_api("POST", "/weighing-campaigns", json=payload)
    return str(res)


@app.callback(
    Output("wm-status", "children"),
    Input("wm-submit", "n_clicks"),
    State("wm-campaign", "value"),
    State("wm-cable", "value"),
    State("wm-tension", "value"),
    State("wm-temp", "value"),
    State("wm-notes", "value"),
    prevent_initial_call=True,
)
def submit_weighing_measurement(_, campaign_id, cable_id, tension, temp, notes):
    payload = {
        "weighing_campaign_id": campaign_id,
        "cable_id": cable_id,
        "measured_tension_tf": tension,
        "measured_temperature_C": temp,
        "notes": notes,
    }
    res = call_api("POST", "/weighing-measurements", json=payload)
    return str(res)


@app.callback(
    Output("snap-status", "children"),
    Input("snap-submit", "n_clicks"),
    State("snap-cable", "value"),
    State("snap-state", "value"),
    State("snap-L", "value"),
    State("snap-mu", "value"),
    State("snap-mu-basis", "value"),
    State("snap-sa", "value"),
    State("snap-st", "value"),
    State("snap-strand-type", "value"),
    State("snap-notes", "value"),
    prevent_initial_call=True,
)
def submit_snapshot(_, cable_id, state_id, L, mu, mu_basis, sa, st, strand_type_id, notes):
    payload = {
        "cable_id": cable_id,
        "source_state_version_id": state_id,
        "effective_length_m": L,
        "mu_basis": mu_basis,
        "mu_value_kg_m": mu,
        "strands_active": sa,
        "strands_total": st,
        "strand_type_id": strand_type_id,
        "notes": notes,
    }
    res = call_api("POST", "/cable-config-snapshots", json=payload)
    return str(res)


@app.callback(
    Output("kc-status", "children"),
    Input("kc-submit", "n_clicks"),
    State("kc-cable", "value"),
    State("kc-meas", "value"),
    State("kc-snap", "value"),
    State("kc-value", "value"),
    State("kc-from", "value"),
    State("kc-to", "value"),
    State("kc-algo", "value"),
    State("kc-user", "value"),
    State("kc-notes", "value"),
    prevent_initial_call=True,
)
def submit_kc(_, cable_id, meas_id, snap_id, k_val, v_from, v_to, algo, user_id, notes):
    payload = {
        "cable_id": cable_id,
        "derived_from_weighing_measurement_id": meas_id,
        "config_snapshot_id": snap_id,
        "k_value": k_val,
        "valid_from": datetime.fromisoformat(v_from) if v_from else None,
        "valid_to": datetime.fromisoformat(v_to) if v_to else None,
        "algorithm_version": algo,
        "computed_by_user_id": user_id,
        "notes": notes,
    }
    res = call_api("POST", "/k-calibrations", json=payload)
    return str(res)


@app.callback(
    Output("an-status", "children"),
    Input("an-submit", "n_clicks"),
    State("an-acq", "value"),
    State("an-user", "value"),
    State("an-algo", "value"),
    State("an-notes", "value"),
    prevent_initial_call=True,
)
def submit_analysis_run(_, acq_id, user_id, algo, notes):
    payload = {
        "acquisition_id": acq_id,
        "created_by_user_id": user_id,
        "algorithm_version": algo,
        "notes": notes,
    }
    res = call_api("POST", "/analysis-runs", json=payload)
    return str(res)


@app.callback(
    Output("res-status", "children"),
    Input("res-submit", "n_clicks"),
    State("res-run", "value"),
    State("res-cable", "value"),
    State("res-f0", "value"),
    State("res-df", "value"),
    State("res-snr", "value"),
    State("res-qual", "value"),
    prevent_initial_call=True,
)
def submit_analysis_result(_, run_id, cable_id, f0, df_hz, snr, quality):
    payload = {
        "analysis_run_id": run_id,
        "cable_id": cable_id,
        "f0_hz": f0,
        "harmonics_json": {},
        "df_hz": df_hz,
        "snr_metric": snr,
        "quality_flag": quality,
    }
    res = call_api("POST", "/analysis-results", json=payload)
    return str(res)


@app.callback(
    Output("res-table", "children"),
    Input("res-query-btn", "n_clicks"),
    State("res-run-query", "value"),
    prevent_initial_call=True,
)
def query_results(_, run_id):
    res = call_api("GET", f"/analysis-runs/{run_id}/results")
    if isinstance(res, list):
        return dash_table.DataTable(data=res, page_size=10)
    return str(res)


@app.callback(
    Output("hist-status", "children"),
    Output("hist-table", "children"),
    Output("hist-graph-tension", "figure"),
    Output("hist-graph-f0", "figure"),
    Input("hist-submit", "n_clicks"),
    State("hist-bridge", "value"),
    State("hist-cable", "value"),
    State("hist-from", "value"),
    State("hist-to", "value"),
    prevent_initial_call=True,
)
def load_history(_, bridge_id, cable_id, date_from, date_to):
    params = {}
    if bridge_id:
        params["bridge_id"] = bridge_id
    if cable_id:
        params["cable_id"] = cable_id
    if date_from:
        params["date_from"] = date_from
    if date_to:
        params["date_to"] = date_to
    res = call_api("GET", "/history", params=params)
    if isinstance(res, dict) and res.get("error"):
        return str(res), None, {}, {}
    results = res.get("results", []) if isinstance(res, dict) else []
    if not results:
        return "Sin datos", None, {}, {}
    df = results
    fig_t = px.line(df, x="acquired_at", y="tension_tf", color="nombre_en_puente", markers=True, title="Tensión vs fecha")
    fig_f = px.line(df, x="acquired_at", y="f0_hz", color="nombre_en_puente", markers=True, title="f0 vs fecha")
    table = dash_table.DataTable(data=df, page_size=10)
    return "", table, fig_t, fig_f


@app.callback(
    Output("sem-status", "children"),
    Output("sem-table", "children"),
    Input("sem-submit", "n_clicks"),
    State("sem-bridge", "value"),
    State("sem-acq", "value"),
    State("sem-topn", "value"),
    prevent_initial_call=True,
)
def consult_semaforo(_, bridge_id, acq_id, topn):
    params = {"acquisition_id": acq_id}
    if topn:
        params["top_n"] = topn
    res = call_api("GET", f"/bridges/{bridge_id}/semaforo", params=params)
    if isinstance(res, dict) and res.get("error"):
        return str(res), None
    items = res.get("items", []) if isinstance(res, dict) else []
    table = dash_table.DataTable(data=items, page_size=10) if items else html.Div("Sin resultados")
    resumen = f"Total: {res.get('total', 0)} | Exceden 45% Fu: {res.get('exceden', 0)}"
    return resumen, table


if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)
