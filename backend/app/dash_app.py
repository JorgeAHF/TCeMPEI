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


sidebar = html.Div(
    dbc.Nav(
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
    ),
    id="sidebar",
    style={"display": "none"},
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


def welcome_page():
    return dbc.Container(
        [
            html.H3("Bienvenido a TCeMPEI"),
            html.P("Usa el menú lateral para navegar el catálogo, adquisiciones, pesajes, análisis e histórico."),
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
                    {"name": ["", "ID"], "id": "id"},
                    {"name": ["", "Nombre"], "id": "nombre"},
                    {"name": ["", "Clave"], "id": "clave_interna"},
                    {"name": ["", "Num. tirantes"], "id": "num_tirantes"},
                    {"name": ["", "Notas"], "id": "notas"},
                    {"name": ["Acciones", "Ver"], "id": "ver"},
                    {"name": ["Acciones", "Editar"], "id": "editar"},
                    {"name": ["Acciones", "Eliminar"], "id": "eliminar"},
                ],
                row_selectable="single",
                hidden_columns=["id"],
                style_table={"maxHeight": "300px", "overflowY": "auto"},
                style_cell={"textAlign": "center"},
                style_data_conditional=[
                    {
                        "if": {"column_id": c},
                        "backgroundColor": "#f8f9fa",
                        "color": "#0d6efd",
                        "cursor": "pointer",
                        "fontWeight": "600",
                    }
                    for c in ["ver", "editar", "eliminar"]
                ],
                merge_duplicate_headers=True,
            ),
            dbc.Button("Seleccionar puente", id="bridge-select", color="info", className="mb-3 ms-2", outline=True, size="sm"),
            dbc.Button("Nuevo puente", id="bridge-add-row", color="secondary", className="mb-3 ms-2", outline=True, size="sm"),
            html.Div(id="br-edit-status", className="mb-3"),
            html.Div(id="br-select-status", className="mb-2"),
            html.Hr(),
            html.P("Una vez creado el puente, define tirantes y sus estados."),
            html.H5("Paso 2: Tirantes y estados (resumen)"),
            dash_table.DataTable(
                id="cables-states-table",
                columns=[
                    {"name": ["", "ID"], "id": "id"},
                    {"name": ["", "Tirante"], "id": "nombre_en_puente"},
                    {"name": ["", "Fecha de actualización"], "id": "valid_from"},
                    {"name": ["", "Caducidad"], "id": "valid_to"},
                    {"name": ["Acciones", "Ver"], "id": "ver"},
                    {"name": ["Acciones", "Editar"], "id": "editar"},
                    {"name": ["Acciones", "Eliminar"], "id": "eliminar"},
                ],
                data=[],
                hidden_columns=["id"],
                style_table={"maxHeight": "300px", "overflowY": "auto"},
                style_cell={"textAlign": "center"},
                style_data_conditional=[
                    {
                        "if": {"column_id": c},
                        "backgroundColor": "#f8f9fa",
                        "color": "#0d6efd",
                        "textAlign": "center",
                        "cursor": "pointer",
                        "fontWeight": "600",
                    }
                    for c in ["ver", "editar", "eliminar"]
                ],
                merge_duplicate_headers=True,
            ),
            html.Div(id="cable-delete-status", className="mb-2"),
            html.Hr(),
            html.Div(id="catalogo-tables"),
            html.Div(id="strand-action-status", className="mt-2"),
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
modal_cable = dbc.Modal(
    [
        dbc.ModalHeader("Propiedades del Tirante"),
        dbc.ModalBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("ID tirante"), md=3),
                        dbc.Col(dbc.Label("Versión (auto)"), md=3),
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(dbc.Input(id="modal-cable-id", placeholder="ID", disabled=True), md=3),
                        dbc.Col(dbc.Input(id="modal-version", placeholder="versión", disabled=True), md=3),
                    ]
                ),
                dbc.Label("Nombre en puente", className="mt-2"),
                dbc.Input(id="modal-cable-name", placeholder="Nombre en puente", className="mb-2"),
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Vigente desde (YYYY-MM-DD HH:MM)"), md=6),
                        dbc.Col(dbc.Label("Vigente hasta (opcional)"), md=6),
                    ],
                className="mt-2",
                ),
                dbc.Row(
                    [
                        dbc.Col(dbc.Input(id="modal-valid-from", type="datetime-local", placeholder="YYYY-MM-DDTHH:MM"), md=6),
                        dbc.Col(dbc.Input(id="modal-valid-to", type="datetime-local", placeholder="YYYY-MM-DDTHH:MM"), md=6),
                    ],
                    className="mt-2",
                ),
                dbc.Label("Longitud efectiva (m)", className="mt-2"),
                dbc.Input(id="modal-length", placeholder="Longitud efectiva (m)", type="number", className="mb-2"),
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("Tipo de torón"), md=4),
                        dbc.Col(
                            dcc.Dropdown(
                                id="modal-strand-type",
                                placeholder="Selecciona tipo de torón",
                                options=[],
                                clearable=False,
                            ),
                            md=4,
                        ),
                        dbc.Col(dbc.Button("Editar torón", id="strand-edit", color="secondary", size="sm"), md=2),
                        dbc.Col(dbc.Button("Nuevo torón", id="strand-new", color="secondary", outline=True, size="sm"), md=2),
                    ],
                    className="mt-2",
                ),
                dbc.Label("Torones totales", className="mt-2"),
                dbc.Input(id="modal-strands-total", placeholder="Torones totales", type="number", className="mb-2"),
                dbc.Label("Torones activos", className="mt-2"),
                dbc.Input(id="modal-strands-active", placeholder="Torones activos", type="number", className="mb-2"),
                dbc.Label("Masa total (kg/m)", className="mt-2"),
                dbc.Input(id="modal-mu-total", placeholder="Masa total (kg/m)", type="number", className="mb-2"),
                dbc.Label("Masa torones activos (kg/m)", className="mt-2"),
                dbc.Input(id="modal-mu-active", placeholder="Masa activos (kg/m)", type="number", className="mb-2"),
                dbc.Label("Módulo E (MPa)", className="mt-2"),
                dbc.Input(id="modal-E", placeholder="E (MPa)", type="number", className="mb-2"),
                dbc.Label("Área (mm²)", className="mt-2"),
                dbc.Input(id="modal-area", placeholder="Área (mm²)", type="number", className="mb-2"),
                dbc.Label("Diámetro (mm)", className="mt-2"),
                dbc.Input(id="modal-diam", placeholder="Diámetro (mm)", type="number", className="mb-2"),
                dbc.Label("Fu override (opcional)", className="mt-2"),
                dbc.Input(id="modal-Fu", placeholder="Fu override", type="number", className="mb-2"),
                dbc.Label("Tensión de diseño (tf)", className="mt-2"),
                dbc.Input(id="modal-design", placeholder="Tensión de diseño (tf)", type="number", className="mb-2"),
                dbc.Label("Longitud antivandálico (m, opcional)", className="mt-2"),
                dbc.Input(id="modal-anti", placeholder="Longitud antivandálico (m)", type="number", className="mb-2"),
                dbc.Label("Notas / fuente", className="mt-2"),
                dbc.Textarea(id="modal-notes", placeholder="Notas / fuente", className="mb-2"),
                html.Div(id="cable-modal-status", className="mt-2"),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button("Guardar", id="cable-modal-save", color="primary", className="me-2"),
                dbc.Button("Cerrar", id="cable-modal-close", color="secondary"),
            ]
        ),
    ],
    id="cable-modal",
    is_open=False,
    size="lg",
    style={"maxWidth": "80vw"},
)

