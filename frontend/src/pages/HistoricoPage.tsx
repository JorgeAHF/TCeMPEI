import { useEffect, useMemo, useState } from 'react'
import type { Config, Data, Layout } from 'plotly.js'
import Plot from 'react-plotly.js'
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner, Table } from 'react-bootstrap'
import api from '../lib/apiClient'
import { apiErrorMessage, formatDateTime } from '../lib/utils'
import { AnomaliesResponse, Bridge, Cable, HistoryItem, HistoryResponse } from '../types/api'

const plotConfig: Partial<Config> = {
  responsive: true,
  displaylogo: false,
}

const plotLayout: Partial<Layout> = {
  autosize: true,
  margin: { l: 48, r: 24, t: 40, b: 42 },
}

export default function HistoricoPage() {
  const [bridges, setBridges] = useState<Bridge[]>([])
  const [cables, setCables] = useState<Cable[]>([])
  const [bridgeId, setBridgeId] = useState('')
  const [cableId, setCableId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [zThreshold, setZThreshold] = useState('2.5')
  const [history, setHistory] = useState<HistoryResponse | null>(null)
  const [anomalies, setAnomalies] = useState<AnomaliesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const filteredCables = useMemo(
    () => cables.filter((cable) => !bridgeId || String(cable.bridge_id) === bridgeId),
    [bridgeId, cables],
  )

  useEffect(() => {
    loadContext()
  }, [])

  async function loadContext() {
    setLoading(true)
    try {
      const [bridgesRes, cablesRes] = await Promise.all([api.get('/bridges'), api.get('/cables')])
      setBridges(bridgesRes.data)
      setCables(cablesRes.data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el histórico'))
    } finally {
      setLoading(false)
    }
  }

  function buildParams(): Record<string, string> {
    const params: Record<string, string> = {}
    if (bridgeId) params.bridge_id = bridgeId
    if (cableId) params.cable_id = cableId
    if (dateFrom) params.date_from = `${dateFrom}T00:00:00`
    if (dateTo) params.date_to = `${dateTo}T23:59:59`
    return params
  }

  async function handleQuery() {
    setSubmitting(true)
    setError('')
    setAnomalies(null)
    try {
      const { data } = await api.get('/history', { params: buildParams() })
      setHistory(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo consultar el histórico'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDetectAnomalies() {
    if (!cableId) {
      setError('Selecciona un tirante específico para detectar anomalías')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const params: Record<string, string> = { z_threshold: zThreshold }
      if (dateFrom) params.date_from = `${dateFrom}T00:00:00`
      if (dateTo) params.date_to = `${dateTo}T23:59:59`
      const { data } = await api.get(`/cables/${cableId}/anomalies`, { params })
      setAnomalies(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo ejecutar la detección de anomalías'))
    } finally {
      setSubmitting(false)
    }
  }

  // Construye series normales + serie de anomalías resaltadas
  function buildSeriesWithAnomalies(items: HistoryItem[], key: 'tension_tf' | 'f0_hz'): Data[] {
    const byCable = new Map<string, HistoryItem[]>()
    items.forEach((item) => {
      const bucket = byCable.get(item.nombre_en_puente) || []
      bucket.push(item)
      byCable.set(item.nombre_en_puente, bucket)
    })

    const anomalyDates = new Set(anomalies?.items.filter((a) => a.is_anomaly).map((a) => a.acquired_at) ?? [])

    const series: Data[] = []
    byCable.forEach((sItems, name) => {
      series.push({
        type: 'scatter',
        mode: 'lines+markers',
        name,
        x: sItems.map((item) => item.acquired_at),
        y: sItems.map((item) => item[key]),
        marker: { size: 6 },
      } satisfies Data)

      // Capa de anomalías encima
      if (anomalies && anomalyDates.size > 0) {
        const anomalousItems = sItems.filter((item) => anomalyDates.has(item.acquired_at))
        if (anomalousItems.length > 0) {
          series.push({
            type: 'scatter',
            mode: 'markers',
            name: `${name} — anomalía`,
            x: anomalousItems.map((item) => item.acquired_at),
            y: anomalousItems.map((item) => item[key]),
            marker: { color: '#dc3545', size: 12, symbol: 'x', line: { width: 2, color: '#dc3545' } },
            showlegend: true,
          } satisfies Data)
        }
      }
    })
    return series
  }

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <Spinner size="sm" />
        <span>Cargando histórico…</span>
      </div>
    )
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="fw-bold mb-1">Histórico</h4>
          <p className="text-muted mb-0">Evolución de tensión y frecuencia por tirante</p>
        </div>
        <Button variant="outline-secondary" onClick={loadContext} disabled={submitting}>
          Recargar
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}

      <Card className="mb-4">
        <Card.Body>
          <Row className="g-3 align-items-end">
            <Col md={3}>
              <Form.Label>Puente</Form.Label>
              <Form.Select
                value={bridgeId}
                onChange={(event) => {
                  setBridgeId(event.target.value)
                  setCableId('')
                  setAnomalies(null)
                }}
              >
                <option value="">Todos…</option>
                {bridges.map((bridge) => (
                  <option key={bridge.id} value={bridge.id}>
                    {bridge.nombre}
                  </option>
                ))}
              </Form.Select>
            </Col>
            <Col md={3}>
              <Form.Label>Tirante</Form.Label>
              <Form.Select
                value={cableId}
                onChange={(event) => {
                  setCableId(event.target.value)
                  setAnomalies(null)
                }}
              >
                <option value="">Todos…</option>
                {filteredCables.map((cable) => (
                  <option key={cable.id} value={cable.id}>
                    {cable.nombre_en_puente}
                  </option>
                ))}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Form.Label>Desde</Form.Label>
              <Form.Control type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
            </Col>
            <Col md={2}>
              <Form.Label>Hasta</Form.Label>
              <Form.Control type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            </Col>
            <Col md={2}>
              <Button onClick={handleQuery} disabled={submitting} className="w-100">
                Consultar
              </Button>
            </Col>
          </Row>

          {cableId && (
            <Row className="g-3 align-items-end mt-1 border-top pt-3">
              <Col md={12}>
                <small className="text-muted fw-semibold">Detección de anomalías (requiere tirante seleccionado)</small>
              </Col>
              <Col md={3}>
                <Form.Label>Umbral z-score</Form.Label>
                <Form.Control
                  type="number"
                  step="0.1"
                  min="0.5"
                  max="10"
                  value={zThreshold}
                  onChange={(event) => setZThreshold(event.target.value)}
                />
                <Form.Text className="text-muted">Típico: 2.0–3.0</Form.Text>
              </Col>
              <Col md={3} className="d-flex align-items-end">
                <Button variant="warning" onClick={handleDetectAnomalies} disabled={submitting} className="w-100">
                  Detectar anomalías
                </Button>
              </Col>
              {anomalies && (
                <Col md={6} className="d-flex align-items-end">
                  <Alert
                    variant={anomalies.n_anomalies > 0 ? 'warning' : 'success'}
                    className="mb-0 w-100 py-2"
                  >
                    {anomalies.n_anomalies > 0 ? (
                      <>
                        <strong>{anomalies.n_anomalies}</strong> anomalía{anomalies.n_anomalies !== 1 ? 's' : ''} detectada{anomalies.n_anomalies !== 1 ? 's' : ''} de{' '}
                        <strong>{anomalies.n_results}</strong> resultados (z &gt; {anomalies.z_threshold})
                      </>
                    ) : (
                      <>Sin anomalías en {anomalies.n_results} resultados (z &gt; {anomalies.z_threshold})</>
                    )}
                  </Alert>
                </Col>
              )}
            </Row>
          )}
        </Card.Body>
      </Card>

      {history && (
        <>
          <Row className="g-3 mb-4">
            <Col xs={6} md={3}>
              <Card className="text-center py-3">
                <Card.Body>
                  <h3 className="fw-bold mb-0">{history.results.length}</h3>
                  <small className="text-muted">Resultados</small>
                </Card.Body>
              </Card>
            </Col>
            <Col xs={6} md={3}>
              <Card className="text-center py-3">
                <Card.Body>
                  <h3 className="fw-bold mb-0">{new Set(history.results.map((item) => item.cable_id)).size}</h3>
                  <small className="text-muted">Tirantes</small>
                </Card.Body>
              </Card>
            </Col>
            {anomalies && anomalies.n_anomalies > 0 && (
              <Col xs={6} md={3}>
                <Card className="text-center py-3 border-warning">
                  <Card.Body>
                    <h3 className="fw-bold mb-0 text-warning">{anomalies.n_anomalies}</h3>
                    <small className="text-muted">Anomalías detectadas</small>
                  </Card.Body>
                </Card>
              </Col>
            )}
          </Row>

          {history.results.length > 0 ? (
            <>
              <Row className="g-3 mb-4">
                <Col xl={6}>
                  <Card>
                    <Card.Body>
                      <Plot
                        data={buildSeriesWithAnomalies(history.results, 'tension_tf')}
                        layout={{
                          ...plotLayout,
                          title: { text: 'Tensión vs fecha' },
                          xaxis: { title: { text: 'Fecha' } },
                          yaxis: { title: { text: 'Tensión [tf]' } },
                        }}
                        config={plotConfig}
                        style={{ width: '100%', height: 360 }}
                        useResizeHandler
                      />
                    </Card.Body>
                  </Card>
                </Col>
                <Col xl={6}>
                  <Card>
                    <Card.Body>
                      <Plot
                        data={buildSeriesWithAnomalies(history.results, 'f0_hz')}
                        layout={{
                          ...plotLayout,
                          title: { text: 'f0 vs fecha' },
                          xaxis: { title: { text: 'Fecha' } },
                          yaxis: { title: { text: 'Frecuencia [Hz]' } },
                        }}
                        config={plotConfig}
                        style={{ width: '100%', height: 360 }}
                        useResizeHandler
                      />
                    </Card.Body>
                  </Card>
                </Col>
              </Row>

              <Card className="mb-4">
                <Card.Body>
                  <h5 className="mb-3">Resultados</h5>
                  <Table hover responsive size="sm" className="mb-0">
                    <thead className="table-light">
                      <tr>
                        <th>Fecha</th>
                        <th>Tirante</th>
                        <th>Run</th>
                        <th>f0 Hz</th>
                        <th>Tensión tf</th>
                        <th>K</th>
                        <th>Calidad</th>
                        {anomalies && <th>Anomalía</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {history.results.map((item) => {
                        const anomalyItem = anomalies?.items.find(
                          (a) => a.acquired_at === item.acquired_at && a.cable_id === item.cable_id,
                        )
                        const isAnomaly = anomalyItem?.is_anomaly ?? false
                        return (
                          <tr
                            key={`${item.analysis_run_id}-${item.cable_id}-${item.acquired_at}`}
                            className={isAnomaly ? 'table-warning' : undefined}
                          >
                            <td>{formatDateTime(item.acquired_at)}</td>
                            <td>{item.nombre_en_puente}</td>
                            <td>{item.analysis_run_id}</td>
                            <td>{item.f0_hz.toFixed(4)}</td>
                            <td>{item.tension_tf.toFixed(4)}</td>
                            <td>{item.k_used_value.toFixed(4)}</td>
                            <td>{item.quality_flag}</td>
                            {anomalies && (
                              <td>
                                {isAnomaly ? (
                                  <Badge bg="warning" text="dark" title={anomalyItem?.anomaly_reason ?? ''}>
                                    Anomalía
                                  </Badge>
                                ) : (
                                  <Badge bg="light" text="secondary">
                                    Normal
                                  </Badge>
                                )}
                              </td>
                            )}
                          </tr>
                        )
                      })}
                    </tbody>
                  </Table>
                </Card.Body>
              </Card>

              {anomalies && anomalies.n_anomalies > 0 && (
                <Card className="mb-4 border-warning">
                  <Card.Body>
                    <div className="d-flex justify-content-between align-items-center mb-3">
                      <h5 className="mb-0 text-warning">Detalle de anomalías</h5>
                      <Badge bg="warning" text="dark">{anomalies.n_anomalies}</Badge>
                    </div>
                    <Table hover responsive size="sm" className="mb-0">
                      <thead className="table-light">
                        <tr>
                          <th>Fecha</th>
                          <th>f0 Hz</th>
                          <th>Tensión tf</th>
                          <th>z Tensión</th>
                          <th>z f0</th>
                          <th>Razón</th>
                        </tr>
                      </thead>
                      <tbody>
                        {anomalies.items
                          .filter((a) => a.is_anomaly)
                          .map((a) => (
                            <tr key={a.analysis_result_id} className="table-warning">
                              <td>{formatDateTime(a.acquired_at)}</td>
                              <td>{a.f0_hz.toFixed(4)}</td>
                              <td>{a.tension_tf.toFixed(4)}</td>
                              <td>{a.zscore_tension.toFixed(2)}</td>
                              <td>{a.zscore_f0.toFixed(2)}</td>
                              <td>{a.anomaly_reason}</td>
                            </tr>
                          ))}
                      </tbody>
                    </Table>
                  </Card.Body>
                </Card>
              )}
            </>
          ) : (
            <Alert variant="secondary">No hay resultados para los filtros seleccionados.</Alert>
          )}

          {!!history.k_calibrations?.length && (
            <Card>
              <Card.Body>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <h5 className="mb-0">Calibraciones K del tirante</h5>
                  <Badge bg="secondary">{history.k_calibrations.length}</Badge>
                </div>
                <Table hover responsive size="sm" className="mb-0">
                  <thead className="table-light">
                    <tr>
                      <th>K</th>
                      <th>Desde</th>
                      <th>Hasta</th>
                      <th>Algoritmo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.k_calibrations.map((calibration) => (
                      <tr key={calibration.id}>
                        <td>{calibration.k_value.toFixed(4)}</td>
                        <td>{formatDateTime(calibration.valid_from)}</td>
                        <td>{formatDateTime(calibration.valid_to)}</td>
                        <td>{calibration.algorithm_version}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          )}
        </>
      )}
    </>
  )
}
