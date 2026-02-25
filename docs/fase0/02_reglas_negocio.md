# Reglas de Negocio v1 - TCeMPEI

## 1. Catalogo estructural
- Un puente tiene identidad propia y metadatos obligatorios: nombre, clave interna, ubicacion/proyecto, fecha alta, estado activo.
- Un tirante es una entidad permanente del puente y debe guardar historial tecnico.
- Campos obligatorios de tirante: codigo unico, puente_id, longitud efectiva, torones total/activos, E, area, masa lineal, Fu base.
- Unidades oficiales: m, kg/m, MPa, mm2, Hz, tf (kN opcional).
- Se permite renombrar tirantes guardando alias historico con vigencia.

## 2. Versionado de estado de tirante
- El versionado es manual asistido.
- Toda modificacion estructural debe generar nueva version.
- Debe existir como maximo una version abierta por tirante.
- Validaciones obligatorias:
- No traslapes de vigencia.
- torones_activos <= torones_totales.
- magnitudes positivas.
- vigencias consistentes (valid_to > valid_from cuando aplique).
- Acero: norma y grado obligatorios; lote opcional recomendado.

## 3. Pesajes y constante K
- Modo de K: mixto (manual + calculada).
- Formula oficial de calculo: K = T_pesaje / f0^2.
- K depende de tirante + snapshot de configuracion.
- Alta de una nueva K abre nueva vigencia.
- Cierre de vigencia: fecha explicita o reemplazo.
- Debe existir exactamente una K vigente por tirante/fecha.
- Si no hay K vigente al analizar: se bloquea el guardado con error explicito.
- Metadatos obligatorios de pesaje: fecha/hora, operador, metodo, equipo, temperatura, tension medida, observaciones.
- Adjuntos de pesaje: opcionales. Recomendado al menos una evidencia cuando exista.

## 4. Campanas y archivos
- Una campaña puede tener hasta 150 archivos raw.
- Formato de archivo aceptado en v1: CSV UTF-8.
- Deteccion de datos: busqueda de linea marcador DATA_START (configurable).
- Si falla deteccion automatica: seleccionar manualmente fila de cabecera en UI.
- Re-subida: versionado por archivo, nunca sobrescribir.
- Archivo raw: inmutable.
- Duplicados por hash:
- Bloquear duplicado exacto en la misma campaña.
- Advertir duplicado en campañas distintas.

## 5. Mapeo de canales
- Mapeo canal->tirante via UI.
- Regla por defecto: un tirante no recibe multiples canales.
- Excepcion: permitir multicanal intencional con bandera explicita.
- Validaciones que bloquean normalizacion:
- canal sin tirante.
- tirante duplicado no intencional.
- altura invalida.
- columna inexistente.
- Altura de sensor obligatoria para canales activos de analisis.
- Version de parser/proceso obligatoria en metadatos.

## 6. Analisis dinamico
- Visualizaciones minimas: acelerograma completo y segmento, FFT, PSD Welch.
- Libreria oficial: scipy.signal + numpy.fft.
- Parametros con versionado:
- nperseg 256-16384.
- noverlap 0%-90%.
- threshold 0-1 normalizado.
- armonicos 1-10, default 3.
- f0 con propuesta asistida y validacion manual.
- Se permite fijar f0 manual directa.
- Escala de calidad: ok, doubtful, bad + comentario tecnico.
- Formula oficial de tension: T = f^2 * K.
- Persistencia:
- resumen de resultados en BD obligatorio.
- curvas completas comprimidas opcionales.

## 7. Versionado y aprobacion de analisis
- Cada guardado crea una corrida inmutable con parametros exactos.
- Regla de aprobado: uno vigente por tirante+campana+archivo.
- Roles que aprueban: reviewer y admin.
- Reemplazo logico de aprobado, manteniendo historial completo.

## 8. Resumen y semaforo
- Resumen por campaña (columnas minimas):
- tirante, f0, T, K usada, fecha analisis, estado, aprobado_por.
- Filtros minimos: puente, campaña, tirante, fecha, estado, aprobado/no aprobado.
- Umbrales semaforo:
- OK <= 40% Fu.
- PREALERTA > 40% y <= 45%.
- ALERTA > 45%.
- Anomalias: fuera de alcance v1 (solo historico visual).

## 9. Historico por tirante
- Debe mostrar evolucion temporal de f0, T y K utilizada.
- Debe permitir comparar campañas distintas.

## 10. Seguridad, auditoria y cumplimiento
- Roles v1: admin, analyst, reviewer, viewer.
- JWT access token 8h y refresh token 7 dias.
- Password policy: minimo 12 caracteres, complejidad media, bloqueo por intentos fallidos.
- Diseno de autenticacion desacoplado para integrar SSO/LDAP en v1.1.
- Borrado: soft delete por defecto; hard delete solo admin con motivo.
- Auditoria obligatoria:
- login/logout.
- CRUD tecnico.
- cargas de archivo.
- calculo/alta K.
- aprobacion/rechazo analisis.
- Detalle de auditoria: usuario, fecha, accion, entidad, antes/despues JSON, motivo, IP.
- Retencion de auditoria/logs: 10 anios.
- Exportacion de bitacora: CSV y JSON.