modal_bridge = dbc.Modal(
    [
        dbc.ModalHeader("Puente"),
        dbc.ModalBody(
            [
                dbc.Input(id="bridge-id", type="number", placeholder="ID (auto)", disabled=True, className="mb-2"),
                dbc.Label("Nombre"),
                dbc.Input(id="bridge-nombre", placeholder="Nombre", className="mb-2"),
                dbc.Label("Clave interna"),
                dbc.Input(id="bridge-clave", placeholder="Clave interna", className="mb-2"),
                dbc.Label("Número de tirantes"),
                dbc.Input(id="bridge-num", type="number", placeholder="Num. tirantes", className="mb-2"),
                dbc.Label("Notas"),
                dbc.Textarea(id="bridge-notas", placeholder="Notas", className="mb-2"),
                html.Div(id="bridge-modal-status", className="mt-2"),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button("Guardar", id="bridge-modal-save", color="primary", className="me-2"),
                dbc.Button("Cerrar", id="bridge-modal-close", color="secondary"),
            ]
        ),
    ],
    id="bridge-modal",
    is_open=False,
    size="lg",
    style={"maxWidth": "80vw"},
)

modal_strand = dbc.Modal(
    [
        dbc.ModalHeader("Propiedades del Torón"),
        dbc.ModalBody(
            [
                dbc.Row(
                    [
                        dbc.Col(dbc.Label("ID torón"), md=4),
                        dbc.Col(dbc.Label("Vigente desde (opcional)"), md=4),
                        dbc.Col(dbc.Label("Vigente hasta (opcional)"), md=4),
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col(dbc.Input(id="strand-id", placeholder="ID", disabled=True), md=4),
                        dbc.Col(dbc.Input(id="strand-valid-from", type="datetime-local", placeholder="YYYY-MM-DDTHH:MM"), md=4),
                        dbc.Col(dbc.Input(id="strand-valid-to", type="datetime-local", placeholder="YYYY-MM-DDTHH:MM"), md=4),
                    ]
                ),
                dbc.Label("Nombre", className="mt-2"),
                dbc.Input(id="strand-nombre", placeholder="Nombre", className="mb-2"),
                dbc.Label("Masa por torón (kg/m)", className="mt-2"),
                dbc.Input(id="strand-mu", placeholder="kg/m", type="number", className="mb-2"),
                dbc.Label("Módulo E (MPa)", className="mt-2"),
                dbc.Input(id="strand-E", placeholder="E (MPa)", type="number", className="mb-2"),
                dbc.Label("Área (mm²)", className="mt-2"),
                dbc.Input(id="strand-area", placeholder="Área (mm²)", type="number", className="mb-2"),
                dbc.Label("Diámetro (mm)", className="mt-2"),
                dbc.Input(id="strand-diam", placeholder="Diámetro (mm)", type="number", className="mb-2"),
                dbc.Label("Fu (default)", className="mt-2"),
                dbc.Input(id="strand-Fu", placeholder="Fu default", type="number", className="mb-2"),
                dbc.Label("Notas", className="mt-2"),
                dbc.Textarea(id="strand-notas", placeholder="Notas", className="mb-2"),
                html.Div(id="strand-status", className="mt-2"),
            ]
        ),
        dbc.ModalFooter(
            [
                dbc.Button("Guardar torón", id="strand-save", color="primary", className="me-2"),
                dbc.Button("Cerrar", id="strand-close", color="secondary"),
            ]
        ),
    ],
    id="strand-modal",
    is_open=False,
)
app.layout = dbc.Container(
    [
        dcc.Location(id="url"),
        dcc.Store(id="token-store"),
        dcc.Store(id="user-info"),
        dcc.Store(id="selected-bridge-store"),
        dcc.Store(id="selected-bridge-name"),
        dcc.Store(id="cables-store"),
        dbc.Row(
            [
                dbc.Col(sidebar, width=2, style={"borderRight": "1px solid #eaeaea", "minHeight": "100vh"}),
                dbc.Col(
                    [
                        html.Div(id="header-info", className="p-2"),
                        content,
                        modal_cable,
                        modal_strand,
                        modal_bridge,
                    ],
                    width=10,
                ),
            ],
            className="g-0",
        ),
    ],
    fluid=True,
)


