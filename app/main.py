import logging
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dash
from dash import Dash, Input, Output, State, dcc, html, dash_table, no_update

from sqlalchemy import select

from app.auth_service import ensure_default_admin, hash_password, verify_password
from app.config import ensure_data_dirs
from app.db import Base, get_engine, get_session_local
from app.models import Bridge, Cable, CableStateVersion, Sensor, SensorInstallation, StrandType, User
from app.services import ValidationError, create_cable_state_version, register_installation

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
)
logger = logging.getLogger(__name__)

ensure_data_dirs()
SessionLocal = get_session_local()
Base.metadata.create_all(get_engine())

app = Dash(__name__, suppress_callback_exceptions=True)
server = app.server

NAV_ITEMS = [
    {"label": "Catálogo", "path": "/catalogo"},
    {"label": "Adquisiciones", "path": "/adquisiciones"},
    {"label": "Pesajes directos", "path": "/pesajes-directos"},
    {"label": "Análisis", "path": "/analisis"},
    {"label": "Histórico", "path": "/historico"},
    {"label": "Semáforo", "path": "/semaforo"},
    {"label": "Admin", "path": "/admin"},
]


ensure_default_admin()


def parse_date(value):
    return datetime.fromisoformat(value) if value else None


def render_bridge_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Nombre"),
                    dcc.Input(id="bridge-name", type="text", placeholder="Puente Atirantado"),
                    html.Label("Clave interna"),
                    dcc.Input(id="bridge-key", type="text"),
                    html.Label("Notas"),
                    dcc.Textarea(id="bridge-notes"),
                    html.Button("Guardar", id="bridge-save", n_clicks=0),
                    html.Div(id="bridge-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="bridge-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Nombre", "id": "nombre"},
                    {"name": "Clave", "id": "clave_interna"},
                    {"name": "Notas", "id": "notas"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def render_strand_type_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Nombre"),
                    dcc.Input(id="strand-name", type="text", placeholder="7T"),
                    html.Label("Diámetro (mm)"),
                    dcc.Input(id="strand-diameter", type="number"),
                    html.Label("Área (mm2)"),
                    dcc.Input(id="strand-area", type="number"),
                    html.Label("E (MPa)"),
                    dcc.Input(id="strand-e", type="number"),
                    html.Label("Fu default"),
                    dcc.Input(id="strand-fu", type="number"),
                    html.Label("Peso μ por torón (kg/m)"),
                    dcc.Input(id="strand-mu", type="number"),
                    html.Label("Notas"),
                    dcc.Textarea(id="strand-notes"),
                    html.Button("Guardar", id="strand-save", n_clicks=0),
                    html.Div(id="strand-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="strand-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Nombre", "id": "nombre"},
                    {"name": "Diámetro", "id": "diametro_mm"},
                    {"name": "Área", "id": "area_mm2"},
                    {"name": "E", "id": "e_mpa"},
                    {"name": "Fu", "id": "fu_default"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def render_cable_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Puente"),
                    dcc.Dropdown(id="cable-bridge-dropdown", options=[]),
                    html.Label("Nombre en puente"),
                    dcc.Input(id="cable-name", type="text"),
                    html.Label("Notas"),
                    dcc.Textarea(id="cable-notes"),
                    html.Button("Guardar", id="cable-save", n_clicks=0),
                    html.Div(id="cable-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="cable-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Puente", "id": "bridge"},
                    {"name": "Nombre", "id": "nombre_en_puente"},
                    {"name": "Notas", "id": "notas"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def render_cable_version_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Tirante"),
                    dcc.Dropdown(id="version-cable-dropdown", options=[]),
                    html.Label("Tipo de torón"),
                    dcc.Dropdown(id="version-strand-type-dropdown", options=[]),
                    html.Label("Vigente desde"),
                    dcc.DatePickerSingle(id="version-valid-from"),
                    html.Label("Vigente hasta"),
                    dcc.DatePickerSingle(id="version-valid-to"),
                    html.Label("Longitud efectiva (m)"),
                    dcc.Input(id="version-length-effective", type="number"),
                    html.Label("Longitud total (m)"),
                    dcc.Input(id="version-length-total", type="number"),
                    html.Label("Torones totales"),
                    dcc.Input(id="version-strands-total", type="number"),
                    html.Label("Torones activos"),
                    dcc.Input(id="version-strands-active", type="number"),
                    html.Label("Torones inactivos"),
                    dcc.Input(id="version-strands-inactive", type="number"),
                    html.Label("Diámetro (mm)"),
                    dcc.Input(id="version-diametro", type="number"),
                    html.Label("Área (mm2)"),
                    dcc.Input(id="version-area", type="number"),
                    html.Label("E (MPa)"),
                    dcc.Input(id="version-e", type="number"),
                    html.Label("μ total (kg/m)"),
                    dcc.Input(id="version-mu-total", type="number"),
                    html.Label("μ base activa (kg/m)"),
                    dcc.Input(id="version-mu-active", type="number"),
                    html.Label("Tensión de diseño (tf)"),
                    dcc.Input(id="version-design-tension", type="number"),
                    html.Label("Fu override"),
                    dcc.Input(id="version-fu-override", type="number"),
                    html.Label("Antivandálico"),
                    dcc.Checklist(
                        id="version-antivandalic",
                        options=[{"label": "Habilitado", "value": "enabled"}],
                    ),
                    html.Label("Longitud antivandálica (m)"),
                    dcc.Input(id="version-antivandalic-length", type="number"),
                    html.Label("Fuente"),
                    dcc.Input(id="version-source", type="text"),
                    html.Label("Notas"),
                    dcc.Textarea(id="version-notes"),
                    html.Button("Guardar", id="version-save", n_clicks=0),
                    html.Div(id="version-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="version-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Tirante", "id": "cable"},
                    {"name": "Desde", "id": "valid_from"},
                    {"name": "Hasta", "id": "valid_to"},
                    {"name": "Longitud", "id": "length_effective_m"},
                    {"name": "Torones activos", "id": "strands_active"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def render_sensor_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Tipo de sensor"),
                    dcc.Input(id="sensor-type", type="text", value="acelerometro"),
                    html.Label("Serie/Activo"),
                    dcc.Input(id="sensor-serial", type="text"),
                    html.Label("Unidad"),
                    dcc.Input(id="sensor-unit", type="text", value="g"),
                    html.Label("Notas"),
                    dcc.Textarea(id="sensor-notes"),
                    html.Button("Guardar", id="sensor-save", n_clicks=0),
                    html.Div(id="sensor-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="sensor-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Tipo", "id": "sensor_type"},
                    {"name": "Serie", "id": "serial_or_asset_id"},
                    {"name": "Unidad", "id": "unit"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def render_installation_form():
    return html.Div(
        [
            html.Div(
                [
                    html.Label("Sensor"),
                    dcc.Dropdown(id="installation-sensor-dropdown", options=[]),
                    html.Label("Tirante"),
                    dcc.Dropdown(id="installation-cable-dropdown", options=[]),
                    html.Label("Instalado desde"),
                    dcc.DatePickerSingle(id="installation-from"),
                    html.Label("Instalado hasta"),
                    dcc.DatePickerSingle(id="installation-to"),
                    html.Label("Altura (m)"),
                    dcc.Input(id="installation-height", type="number"),
                    html.Label("Montaje"),
                    dcc.Textarea(id="installation-mounting"),
                    html.Label("Notas"),
                    dcc.Textarea(id="installation-notes"),
                    html.Button("Guardar", id="installation-save", n_clicks=0),
                    html.Div(id="installation-message", className="alert"),
                ],
                className="form-grid",
            ),
            dash_table.DataTable(
                id="installation-table",
                columns=[
                    {"name": "ID", "id": "id"},
                    {"name": "Sensor", "id": "sensor"},
                    {"name": "Tirante", "id": "cable"},
                    {"name": "Desde", "id": "installed_from"},
                    {"name": "Hasta", "id": "installed_to"},
                    {"name": "Altura", "id": "height_m"},
                ],
                data=[],
            ),
        ],
        className="form-section",
    )


def make_sidebar():
    return html.Div(
        [html.H2("CeMPEI | IMT"), html.H4("Gestión de tirantes"), html.Hr()]
        + [
            html.Div(
                dcc.Link(item["label"], href=item["path"], className="nav-link"),
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
            dcc.Tabs(
                id="catalog-tabs",
                value="bridges",
                children=[
                    dcc.Tab(label="Puentes", value="bridges", children=render_bridge_form()),
                    dcc.Tab(
                        label="Tipos de torón", value="strand-types", children=render_strand_type_form()
                    ),
                    dcc.Tab(label="Tirantes", value="cables", children=render_cable_form()),
                    dcc.Tab(
                        label="Versiones de tirante",
                        value="cable-versions",
                        children=render_cable_version_form(),
                    ),
                    dcc.Tab(label="Sensores", value="sensors", children=render_sensor_form()),
                    dcc.Tab(
                        label="Instalaciones",
                        value="installations",
                        children=render_installation_form(),
                    ),
                ],
            ),
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
    if pathname.startswith("/home"):
        return html.Div([
            html.H3("Bienvenida"),
            html.P("Sistema de gestión histórica y análisis de tirantes para puentes atirantados."),
        ])
    return html.Div([
        html.H3("Bienvenida"),
        html.P("Sistema de gestión histórica y análisis de tirantes para puentes atirantados."),
    ])


def render_login():
    return html.Div(
        [
            html.H2("Ingreso"),
            html.Label("Correo"),
            dcc.Input(id="login-email", type="email", placeholder="admin@example.com"),
            html.Label("Contraseña"),
            dcc.Input(id="login-password", type="password", placeholder="******"),
            html.Button("Entrar", id="login-button"),
            html.Div(id="login-alert", className="alert"),
        ],
        className="login-container",
    )


def render_layout():
    return html.Div(
        [
            dcc.Location(id="url"),
            dcc.Store(id="current-user", storage_type="session"),
            html.Div(id="page", children=render_login()),
        ]
    )


app.layout = render_layout()


def render_app_shell():
    return html.Div(
        [
            html.Div(
                [
                    make_sidebar(),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(id="user-summary"),
                                    html.Button("Cerrar sesión", id="logout-button", n_clicks=0),
                                ],
                                className="topbar",
                            ),
                            html.Div(id="content", children=build_content("/")),
                        ],
                        className="content-area",
                    ),
                ],
                className="layout",
            ),
        ]
    )


@app.callback(
    Output("page", "children"),
    Input("current-user", "data"),
    Input("url", "pathname"),
)
def guard_routes(user_data, pathname):
    if not user_data:
        return render_login()
    return render_app_shell()


@app.callback(
    Output("user-summary", "children"),
    Input("current-user", "data"),
)
def show_user(user_data):
    if not user_data:
        return "Sesión no iniciada"
    return f"{user_data['email']} ({user_data['role']})"


@app.callback(
    Output("login-alert", "children"),
    Output("current-user", "data"),
    Output("url", "pathname"),
    Input("login-button", "n_clicks"),
    State("login-email", "value"),
    State("login-password", "value"),
    prevent_initial_call=True,
)
def handle_login(n_clicks, email, password):
    logger.info("Login click received")
    if not n_clicks:
        return no_update, no_update, no_update

    email = (email or "").strip().lower()
    password = (password or "").strip()

    logger.info("Email received: %s", email)

    if not email or not password:
        return "Ingresa correo y contraseña", no_update, no_update

    try:
        with SessionLocal() as session:
            user = session.scalars(select(User).where(User.email == email)).first()

            if not user:
                logger.info("User not found: %s", email)
                return "Usuario no existe", no_update, no_update

            logger.info("User found: %s", email)

            if not verify_password(password, user.hashed_password):
                logger.info("Incorrect password for: %s", email)
                return "Contraseña incorrecta", no_update, no_update

            if not getattr(user, "is_active", True):
                logger.info("Inactive user attempted login: %s", email)
                return "Usuario inactivo", no_update, no_update

            logger.info("Authentication successful for %s", email)
            return "Inicio de sesión correcto", {"email": user.email, "role": user.role}, "/home"
    except Exception:
        logger.exception("Unexpected error during login")
        return "Error interno. Revisa logs.", no_update, no_update


@app.callback(
    Output("current-user", "data"),
    Input("logout-button", "n_clicks"),
    prevent_initial_call=True,
)
def logout(_):
    return None


def serialize_datetime(value: datetime | None) -> str:
    return value.isoformat() if value else ""


@app.callback(
    Output("bridge-table", "data"),
    Output("bridge-message", "children"),
    Input("url", "pathname"),
    Input("bridge-save", "n_clicks"),
    State("bridge-name", "value"),
    State("bridge-key", "value"),
    State("bridge-notes", "value"),
    prevent_initial_call=False,
)
def handle_bridges(pathname, n_clicks, name, key, notes):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        if not name:
            message = "El nombre es obligatorio"
        else:
            with SessionLocal() as session:
                try:
                    session.add(Bridge(nombre=name, clave_interna=key, notas=notes))
                    session.commit()
                    message = "Puente guardado"
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        data = [
            {
                "id": b.id,
                "nombre": b.nombre,
                "clave_interna": b.clave_interna,
                "notas": b.notas,
            }
            for b in session.scalars(select(Bridge)).all()
        ]
    return data, message


@app.callback(
    Output("strand-table", "data"),
    Output("strand-message", "children"),
    Input("url", "pathname"),
    Input("strand-save", "n_clicks"),
    State("strand-name", "value"),
    State("strand-diameter", "value"),
    State("strand-area", "value"),
    State("strand-e", "value"),
    State("strand-fu", "value"),
    State("strand-mu", "value"),
    State("strand-notes", "value"),
    prevent_initial_call=False,
)
def handle_strand_types(pathname, n_clicks, name, diameter, area, e_mpa, fu, mu, notes):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        required = [name, diameter, area, e_mpa, fu]
        if any(v is None for v in required):
            message = "Captura nombre, diámetro, área, E y Fu"
        else:
            with SessionLocal() as session:
                try:
                    session.add(
                        StrandType(
                            nombre=name,
                            diametro_mm=float(diameter),
                            area_mm2=float(area),
                            e_mpa=float(e_mpa),
                            fu_default=float(fu),
                            mu_por_toron_kg_m=float(mu) if mu is not None else None,
                            notas=notes,
                        )
                    )
                    session.commit()
                    message = "Tipo de torón guardado"
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        data = [
            {
                "id": st.id,
                "nombre": st.nombre,
                "diametro_mm": st.diametro_mm,
                "area_mm2": st.area_mm2,
                "e_mpa": st.e_mpa,
                "fu_default": st.fu_default,
            }
            for st in session.scalars(select(StrandType)).all()
        ]
    return data, message


@app.callback(
    Output("cable-table", "data"),
    Output("cable-message", "children"),
    Input("url", "pathname"),
    Input("cable-save", "n_clicks"),
    State("cable-bridge-dropdown", "value"),
    State("cable-name", "value"),
    State("cable-notes", "value"),
    prevent_initial_call=False,
)
def handle_cables(pathname, n_clicks, bridge_id, name, notes):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        if not bridge_id or not name:
            message = "Selecciona puente y nombre"
        else:
            with SessionLocal() as session:
                try:
                    session.add(
                        Cable(bridge_id=int(bridge_id), nombre_en_puente=name, notas=notes)
                    )
                    session.commit()
                    message = "Tirante guardado"
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        cables = session.scalars(select(Cable)).all()
        data = [
            {
                "id": c.id,
                "bridge": c.bridge.nombre if c.bridge else c.bridge_id,
                "nombre_en_puente": c.nombre_en_puente,
                "notas": c.notas,
            }
            for c in cables
        ]
    return data, message


@app.callback(
    Output("version-table", "data"),
    Output("version-message", "children"),
    Input("url", "pathname"),
    Input("version-save", "n_clicks"),
    State("version-cable-dropdown", "value"),
    State("version-strand-type-dropdown", "value"),
    State("version-valid-from", "date"),
    State("version-valid-to", "date"),
    State("version-length-effective", "value"),
    State("version-length-total", "value"),
    State("version-strands-total", "value"),
    State("version-strands-active", "value"),
    State("version-strands-inactive", "value"),
    State("version-diametro", "value"),
    State("version-area", "value"),
    State("version-e", "value"),
    State("version-mu-total", "value"),
    State("version-mu-active", "value"),
    State("version-design-tension", "value"),
    State("version-fu-override", "value"),
    State("version-antivandalic", "value"),
    State("version-antivandalic-length", "value"),
    State("version-source", "value"),
    State("version-notes", "value"),
    prevent_initial_call=False,
)
def handle_versions(
    pathname,
    n_clicks,
    cable_id,
    strand_type_id,
    valid_from,
    valid_to,
    length_effective,
    length_total,
    strands_total,
    strands_active,
    strands_inactive,
    diametro,
    area,
    e_mpa,
    mu_total,
    mu_active,
    design_tension,
    fu_override,
    antivandalic,
    antivandalic_length,
    source,
    notes,
):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        required = [cable_id, strand_type_id, valid_from, length_effective, strands_total, strands_active]
        if any(v in (None, "") for v in required):
            message = "Llena tirante, tipo de torón, fecha desde, longitud y torones"
        else:
            candidate = CableStateVersion(
                cable_id=int(cable_id),
                strand_type_id=int(strand_type_id),
                valid_from=parse_date(valid_from),
                valid_to=parse_date(valid_to),
                length_effective_m=float(length_effective),
                length_total_m=float(length_total) if length_total else None,
                strands_total=int(strands_total),
                strands_active=int(strands_active),
                strands_inactive=int(strands_inactive or 0),
                diametro_mm=float(diametro or 0),
                area_mm2=float(area or 0),
                e_mpa=float(e_mpa or 0),
                mu_total_kg_m=float(mu_total or 0),
                mu_active_basis_kg_m=float(mu_active or 0),
                design_tension_tf=float(design_tension or 0),
                fu_override=float(fu_override) if fu_override else None,
                antivandalic_enabled=bool(antivandalic),
                antivandalic_length_m=float(antivandalic_length) if antivandalic_length else None,
                source=source,
                notes=notes,
            )
            with SessionLocal() as session:
                try:
                    create_cable_state_version(candidate, session=session)
                    session.commit()
                    message = "Versión guardada"
                except ValidationError as exc:
                    session.rollback()
                    message = str(exc)
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        versions = session.scalars(select(CableStateVersion)).all()
        data = [
            {
                "id": v.id,
                "cable": v.cable.nombre_en_puente if v.cable else v.cable_id,
                "valid_from": serialize_datetime(v.valid_from),
                "valid_to": serialize_datetime(v.valid_to),
                "length_effective_m": v.length_effective_m,
                "strands_active": v.strands_active,
            }
            for v in versions
        ]
    return data, message


@app.callback(
    Output("sensor-table", "data"),
    Output("sensor-message", "children"),
    Input("url", "pathname"),
    Input("sensor-save", "n_clicks"),
    State("sensor-type", "value"),
    State("sensor-serial", "value"),
    State("sensor-unit", "value"),
    State("sensor-notes", "value"),
    prevent_initial_call=False,
)
def handle_sensors(pathname, n_clicks, sensor_type, serial, unit, notes):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        if not serial:
            message = "Captura número de serie"
        else:
            with SessionLocal() as session:
                try:
                    session.add(
                        Sensor(
                            sensor_type=sensor_type or "acelerometro",
                            serial_or_asset_id=serial,
                            unit=unit or "g",
                            notas=notes,
                        )
                    )
                    session.commit()
                    message = "Sensor guardado"
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        data = [
            {
                "id": s.id,
                "sensor_type": s.sensor_type,
                "serial_or_asset_id": s.serial_or_asset_id,
                "unit": s.unit,
            }
            for s in session.scalars(select(Sensor)).all()
        ]
    return data, message


@app.callback(
    Output("installation-table", "data"),
    Output("installation-message", "children"),
    Input("url", "pathname"),
    Input("installation-save", "n_clicks"),
    State("installation-sensor-dropdown", "value"),
    State("installation-cable-dropdown", "value"),
    State("installation-from", "date"),
    State("installation-to", "date"),
    State("installation-height", "value"),
    State("installation-mounting", "value"),
    State("installation-notes", "value"),
    prevent_initial_call=False,
)
def handle_installations(
    pathname,
    n_clicks,
    sensor_id,
    cable_id,
    installed_from,
    installed_to,
    height,
    mounting,
    notes,
):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update

    message = ""
    if n_clicks:
        required = [sensor_id, cable_id, installed_from, height]
        if any(v in (None, "") for v in required):
            message = "Captura sensor, tirante, fechas y altura"
        else:
            candidate = SensorInstallation(
                sensor_id=int(sensor_id),
                cable_id=int(cable_id),
                installed_from=parse_date(installed_from),
                installed_to=parse_date(installed_to),
                height_m=float(height),
                mounting_details=mounting,
                notes=notes,
            )
            with SessionLocal() as session:
                try:
                    register_installation(candidate, session=session)
                    session.commit()
                    message = "Instalación guardada"
                except ValidationError as exc:
                    session.rollback()
                    message = str(exc)
                except Exception as exc:  # pragma: no cover - feedback runtime
                    session.rollback()
                    message = f"No se pudo guardar: {exc}"

    with SessionLocal() as session:
        installations = session.scalars(select(SensorInstallation)).all()
        data = [
            {
                "id": inst.id,
                "sensor": inst.sensor_id,
                "cable": inst.cable_id,
                "installed_from": serialize_datetime(inst.installed_from),
                "installed_to": serialize_datetime(inst.installed_to),
                "height_m": inst.height_m,
            }
            for inst in installations
        ]
    return data, message


@app.callback(
    Output("cable-bridge-dropdown", "options"),
    Output("version-cable-dropdown", "options"),
    Output("installation-cable-dropdown", "options"),
    Output("installation-sensor-dropdown", "options"),
    Output("version-strand-type-dropdown", "options"),
    Input("url", "pathname"),
    Input("bridge-save", "n_clicks"),
    Input("cable-save", "n_clicks"),
    Input("strand-save", "n_clicks"),
    Input("sensor-save", "n_clicks"),
)
def refresh_options(pathname, *_):
    if not pathname or not pathname.startswith("/catalogo"):
        return no_update, no_update, no_update, no_update, no_update

    with SessionLocal() as session:
        bridges = session.scalars(select(Bridge)).all()
        cables = session.scalars(select(Cable)).all()
        sensors = session.scalars(select(Sensor)).all()
        strand_types = session.scalars(select(StrandType)).all()

    bridge_opts = [{"label": b.nombre, "value": b.id} for b in bridges]
    cable_opts = [{"label": c.nombre_en_puente, "value": c.id} for c in cables]
    sensor_opts = [
        {"label": f"{s.sensor_type} | {s.serial_or_asset_id}", "value": s.id} for s in sensors
    ]
    strand_opts = [{"label": st.nombre, "value": st.id} for st in strand_types]
    return bridge_opts, cable_opts, cable_opts, sensor_opts, strand_opts


@app.callback(Output("content", "children"), Input("url", "pathname"))
def display_page(pathname: str):
    return build_content(pathname or "/")


if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=int(os.getenv("PORT", 8050)))
