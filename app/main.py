import os
from datetime import datetime

import dash
from dash import Dash, Input, Output, dcc, html

from .config import ensure_data_dirs
from .db import get_session_local
from .models import Base

ensure_data_dirs()
SessionLocal = get_session_local()

app = Dash(__name__)
server = app.server

NAV_ITEMS = [
    "Catálogo",
    "Adquisiciones",
    "Pesajes directos",
    "Análisis",
    "Histórico",
    "Semáforo",
    "Admin",
]


def make_sidebar():
    return html.Div(
        [html.H2("CeMPEI | IMT"), html.H4("Gestión de tirantes"), html.Hr()] +
        [
            html.Div(
                dcc.Link(item, href=f"/{item.lower().replace(' ', '-')}", className="nav-link"),
                className="nav-item",
            )
            for item in NAV_ITEMS
        ],
        className="sidebar",
    )


def build_content(pathname: str):
    if pathname.startswith("/catalogo"):
        return html.Div([
            html.H3("Catálogo"),
            html.P("Alta de puentes, tirantes, tipos de torón y sensores con historial versionado."),
        ])
    if pathname.startswith("/adquisiciones"):
        return html.Div([
            html.H3("Adquisiciones"),
            html.Ul([
                html.Li("Wizard de 4 pasos: datos, carga CSV, mapeo, normalizado."),
                html.Li("Registra hash SHA256 y metadatos de archivos."),
            ]),
        ])
    if pathname.startswith("/pesajes-directos"):
        return html.Div([
            html.H3("Pesajes directos"),
            html.P("Registrar campañas de pesaje, snapshots y calibraciones K con rango de validez."),
        ])
    if pathname.startswith("/analisis"):
        return html.Div([
            html.H3("Análisis"),
            html.P("Crear sesiones (runs) por campaña, configurar parámetros por tirante y guardar resultados."),
        ])
    if pathname.startswith("/historico"):
        return html.Div([
            html.H3("Histórico"),
            html.P("Consultas de f0, tensión y K versus fecha con filtros por puente y tirante."),
        ])
    if pathname.startswith("/semaforo"):
        return html.Div([
            html.H3("Semáforo"),
            html.P("Indicadores por puente con criterio T > 0.45 Fu usando estado vigente del tirante."),
        ])
    if pathname.startswith("/admin"):
        return html.Div([
            html.H3("Admin"),
            html.P("Gestión de usuarios y auditoría mínima."),
        ])
    return html.Div([
        html.H3("Bienvenida"),
        html.P("Sistema de gestión histórica y análisis de tirantes para puentes atirantados."),
    ])


app.layout = html.Div(
    [
        dcc.Location(id="url"),
        html.Div(make_sidebar(), className="sidebar-container"),
        html.Div(id="content"),
    ],
    className="layout",
)


@app.callback(Output("content", "children"), Input("url", "pathname"))
def display_page(pathname: str):
    return build_content(pathname or "/")


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=int(os.getenv("PORT", 8050)))