@app.callback(
    Output("page-content", "children"),
    Output("sidebar", "style"),
    Input("url", "pathname"),
    Input("token-store", "data"),
)
def render_page(pathname: str, token):
    if not token:
        return home_page(), {"display": "none"}
    pages = {
        "/": welcome_page(),
        "/catalogo": catalogo_page(),
        "/adquisiciones": acquisition_page(),
        "/pesajes": pesaje_page(),
        "/analisis": analisis_page(),
        "/historico": historico_page(),
        "/semaforo": semaforo_page(),
        "/admin": html.Div([html.H3("Admin"), html.P("Gestión de usuarios via /users y /auth/login")]),
    }
    return pages.get(pathname, welcome_page()), {"borderRight": "1px solid #eaeaea", "minHeight": "100vh"}


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
    Output("header-info", "children"),
    Input("user-info", "data"),
    Input("selected-bridge-name", "data"),
)
def update_header(user, bridge_name):
    username = user.get("username") if isinstance(user, dict) else None
    return dbc.Alert(
        f"Usuario: {username or 'No autenticado'} | Puente: {bridge_name or 'No seleccionado'}",
        color="light",
        className="mb-3",
    )


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
    strands_table = (
        dash_table.DataTable(
            id="strand-table",
            columns=[
                {"name": ["", "ID"], "id": "id"},
                {"name": ["", "Nombre"], "id": "nombre"},
                {"name": ["", "Área (mm²)"], "id": "area_mm2"},
                {"name": ["Acciones", "Ver"], "id": "ver"},
                {"name": ["Acciones", "Editar"], "id": "editar"},
                {"name": ["Acciones", "Eliminar"], "id": "eliminar"},
            ],
            data=[
                {
                    "id": s.get("id"),
                    "nombre": s.get("nombre"),
                    "area_mm2": s.get("area_mm2"),
                    "ver": "🔍 Ver",
                    "editar": "✏️ Editar",
                    "eliminar": "🗑 Eliminar",
                }
                for s in strands
            ],
            hidden_columns=["id"],
            style_table={"maxHeight": "300px", "overflowY": "auto"},
            style_cell={"textAlign": "center"},
            style_data_conditional=[
                {
                    "if": {"column_id": c},
                    "backgroundColor": "#f8f9fa",
                    "color": "#0d6efd",
                    "cursor": "pointer",
                    "fontWeight": "600",
                }
                for c in ["ver", "editar", "eliminar"]
            ],
            merge_duplicate_headers=True,
        )
        if isinstance(strands, list)
        else html.Div("")
    )
    return (
        [
            {
                **b,
                "ver": "🔍 Ver",
                "editar": "✏️ Editar",
                "eliminar": "🗑 Eliminar",
            }
            for b in bridges
        ]
        if isinstance(bridges, list)
        else [],
        cables if isinstance(cables, list) else [],
        status,
        html.Div([html.H6("Tipos de torón"), strands_table]),
    )


