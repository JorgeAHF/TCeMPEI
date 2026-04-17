import { FormEvent, useEffect, useMemo, useState } from 'react'
import type { Config, Data, Layout } from 'plotly.js'
import Plot from 'react-plotly.js'
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner, Table } from 'react-bootstrap'
import api from '../lib/apiClient'
import { apiErrorMessage, formatDateTime } from '../lib/utils'
import { Acquisition, AnalysisPreviewResponse, AnalysisResult, AnalysisRun, Cable } from '../types/api'

type RunFormState = {
  acquisition_id: string
  algorithm_version: string
  notes: string
}

type PreviewFormState = {
  run_id: string
  cable_id: string
  csv_column_name: string
  segment_pct_start: string
  segment_pct_end: string
  nperseg: string
  noverlap_pct: string
  peak_threshold: string
  min_distance_hz: string
  n_harmonics: string
  f0_hint_hz: string
  f0_manual_hz: string
}

type ResultFormState = {
  analysis_run_id: string
  cable_id: string
  f0_hz: string
  df_hz: string
  snr_metric: string
  quality_flag: string
}

const emptyRunForm = (): RunFormState => ({
  acquisition_id: '',
  algorithm_version: 'v1.0',
  notes: '',
})

const emptyPreviewForm = (): PreviewFormState => ({
  run_id: '',
  cable_id: '',
  csv_column_name: '',
  segment_pct_start: '0',
  segment_pct_end: '100',
  nperseg: '2048',
  noverlap_pct: '50',
  peak_threshold: '0.2',
  min_distance_hz: '0.05',
  n_harmonics: '3',
  f0_hint_hz: '',
  f0_manual_hz: '',
})

const emptyResultForm = (): ResultFormState => ({
  analysis_run_id: '',
  cable_id: '',
  f0_hz: '',
  df_hz: '',
  snr_metric: '',
  quality_flag: 'ok',
})

const plotConfig: Partial<Config> = {
  responsive: true,
  displaylogo: false,
}

const plotLayout: Partial<Layout> = {
  autosize: true,
  margin: { l: 48, r: 24, t: 40, b: 42 },
}