@app.callback(
    Output("bridge-modal", "is_open"),
    Output("bridge-modal-status", "children"),
    Output("bridge-id", "value"),
    Output("bridge-nombre", "value"),
    Output("bridge-clave", "value"),
    Output("bridge-num", "value"),
    Output("bridge-notas", "value"),
    Output("bridge-nombre", "disabled"),
    Input("bridge-add-row", "n_clicks"),
    Input("bridges-table", "active_cell"),
    Input("bridge-modal-close", "n_clicks"),
    State("bridges-table", "data"),
    prevent_initial_call=True,
)
def open_bridge_modal(n_new, active_cell, n_close, table_data):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]
    empty = (False, "", None, None, None, None, None, False)
    if trigger == "bridge-modal-close":
        return empty
    if trigger == "bridge-add-row":
        return True, "", None, "", "", None, "", False
    if trigger == "bridges-table":
        if not active_cell or not table_data:
            return False, "Selecciona un puente.", None, None, None, None, None, False
        col = active_cell.get("column_id")
        if col not in ("ver", "editar"):
            raise dash.exceptions.PreventUpdate
        row = table_data[active_cell.get("row")]
        disable_fields = col == "ver"
        return (
            True,
            "",
            row.get("id"),
            row.get("nombre"),
            row.get("clave_interna"),
            row.get("num_tirantes"),
            row.get("notas"),
            disable_fields,
        )
    raise dash.exceptions.PreventUpdate