export default function AnalisisPage() {
  const [acquisitions, setAcquisitions] = useState<Acquisition[]>([])
  const [runs, setRuns] = useState<AnalysisRun[]>([])
  const [cables, setCables] = useState<Cable[]>([])
  const [preview, setPreview] = useState<AnalysisPreviewResponse | null>(null)
  const [results, setResults] = useState<AnalysisResult[]>([])
  const [runForm, setRunForm] = useState<RunFormState>(emptyRunForm())
  const [previewForm, setPreviewForm] = useState<PreviewFormState>(emptyPreviewForm())
  const [resultForm, setResultForm] = useState<ResultFormState>(emptyResultForm())
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fullSignalData: Data[] = preview
    ? [
        {
          type: 'scatter',
          mode: 'lines',
          x: preview.signal_full.time_s,
          y: preview.signal_full.accel,
          line: { color: '#0d6efd' },
          name: 'Aceleracion',
        },
      ]
    : []

  const segmentSignalData: Data[] = preview
    ? [
        {
          type: 'scatter',
          mode: 'lines',
          x: preview.signal_segment.time_s,
          y: preview.signal_segment.accel,
          line: { color: '#198754' },
          name: 'Segmento',
        },
      ]
    : []

  const fftData: Data[] = preview
    ? [
        {
          type: 'scatter',
          mode: 'lines',
          x: preview.fft.freq_hz,
          y: preview.fft.amplitude,
          line: { color: '#fd7e14' },
          name: 'FFT',
        },
        {
          type: 'scatter',
          mode: 'markers',
          x: preview.candidate_peaks.map((peak) => peak.frequency_hz),
          y: preview.candidate_peaks.map((peak) => peak.amplitude),
          marker: { color: '#dc3545', size: 8 },
          name: 'Picos',
        },
      ]
    : []

  const psdData: Data[] = preview
    ? [
        {
          type: 'scatter',
          mode: 'lines',
          x: preview.psd.freq_hz,
          y: preview.psd.power,
          line: { color: '#6f42c1' },
          name: 'PSD',
        },
      ]
    : []

  const selectedRun = runs.find((run) => String(run.id) === previewForm.run_id) || null
  const selectedAcquisition = acquisitions.find((acquisition) => acquisition.id === selectedRun?.acquisition_id) || null
  const cablesForRun = useMemo(
    () => cables.filter((cable) => cable.bridge_id === selectedAcquisition?.bridge_id),
    [cables, selectedAcquisition],
  )

  useEffect(() => {
    loadContext()
  }, [])

  useEffect(() => {
    if (!previewForm.run_id) {
      setResults([])
      return
    }
    setResultForm((prev) => ({ ...prev, analysis_run_id: previewForm.run_id }))
    loadResults(Number(previewForm.run_id))
  }, [previewForm.run_id])

  async function loadContext() {
    setLoading(true)
    try {
      const [acquisitionsRes, runsRes, cablesRes] = await Promise.all([
        api.get('/acquisitions'),
        api.get('/analysis-runs'),
        api.get('/cables'),
      ])
      setAcquisitions(acquisitionsRes.data)
      setRuns(runsRes.data)
      setCables(cablesRes.data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el módulo de análisis'))
    } finally {
      setLoading(false)
    }
  }

  async function loadResults(runId: number) {
    try {
      const { data } = await api.get(`/analysis-runs/${runId}/results`)
      setResults(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudieron cargar los resultados del run'))
    }
  }

  function resetMessages() {
    setError('')
    setSuccess('')
  }

  async function handleRunSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const { data } = await api.post('/analysis-runs', {
        acquisition_id: Number(runForm.acquisition_id),
        algorithm_version: runForm.algorithm_version,
        notes: runForm.notes || undefined,
      })
      await loadContext()
      setPreview(null)
      setPreviewForm((prev) => ({ ...prev, run_id: String(data.id), cable_id: '' }))
      setResultForm((prev) => ({ ...prev, analysis_run_id: String(data.id) }))
      setSuccess(`Run ${data.id} creado`)
      setRunForm(emptyRunForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo crear el run de análisis'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handlePreviewSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const payload = {
        cable_id: Number(previewForm.cable_id),
        csv_column_name: previewForm.csv_column_name || undefined,
        segment_pct_start: Number(previewForm.segment_pct_start),
        segment_pct_end: Number(previewForm.segment_pct_end),
        nperseg: Number(previewForm.nperseg),
        noverlap_pct: Number(previewForm.noverlap_pct),
        peak_threshold: Number(previewForm.peak_threshold),
        min_distance_hz: Number(previewForm.min_distance_hz),
        n_harmonics: Number(previewForm.n_harmonics),
        f0_hint_hz: previewForm.f0_hint_hz ? Number(previewForm.f0_hint_hz) : undefined,
        f0_manual_hz: previewForm.f0_manual_hz ? Number(previewForm.f0_manual_hz) : undefined,
      }
      const { data } = await api.post(`/analysis-runs/${previewForm.run_id}/preview`, payload)
      setPreview(data)
      setResultForm((prev) => ({
        ...prev,
        analysis_run_id: previewForm.run_id,
        cable_id: String(previewForm.cable_id),
        f0_hz: String(data.f0_selected_hz),
        df_hz: String(data.df_hz),
        snr_metric: String(data.snr_metric),
      }))
      setSuccess('Preview generado')
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo generar el preview'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleResultSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      await api.post('/analysis-results', {
        analysis_run_id: Number(resultForm.analysis_run_id),
        cable_id: Number(resultForm.cable_id),
        f0_hz: Number(resultForm.f0_hz),
        harmonics_json: preview ? { harmonics: preview.harmonics } : {},
        df_hz: resultForm.df_hz ? Number(resultForm.df_hz) : undefined,
        snr_metric: resultForm.snr_metric ? Number(resultForm.snr_metric) : undefined,
        quality_flag: resultForm.quality_flag,
      })
      await loadResults(Number(resultForm.analysis_run_id))
      setSuccess('Resultado guardado')
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo guardar el resultado'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleApprove(resultId: number) {
    resetMessages()
    setSubmitting(true)
    try {
      await api.patch(`/analysis-results/${resultId}/approve`)
      await loadResults(Number(previewForm.run_id))
      setSuccess(`Resultado #${resultId} marcado como aprobado`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo aprobar el resultado'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleUnapprove(resultId: number) {
    resetMessages()
    setSubmitting(true)
    try {
      await api.patch(`/analysis-results/${resultId}/unapprove`)
      await loadResults(Number(previewForm.run_id))
      setSuccess(`Aprobación de resultado #${resultId} revocada`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo revocar la aprobación'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <Spinner size="sm" />
        <span>Cargando análisis…</span>
      </div>
    )
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="fw-bold mb-1">Análisis</h4>
          <p className="text-muted mb-0">Runs, preview interactivo y registro de resultados</p>
        </div>
        <Button variant="outline-secondary" onClick={loadContext} disabled={submitting}>
          Recargar
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      <Row className="g-4">
        <Col xl={4}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">1. Crear run</h5>
                  <small className="text-muted">Punto de partida del análisis</small>
                </div>
                <Badge bg="secondary">{runs.length}</Badge>
              </div>

              <Form onSubmit={handleRunSubmit}>
                <Row className="g-3">
                  <Col md={12}>
                    <Form.Label>Adquisición</Form.Label>
                    <Form.Select
                      value={runForm.acquisition_id}
                      onChange={(event) => setRunForm((prev) => ({ ...prev, acquisition_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {acquisitions.map((acquisition) => (
                        <option key={acquisition.id} value={acquisition.id}>
                          #{acquisition.id} · {formatDateTime(acquisition.acquired_at)}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={12}>
                    <Form.Label>Versión algoritmo</Form.Label>
                    <Form.Control
                      value={runForm.algorithm_version}
                      onChange={(event) => setRunForm((prev) => ({ ...prev, algorithm_version: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={runForm.notes}
                      onChange={(event) => setRunForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting}>
                      Crear run
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={8}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">2. Preview interactivo</h5>
                  <small className="text-muted">Selecciona el run y ajusta parámetros FFT/PSD</small>
                </div>
                <Badge bg="secondary">{preview ? 'listo' : 'pendiente'}</Badge>
              </div>

              <Form onSubmit={handlePreviewSubmit}>
                <Row className="g-3">
                  <Col md={4}>
                    <Form.Label>Run</Form.Label>
                    <Form.Select
                      value={previewForm.run_id}
                      onChange={(event) => {
                        const runId = event.target.value
                        setPreview(null)
                        setPreviewForm((prev) => ({ ...prev, run_id: runId, cable_id: '' }))
                        setResultForm((prev) => ({ ...prev, analysis_run_id: runId, cable_id: '' }))
                      }}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {runs.map((run) => (
                        <option key={run.id} value={run.id}>
                          #{run.id} · acq {run.acquisition_id}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Tirante</Form.Label>
                    <Form.Select
                      value={previewForm.cable_id}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, cable_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {cablesForRun.map((cable) => (
                        <option key={cable.id} value={cable.id}>
                          {cable.nombre_en_puente}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Columna CSV</Form.Label>
                    <Form.Control
                      value={previewForm.csv_column_name}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, csv_column_name: event.target.value }))}
                      placeholder="Opcional"
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Seg. inicio %</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.segment_pct_start}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, segment_pct_start: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Seg. fin %</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.segment_pct_end}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, segment_pct_end: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Nperseg</Form.Label>
                    <Form.Control
                      type="number"
                      value={previewForm.nperseg}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, nperseg: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Noverlap %</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.noverlap_pct}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, noverlap_pct: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Peak threshold</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.peak_threshold}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, peak_threshold: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Distancia mínima Hz</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.min_distance_hz}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, min_distance_hz: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Armónicos</Form.Label>
                    <Form.Control
                      type="number"
                      value={previewForm.n_harmonics}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, n_harmonics: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>f0 hint Hz</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.f0_hint_hz}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, f0_hint_hz: event.target.value }))}
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>f0 manual Hz</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={previewForm.f0_manual_hz}
                      onChange={(event) => setPreviewForm((prev) => ({ ...prev, f0_manual_hz: event.target.value }))}
                      placeholder="Opcional"
                    />
                  </Col>
                  <Col md={6} className="d-flex align-items-end">
                    <Button type="submit" disabled={submitting}>
                      Generar preview
                    </Button>
                  </Col>
                </Row>
              </Form>

              {preview && (
                <>
                  <Alert variant="light" className="border mt-3">
                    <div className="fw-semibold mb-1">{preview.channel_name}</div>
                    <div>f0 sugerida: {preview.f0_suggested_hz.toFixed(4)} Hz</div>
                    <div>f0 seleccionada: {preview.f0_selected_hz.toFixed(4)} Hz</div>
                    <div>SNR: {preview.snr_metric.toFixed(2)}</div>
                    <div>df: {preview.df_hz.toFixed(4)} Hz</div>
                  </Alert>

                  <Row className="g-3">
                    <Col xl={6}>
                      <Card className="border">
                        <Card.Body>
                          <Plot
                            data={fullSignalData}
                            layout={{
                              ...plotLayout,
                              title: { text: 'Acelerograma completo' },
                              xaxis: { title: { text: 't [s]' } },
                              yaxis: { title: { text: 'Aceleracion' } },
                            }}
                            config={plotConfig}
                            style={{ width: '100%', height: 320 }}
                            useResizeHandler
                          />
                        </Card.Body>
                      </Card>
                    </Col>
                    <Col xl={6}>
                      <Card className="border">
                        <Card.Body>
                          <Plot
                            data={segmentSignalData}
                            layout={{
                              ...plotLayout,
                              title: { text: 'Acelerograma segmento' },
                              xaxis: { title: { text: 't [s]' } },
                              yaxis: { title: { text: 'Aceleracion' } },
                            }}
                            config={plotConfig}
                            style={{ width: '100%', height: 320 }}
                            useResizeHandler
                          />
                        </Card.Body>
                      </Card>
                    </Col>
                    <Col xl={6}>
                      <Card className="border">
                        <Card.Body>
                          <Plot
                            data={fftData}
                            layout={{
                              ...plotLayout,
                              title: { text: 'FFT' },
                              xaxis: { title: { text: 'f [Hz]' } },
                              yaxis: { title: { text: 'Amplitud' } },
                            }}
                            config={plotConfig}
                            style={{ width: '100%', height: 320 }}
                            useResizeHandler
                          />
                        </Card.Body>
                      </Card>
                    </Col>
                    <Col xl={6}>
                      <Card className="border">
                        <Card.Body>
                          <Plot
                            data={psdData}
                            layout={{
                              ...plotLayout,
                              title: { text: 'PSD Welch' },
                              xaxis: { title: { text: 'f [Hz]' } },
                              yaxis: { title: { text: 'Potencia' } },
                            }}
                            config={plotConfig}
                            style={{ width: '100%', height: 320 }}
                            useResizeHandler
                          />
                        </Card.Body>
                      </Card>
                    </Col>
                  </Row>
                </>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col xs={12}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">3. Guardar resultado</h5>
                  <small className="text-muted">Registra el valor final de f0 y la tensión calculada</small>
                </div>
                <Badge bg="secondary">{results.length}</Badge>
              </div>

              <Form onSubmit={handleResultSubmit}>
                <Row className="g-3">
                  <Col md={3}>
                    <Form.Label>Run</Form.Label>
                    <Form.Control value={resultForm.analysis_run_id} readOnly />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Tirante</Form.Label>
                    <Form.Select
                      value={resultForm.cable_id}
                      onChange={(event) => setResultForm((prev) => ({ ...prev, cable_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {cablesForRun.map((cable) => (
                        <option key={cable.id} value={cable.id}>
                          {cable.nombre_en_puente}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={2}>
                    <Form.Label>f0 Hz</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={resultForm.f0_hz}
                      onChange={(event) => setResultForm((prev) => ({ ...prev, f0_hz: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={2}>
                    <Form.Label>df Hz</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={resultForm.df_hz}
                      onChange={(event) => setResultForm((prev) => ({ ...prev, df_hz: event.target.value }))}
                    />
                  </Col>
                  <Col md={2}>
                    <Form.Label>SNR</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={resultForm.snr_metric}
                      onChange={(event) => setResultForm((prev) => ({ ...prev, snr_metric: event.target.value }))}
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Quality flag</Form.Label>
                    <Form.Select
                      value={resultForm.quality_flag}
                      onChange={(event) => setResultForm((prev) => ({ ...prev, quality_flag: event.target.value }))}
                    >
                      <option value="ok">ok</option>
                      <option value="doubtful">doubtful</option>
                      <option value="bad">bad</option>
                    </Form.Select>
                  </Col>
                  <Col md={9} className="d-flex align-items-end">
                    <Button type="submit" disabled={submitting || !resultForm.analysis_run_id || !resultForm.cable_id}>
                      Guardar resultado
                    </Button>
                  </Col>
                </Row>
              </Form>

              {!!preview?.harmonics.length && (
                <Table hover responsive size="sm" className="mt-4">
                  <thead className="table-light">
                    <tr>
                      <th>Orden</th>
                      <th>Objetivo Hz</th>
                      <th>Frecuencia Hz</th>
                      <th>Amplitud</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.harmonics.map((harmonic) => (
                      <tr key={harmonic.order}>
                        <td>{harmonic.order}</td>
                        <td>{harmonic.target_frequency_hz.toFixed(4)}</td>
                        <td>{harmonic.frequency_hz.toFixed(4)}</td>
                        <td>{harmonic.amplitude.toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}

              <Table hover responsive size="sm" className="mt-4 mb-0">
                <thead className="table-light">
                  <tr>
                    <th>ID</th>
                    <th>Tirante</th>
                    <th>f0 Hz</th>
                    <th>Tensión tf</th>
                    <th>K usado</th>
                    <th>Calidad</th>
                    <th>Estado</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result) => (
                    <tr key={result.id} className={result.is_approved ? 'table-success' : undefined}>
                      <td>{result.id}</td>
                      <td>{cables.find((cable) => cable.id === result.cable_id)?.nombre_en_puente || result.cable_id}</td>
                      <td>{result.f0_hz.toFixed(4)}</td>
                      <td>{result.tension_tf.toFixed(4)}</td>
                      <td>{result.k_used_value.toFixed(4)}</td>
                      <td>{result.quality_flag}</td>
                      <td>
                        {result.is_approved ? (
                          <Badge bg="success">Aprobado</Badge>
                        ) : (
                          <Badge bg="secondary">Borrador</Badge>
                        )}
                      </td>
                      <td>
                        {result.is_approved ? (
                          <Button
                            size="sm"
                            variant="outline-secondary"
                            disabled={submitting}
                            onClick={() => handleUnapprove(result.id)}
                          >
                            Revocar
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline-success"
                            disabled={submitting}
                            onClick={() => handleApprove(result.id)}
                          >
                            Aprobar
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  )
}