@app.callback(
    Output("selected-bridge-store", "data"),
    Output("selected-bridge-name", "data"),
    Output("cables-states-table", "data", allow_duplicate=True),
    Input("bridges-table", "selected_rows"),
    State("bridges-table", "data"),
    State("cables-store", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def select_bridge(selected_rows, bridges_data, cables_data, token):
    if not selected_rows or not bridges_data:
        return None, None, []
    row = bridges_data[selected_rows[0]]
    bridge_id = row.get("id")
    bridge_name = row.get("nombre")
    cables = [c for c in (cables_data or []) if c.get("bridge_id") == bridge_id]
    summary = []
    for c in cables:
        valid_from = ""
        valid_to = ""
        states = call_api("GET", f"/cables/{c.get('id')}/states", token=token) if token else []
        if isinstance(states, list) and states:
            latest = states[0]
            valid_from = latest.get("valid_from") or ""
            valid_to = latest.get("valid_to") or ""
        summary.append(
            {
                "id": c.get("id"),
                "nombre_en_puente": c.get("nombre_en_puente"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "ver": "🔍 Ver",
                "editar": "✏️ Editar",
                "eliminar": "🗑 Eliminar",
            }
        )
    return bridge_id, bridge_name, summary


@app.callback(
    Output("selected-bridge-store", "data", allow_duplicate=True),
    Output("selected-bridge-name", "data", allow_duplicate=True),
    Output("br-select-status", "children"),
    Output("cables-states-table", "data", allow_duplicate=True),
    Input("bridge-select", "n_clicks"),
    State("bridges-table", "selected_rows"),
    State("bridges-table", "data"),
    State("cables-store", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def manual_select_bridge(_, selected_rows, bridges_data, cables_data, token):
    if not selected_rows or not bridges_data:
        return dash.no_update, dash.no_update, "Selecciona un puente en la tabla.", dash.no_update
    row = bridges_data[selected_rows[0]]
    if not row.get("id"):
        return dash.no_update, dash.no_update, "Selecciona un puente ya guardado (con ID).", dash.no_update
    bridge_id = row.get("id")
    bridge_name = row.get("nombre")
    cables = [c for c in (cables_data or []) if c.get("bridge_id") == bridge_id]
    summary = []
    for c in cables:
        valid_from = ""
        valid_to = ""
        states = call_api("GET", f"/cables/{c.get('id')}/states", token=token) if token else []
        if isinstance(states, list) and states:
            latest = states[0]
            valid_from = latest.get("valid_from") or ""
            valid_to = latest.get("valid_to") or ""
        summary.append(
            {
                "id": c.get("id"),
                "nombre_en_puente": c.get("nombre_en_puente"),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "ver": "🔍 Ver",
                "editar": "✏️ Editar",
                "eliminar": "🗑 Eliminar",
            }
        )
    return bridge_id, bridge_name, f"Puente seleccionado: {bridge_name}", summary


@app.callback(
    Output("cable-delete-status", "children"),
    Output("cables-states-table", "data", allow_duplicate=True),
    Input("cables-states-table", "active_cell"),
    State("cables-states-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def delete_cable(active_cell, table_data, token):
    if not active_cell or active_cell.get("column_id") != "eliminar":
        raise dash.exceptions.PreventUpdate
    if not token:
        return "Login requerido.", table_data
    row_idx = active_cell.get("row")
    if row_idx is None or not table_data or row_idx >= len(table_data):
        return "Fila no válida.", table_data
    row = table_data[row_idx]
    cid = row.get("id") or row.get("cable_id")
    if not cid:
        return "Id de tirante no válido.", table_data
    res = call_api("DELETE", f"/cables/{cid}", token=token)
    if isinstance(res, dict) and res.get("status") == "deleted":
        remaining = [r for r in table_data if (r.get("id") or r.get("cable_id")) != cid]
        return f"Tirante {cid} eliminado.", remaining
    return f"Error eliminando tirante {cid}: {res}", table_data


@app.callback(
    Output("bridges-table", "data", allow_duplicate=True),
    Output("br-edit-status", "children", allow_duplicate=True),
    Output("selected-bridge-store", "data", allow_duplicate=True),
    Output("selected-bridge-name", "data", allow_duplicate=True),
    Input("bridge-modal-save", "n_clicks"),
    State("bridge-id", "value"),
    State("bridge-nombre", "value"),
    State("bridge-clave", "value"),
    State("bridge-num", "value"),
    State("bridge-notas", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def save_bridge_modal(_, bid, nombre, clave, num, notas, token):
    if not token:
        return dash.no_update, "Login requerido.", dash.no_update, dash.no_update
    payload = {"nombre": nombre, "clave_interna": clave, "num_tirantes": num, "notas": notas}
    if bid:
        res = call_api("PUT", f"/bridges/{bid}", json=payload, token=token)
    else:
        res = call_api("POST", "/bridges", json=payload, token=token)
    if isinstance(res, dict) and res.get("error"):
        msg = res.get("error")
        if "400" in str(msg):
            msg = "No se puede reducir num_tirantes sin eliminar tirantes primero." if "reducir" in str(msg) else msg
        return dash.no_update, f"Error: {msg}", dash.no_update, dash.no_update
    # refrescar tabla
    refreshed = call_api("GET", "/bridges", token=token)
    table_data = [
        {**b, "ver": "🔍 Ver", "editar": "✏️ Editar", "eliminar": "🗑 Eliminar"} for b in refreshed
    ] if isinstance(refreshed, list) else []
    return table_data, "Puente guardado.", res.get("id"), res.get("nombre")


@app.callback(
    Output("bridges-table", "data", allow_duplicate=True),
    Output("br-edit-status", "children", allow_duplicate=True),
    Output("selected-bridge-store", "data", allow_duplicate=True),
    Output("selected-bridge-name", "data", allow_duplicate=True),
    Input("bridges-table", "active_cell"),
    State("bridges-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def delete_bridge_active(active_cell, rows, token):
    if not active_cell or active_cell.get("column_id") != "eliminar":
        raise dash.exceptions.PreventUpdate
    if not token:
        return dash.no_update, "Login requerido.", dash.no_update, dash.no_update
    row_idx = active_cell.get("row")
    if row_idx is None or not rows or row_idx >= len(rows):
        return dash.no_update, "Fila no válida.", dash.no_update, dash.no_update
    bid = rows[row_idx].get("id")
    res = call_api("DELETE", f"/bridges/{bid}", token=token)
    if isinstance(res, dict) and res.get("status") == "deleted":
        new_rows = [r for i, r in enumerate(rows) if i != row_idx]
        return new_rows, f"Puente {bid} eliminado.", None, None
    msg = f"Error eliminando puente {bid}: {res}"
    if isinstance(res, dict) and "400" in str(res.get("error", "")):
        msg = "No se puede eliminar: primero elimina los tirantes del puente en el Paso 2."
    return dash.no_update, msg, dash.no_update, dash.no_update

@app.callback(
    Output("cable-modal", "is_open"),
    Output("cable-modal-status", "children"),
    Output("modal-cable-id", "value"),
    Output("modal-cable-name", "value"),
    Output("modal-version", "value"),
    Output("modal-valid-from", "value"),
    Output("modal-valid-to", "value"),
    Output("modal-length", "value"),
    Output("modal-strand-type", "value"),
    Output("modal-strand-type", "options"),
    Output("modal-strands-total", "value"),
    Output("modal-strands-active", "value"),
    Output("modal-mu-total", "value"),
    Output("modal-mu-active", "value"),
    Output("modal-E", "value"),
    Output("modal-area", "value"),
    Output("modal-diam", "value"),
    Output("modal-Fu", "value"),
    Output("modal-design", "value"),
    Output("modal-anti", "value"),
    Output("modal-notes", "value"),
    Output("modal-cable-name", "disabled"),
    Output("modal-valid-from", "disabled"),
    Output("modal-valid-to", "disabled"),
    Output("modal-length", "disabled"),
    Output("modal-strand-type", "disabled"),
    Output("modal-strands-total", "disabled"),
    Output("modal-strands-active", "disabled"),
    Output("modal-mu-total", "disabled"),
    Output("modal-mu-active", "disabled"),
    Output("modal-E", "disabled"),
    Output("modal-area", "disabled"),
    Output("modal-diam", "disabled"),
    Output("modal-Fu", "disabled"),
    Output("modal-design", "disabled"),
    Output("modal-anti", "disabled"),
    Output("modal-notes", "disabled"),
    Output("strand-id", "value"),
    Input("cables-states-table", "active_cell"),
    Input("cable-modal-close", "n_clicks"),
    State("cables-states-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def open_cable_modal(active_cell, n_close, table_data, token):
    table_data = table_data or []
    active_cell = active_cell or {}
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]
    empty_return = (
        False,  # modal open
        "",  # status
        None,  # cable id
        None,  # cable name
        None,  # version
        "",  # valid_from
        "",  # valid_to
        None,  # length
        None,  # strand_type value
        [],  # strand options
        None,  # strands_total
        None,  # strands_active
        None,  # mu_total
        None,  # mu_active
        None,  # E
        None,  # area
        None,  # diam
        None,  # Fu
        None,  # design
        None,  # anti
        "",  # notes
        False,  # name disabled
        False,  # valid_from disabled
        False,  # valid_to disabled
        False,  # length disabled
        False,  # strand_type disabled
        False,  # strands_total disabled
        False,  # strands_active disabled
        False,  # mu_total disabled
        False,  # mu_active disabled
        False,  # E disabled
        False,  # area disabled
        False,  # diam disabled
        False,  # Fu disabled
        False,  # design disabled
        False,  # anti disabled
        False,  # notes disabled
        None,  # strand id
    )
    if trigger == "cable-modal-close":
        return empty_return
    if not active_cell or not table_data:
        no_sel = list(empty_return)
        no_sel[1] = "Selecciona un tirante primero."
        return tuple(no_sel)
    col = active_cell.get("column_id")
    if col not in ("ver", "editar"):
        raise dash.exceptions.PreventUpdate
    row_idx = active_cell.get("row")
    if row_idx is None or row_idx >= len(table_data):
        raise dash.exceptions.PreventUpdate
    row = table_data[row_idx]
    cid = row.get("id") or row.get("cable_id")
    latest = {}
    states = call_api("GET", f"/cables/{cid}/states", token=token) if token else []
    if isinstance(states, list) and states:
        latest = states[0]
    strand_options = []
    strands = call_api("GET", "/strand-types", token=token) if token else []
    if isinstance(strands, list):
        strand_options = [{"label": f"{s.get('id')} - {s.get('nombre')}", "value": s.get("id")} for s in strands]
    else:
        strand_options = []
    view_mode = col == "ver"
    disabled = view_mode
    def nz(val, default=""):
        return val if val not in (None, "") else default
    return (
        True,
        "",
        cid,
        row.get("nombre_en_puente"),
        nz(latest.get("id") if latest else None, None),
        nz(latest.get("valid_from") if latest else None, ""),
        nz(latest.get("valid_to") if latest else None, ""),
        nz(latest.get("length_effective_m") if latest else None, None),
        nz(latest.get("strand_type_id") if latest else None, None),
        strand_options or [],
        nz(latest.get("strands_total") if latest else None, None),
        nz(latest.get("strands_active") if latest else None, None),
        nz(latest.get("mu_total_kg_m") if latest else None, None),
        nz(latest.get("mu_active_basis_kg_m") if latest else None, None),
        nz(latest.get("E_MPa") if latest else None, None),
        nz(latest.get("area_mm2") if latest else None, None),
        nz(latest.get("diametro_mm") if latest else None, None),
        nz(latest.get("Fu_override") if latest else None, None),
        nz(latest.get("design_tension_tf") if latest else None, None),
        nz(latest.get("antivandalic_length_m") if latest else None, None),
        nz(latest.get("notes") if latest else None, ""),
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        disabled,
        latest.get("strand_type_id") if latest else None,
    )


@app.callback(
    Output("cable-modal-status", "children", allow_duplicate=True),
    Input("cable-modal-save", "n_clicks"),
    State("modal-cable-id", "value"),
    State("modal-cable-name", "value"),
    State("modal-valid-from", "value"),
    State("modal-valid-to", "value"),
    State("modal-length", "value"),
    State("modal-strand-type", "value"),
    State("modal-strands-total", "value"),
    State("modal-strands-active", "value"),
    State("modal-mu-total", "value"),
    State("modal-mu-active", "value"),
    State("modal-E", "value"),
    State("modal-area", "value"),
    State("modal-diam", "value"),
    State("modal-Fu", "value"),
    State("modal-design", "value"),
    State("modal-anti", "value"),
    State("modal-notes", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def save_cable_state(_, cid, cable_name, v_from, v_to, length, strand_type, stot, sact, mu_tot, mu_act, E, area, diam, Fu, design, anti, notes, token):
    if not token:
        return "Login requerido."
    if not cid:
        return "Falta cable_id."
    # actualizar nombre del tirante si se envía
    if cable_name:
        call_api("PUT", f"/cables/{cid}", json={"nombre_en_puente": cable_name}, token=token)
    required = {
        "vigente desde": v_from,
        "longitud efectiva (m)": length,
        "tipo de torón": strand_type,
        "torones totales": stot,
        "torones activos": sact,
        "masa total (kg/m)": mu_tot,
        "masa activos (kg/m)": mu_act,
        "E (MPa)": E,
        "área (mm²)": area,
        "diámetro (mm)": diam,
        "tensión diseño (tf)": design,
    }
    faltan = [k for k, v in required.items() if v in (None, "", [])]
    if faltan:
        return f"Faltan campos requeridos: {', '.join(faltan)}"
    payload = {
        "cable_id": cid,
        "valid_from": v_from,
        "valid_to": v_to,
        "length_effective_m": length,
        "length_total_m": length,
        "strand_type_id": strand_type,
        "strands_total": stot,
        "strands_active": sact,
        "strands_inactive": max(0, (stot or 0) - (sact or 0)) if stot and sact else 0,
        "mu_total_kg_m": mu_tot,
        "mu_active_basis_kg_m": mu_act,
        "E_MPa": E,
        "area_mm2": area,
        "diametro_mm": diam,
        "design_tension_tf": design,
        "Fu_override": Fu,
        "antivandalic_enabled": bool(anti),
        "antivandalic_length_m": anti,
        "source": notes,
        "notes": notes,
    }
    res = call_api("POST", "/cable-states", json=payload, token=token)
    if isinstance(res, dict) and res.get("error"):
        return f"Error: {res}"
    return f"Guardado estado id {res.get('id') if isinstance(res, dict) else res}"


@app.callback(
    Output("strand-modal", "is_open"),
    Output("strand-status", "children"),
    Output("strand-id", "value", allow_duplicate=True),
    Output("strand-valid-from", "value"),
    Output("strand-valid-to", "value"),
    Output("strand-nombre", "value"),
    Output("strand-mu", "value"),
    Output("strand-E", "value"),
    Output("strand-area", "value"),
    Output("strand-diam", "value"),
    Output("strand-Fu", "value"),
    Output("strand-notas", "value"),
    Input("strand-edit", "n_clicks"),
    Input("strand-new", "n_clicks"),
    Input("strand-table", "active_cell"),
    Input("strand-close", "n_clicks"),
    State("modal-strand-type", "value"),
    State("strand-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def open_strand_modal(n_edit, n_new, active_cell, n_close, strand_type_id, strand_table, token):
    ctx = dash.callback_context
    if not ctx.triggered:
        raise dash.exceptions.PreventUpdate
    trigger = ctx.triggered[0]["prop_id"].split(".")[0]
    empty = (False, "", None, None, None, None, None, None, None, None, None, None)
    if trigger == "strand-close":
        return empty
    if trigger == "strand-new":
        return (
            True,
            "",
            None,
            "",
            "",
            "",
            None,
            None,
            None,
            None,
            None,
            "",
        )
    # determinar id desde tabla o campo existente
    if trigger == "strand-table":
        if not active_cell or not strand_table:
            return (False, "Selecciona un torón en la tabla.", None, None, None, None, None, None, None, None, None, None)
        col = active_cell.get("column_id")
        if col not in ("ver", "editar"):
            raise dash.exceptions.PreventUpdate
        row = strand_table[active_cell.get("row")]
        strand_type_id = row.get("id")
    if not strand_type_id:
        return (False, "Selecciona un torón o crea uno nuevo.", None, None, None, None, None, None, None, None, None, None)
    strands = call_api("GET", "/strand-types", token=token)
    strand = None
    if isinstance(strands, list):
        strand = next((s for s in strands if s.get("id") == strand_type_id), None)
    if not strand:
        return (False, f"No se encontró torón {strand_type_id}", None, None, None, None, None, None, None, None, None, None)
    return (
        True,
        "",
        strand.get("id"),
        "",
        "",
        strand.get("nombre"),
        strand.get("mu_por_toron_kg_m"),
        strand.get("E_MPa"),
        strand.get("area_mm2"),
        strand.get("diametro_mm"),
        strand.get("Fu_default"),
        strand.get("notas"),
    )


@app.callback(
    Output("strand-status", "children", allow_duplicate=True),
    Input("strand-save", "n_clicks"),
    State("strand-id", "value"),
    State("strand-nombre", "value"),
    State("strand-mu", "value"),
    State("strand-E", "value"),
    State("strand-area", "value"),
    State("strand-diam", "value"),
    State("strand-Fu", "value"),
    State("strand-notas", "value"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def save_strand_modal(_, strand_id, nombre, mu, e, area, diam, fu, notas, token):
    payload = {
        "nombre": nombre,
        "mu_por_toron_kg_m": mu,
        "E_MPa": e,
        "area_mm2": area,
        "diametro_mm": diam,
        "Fu_default": fu,
        "notas": notas,
    }
    if strand_id:
        res = call_api("PUT", f"/strand-types/{strand_id}", json=payload, token=token)
    else:
        res = call_api("POST", "/strand-types", json=payload, token=token)
    if isinstance(res, dict) and res.get("error"):
        return f"Error: {res}"
    sid = res.get("id") if isinstance(res, dict) else strand_id
    return f"Torón {sid or 'nuevo'} guardado."


@app.callback(
    Output("strand-action-status", "children", allow_duplicate=True),
    Output("strand-table", "data", allow_duplicate=True),
    Input("strand-table", "active_cell"),
    State("strand-table", "data"),
    State("token-store", "data"),
    prevent_initial_call=True,
)
def delete_strand(active_cell, table_data, token):
    if not active_cell or active_cell.get("column_id") != "eliminar":
        raise dash.exceptions.PreventUpdate
    if not token:
        return "Login requerido.", dash.no_update
    row_idx = active_cell.get("row")
    if row_idx is None or not table_data or row_idx >= len(table_data):
        return "Fila no válida.", dash.no_update
    row = table_data[row_idx]
    sid = row.get("id")
    res = call_api("DELETE", f"/strand-types/{sid}", token=token)
    if isinstance(res, dict) and res.get("status") == "deleted":
        remaining = [r for r in table_data if r.get("id") != sid]
        return f"Torón {sid} eliminado.", remaining
    return f"Error eliminando torón {sid}: {res}", dash.no_update
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
