import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner, Table } from 'react-bootstrap'
import api from '../lib/apiClient'
import { apiErrorMessage, formatDateTime, fromDateTimeLocalInput, numberOrUndefined, toDateTimeLocalInput } from '../lib/utils'
import { Acquisition, Bridge, Cable, RawPreviewResponse, Sensor } from '../types/api'

type MappingRow = {
  csv_column_name: string
  sensor_id: string
  cable_id: string
  height_m: string
  multichannel_intentional: boolean
}

type SensorFormState = {
  sensor_type: string
  serial_or_asset_id: string
  unit: string
  notas: string
}

const emptySensorForm = (): SensorFormState => ({
  sensor_type: 'acc',
  serial_or_asset_id: '',
  unit: 'g',
  notas: '',
})

export default function AdquisicionesPage() {
  const [bridges, setBridges] = useState<Bridge[]>([])
  const [cables, setCables] = useState<Cable[]>([])
  const [sensors, setSensors] = useState<Sensor[]>([])
  const [acquisitions, setAcquisitions] = useState<Acquisition[]>([])
  const [selectedBridgeId, setSelectedBridgeId] = useState('')
  const [selectedAcquisitionId, setSelectedAcquisitionId] = useState('')
  const [acquiredAt, setAcquiredAt] = useState(toDateTimeLocalInput(new Date().toISOString()))
  const [samplingRate, setSamplingRate] = useState('')
  const [notes, setNotes] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [dataStartMarker, setDataStartMarker] = useState('DATA_START')
  const [headerRowOverride, setHeaderRowOverride] = useState('')
  const [rawPreview, setRawPreview] = useState<RawPreviewResponse | null>(null)
  const [mappingRows, setMappingRows] = useState<MappingRow[]>([])
  const [sensorForm, setSensorForm] = useState<SensorFormState>(emptySensorForm())
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [normalizeResponse, setNormalizeResponse] = useState<any>(null)

  const visibleBridgeId = selectedAcquisitionId
    ? String(acquisitions.find((item) => String(item.id) === selectedAcquisitionId)?.bridge_id || '')
    : selectedBridgeId

  const availableCables = useMemo(
    () => cables.filter((cable) => String(cable.bridge_id) === visibleBridgeId),
    [cables, visibleBridgeId],
  )

  useEffect(() => {
    loadContext()
  }, [])

  async function loadContext() {
    setLoading(true)
    try {
      const [bridgesRes, cablesRes, sensorsRes, acquisitionsRes] = await Promise.all([
        api.get('/bridges'),
        api.get('/cables'),
        api.get('/sensors'),
        api.get('/acquisitions'),
      ])
      setBridges(bridgesRes.data)
      setCables(cablesRes.data)
      setSensors(sensorsRes.data)
      setAcquisitions(acquisitionsRes.data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el contexto de adquisiciones'))
    } finally {
      setLoading(false)
    }
  }

  function resetMessages() {
    setError('')
    setSuccess('')
  }

  function buildMappingRows(headers: string[], previousRows: MappingRow[] = []) {
    const previousByName = new Map(previousRows.map((row) => [row.csv_column_name, row]))
    return headers
      .filter((header) => header && !['time', 'time_s', 'timestamp'].includes(header.toLowerCase()))
      .map((header) => previousByName.get(header) || {
        csv_column_name: header,
        sensor_id: '',
        cable_id: '',
        height_m: '',
        multichannel_intentional: false,
      })
  }

  async function ensureAcquisition() {
    if (selectedAcquisitionId) return Number(selectedAcquisitionId)
    if (!selectedBridgeId) throw new Error('Selecciona un puente o una adquisición existente')
    if (!samplingRate) throw new Error('Define la frecuencia de muestreo antes de crear la adquisición')

    const payload = {
      bridge_id: Number(selectedBridgeId),
      acquired_at: fromDateTimeLocalInput(acquiredAt),
      Fs_Hz: Number(samplingRate),
      notes: notes || undefined,
    }
    const { data } = await api.post('/acquisitions', payload)
    await loadContext()
    setSelectedAcquisitionId(String(data.id))
    setSuccess(`Adquisición ${data.id} creada`)
    return data.id as number
  }

  async function loadRawPreview(acquisitionId: number, rawFileId: number) {
    const params: Record<string, any> = {
      raw_file_id: rawFileId,
      data_start_marker: dataStartMarker || 'DATA_START',
    }
    if (headerRowOverride) params.header_row_override = Number(headerRowOverride)
    const { data } = await api.get(`/acquisitions/${acquisitionId}/raw-preview`, { params })
    setRawPreview(data)
    setMappingRows((prev) => buildMappingRows(data.headers || [], prev))
    return data as RawPreviewResponse
  }

  async function handleSaveRaw() {
    if (!file) {
      setError('Selecciona un archivo CSV para continuar')
      return
    }
    resetMessages()
    setSubmitting(true)
    setNormalizeResponse(null)
    try {
      const acquisitionId = await ensureAcquisition()
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await api.post(`/acquisitions/${acquisitionId}/raw-upload`, formData, {
        params: { parser_version: 'v1' },
      })
      await loadRawPreview(acquisitionId, data.id)
      setSuccess(`Raw guardado como versión ${data.version_no}`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo guardar el raw'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleReloadHeaders() {
    if (!selectedAcquisitionId || !rawPreview) {
      setError('Primero guarda un raw para poder releer cabeceras')
      return
    }
    resetMessages()
    setSubmitting(true)
    try {
      const data = await loadRawPreview(Number(selectedAcquisitionId), rawPreview.raw_file_id)
      setSuccess(`Cabeceras detectadas en la fila ${data.header_row_index ?? 'automática'}`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudieron releer las cabeceras'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCreateSensor(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      await api.post('/sensors', {
        sensor_type: sensorForm.sensor_type,
        serial_or_asset_id: sensorForm.serial_or_asset_id,
        unit: sensorForm.unit,
        notas: sensorForm.notas || undefined,
      })
      const { data } = await api.get('/sensors')
      setSensors(data)
      setSensorForm(emptySensorForm())
      setSuccess('Sensor creado')
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo crear el sensor'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleNormalize() {
    if (!selectedAcquisitionId || !rawPreview) {
      setError('Primero guarda y previsualiza un raw')
      return
    }
    const incomplete = mappingRows.find((row) => !row.sensor_id || !row.cable_id || !row.height_m)
    if (incomplete) {
      setError(`Completa sensor, tirante y altura para ${incomplete.csv_column_name}`)
      return
    }

    resetMessages()
    setSubmitting(true)
    try {
      const params: Record<string, any> = {
        parser_version: 'v1',
        raw_file_id: rawPreview.raw_file_id,
        data_start_marker: dataStartMarker || 'DATA_START',
      }
      if (headerRowOverride) params.header_row_override = Number(headerRowOverride)

      const payload = mappingRows.map((row) => ({
        csv_column_name: row.csv_column_name,
        sensor_id: Number(row.sensor_id),
        cable_id: Number(row.cable_id),
        height_m: Number(row.height_m),
        multichannel_intentional: row.multichannel_intentional,
      }))

      const { data } = await api.post(`/acquisitions/${selectedAcquisitionId}/normalize`, payload, { params })
      setNormalizeResponse(data)
      setSuccess('Normalización generada')
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo generar el normalizado'))
    } finally {
      setSubmitting(false)
    }
  }

  function updateMappingRow(index: number, field: keyof MappingRow, value: string | boolean) {
    setMappingRows((rows) =>
      rows.map((row, rowIndex) => (rowIndex === index ? { ...row, [field]: value } : row)),
    )
  }

  function handleAcquisitionSelection(acquisitionId: string) {
    setSelectedAcquisitionId(acquisitionId)
    if (!acquisitionId) return
    const acquisition = acquisitions.find((item) => String(item.id) === acquisitionId)
    if (!acquisition) return
    setSelectedBridgeId(String(acquisition.bridge_id))
    setAcquiredAt(toDateTimeLocalInput(acquisition.acquired_at))
    setSamplingRate(String(acquisition.Fs_Hz))
    setNotes(acquisition.notes || '')
    setRawPreview(null)
    setMappingRows([])
    setNormalizeResponse(null)
  }

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <Spinner size="sm" />
        <span>Cargando adquisiciones…</span>
      </div>
    )
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="fw-bold mb-1">Adquisiciones</h4>
          <p className="text-muted mb-0">Alta de campaña, carga de raw y normalización</p>
        </div>
        <Button variant="outline-secondary" onClick={loadContext} disabled={submitting}>
          Recargar
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      <Row className="g-4">
        <Col xl={8}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Campaña + Raw</h5>
                  <small className="text-muted">Selecciona una adquisición existente o crea una nueva al guardar el archivo</small>
                </div>
                <Badge bg="secondary">{acquisitions.length}</Badge>
              </div>

              <Row className="g-3 mb-3">
                <Col md={6}>
                  <Form.Label>Adquisición existente</Form.Label>
                  <Form.Select value={selectedAcquisitionId} onChange={(event) => handleAcquisitionSelection(event.target.value)}>
                    <option value="">Crear nueva…</option>
                    {acquisitions.map((acquisition) => (
                      <option key={acquisition.id} value={acquisition.id}>
                        #{acquisition.id} · {formatDateTime(acquisition.acquired_at)}
                      </option>
                    ))}
                  </Form.Select>
                </Col>
                <Col md={6}>
                  <Form.Label>Puente</Form.Label>
                  <Form.Select
                    value={selectedBridgeId}
                    onChange={(event) => setSelectedBridgeId(event.target.value)}
                    disabled={!!selectedAcquisitionId}
                  >
                    <option value="">Seleccionar…</option>
                    {bridges.map((bridge) => (
                      <option key={bridge.id} value={bridge.id}>
                        {bridge.nombre}
                      </option>
                    ))}
                  </Form.Select>
                </Col>
                <Col md={4}>
                  <Form.Label>Fecha y hora</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    value={acquiredAt}
                    onChange={(event) => setAcquiredAt(event.target.value)}
                    disabled={!!selectedAcquisitionId}
                  />
                </Col>
                <Col md={4}>
                  <Form.Label>Fs Hz</Form.Label>
                  <Form.Control
                    type="number"
                    step="any"
                    value={samplingRate}
                    onChange={(event) => setSamplingRate(event.target.value)}
                    disabled={!!selectedAcquisitionId}
                  />
                </Col>
                <Col md={4}>
                  <Form.Label>Notas</Form.Label>
                  <Form.Control
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    disabled={!!selectedAcquisitionId}
                  />
                </Col>
                <Col md={12}>
                  <Form.Label>Archivo raw CSV</Form.Label>
                  <Form.Control
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event: ChangeEvent<HTMLInputElement>) => setFile(event.target.files?.[0] || null)}
                  />
                </Col>
                <Col md={5}>
                  <Form.Label>Marcador inicio datos</Form.Label>
                  <Form.Control value={dataStartMarker} onChange={(event) => setDataStartMarker(event.target.value)} />
                </Col>
                <Col md={3}>
                  <Form.Label>Fila cabecera manual</Form.Label>
                  <Form.Control
                    type="number"
                    min={0}
                    value={headerRowOverride}
                    onChange={(event) => setHeaderRowOverride(event.target.value)}
                  />
                </Col>
                <Col md={4} className="d-flex align-items-end gap-2">
                  <Button onClick={handleSaveRaw} disabled={submitting || !file}>
                    Guardar raw
                  </Button>
                  <Button variant="outline-secondary" onClick={handleReloadHeaders} disabled={submitting || !rawPreview}>
                    Releer cabeceras
                  </Button>
                </Col>
              </Row>

              {rawPreview && (
                <Alert variant="light" className="border">
                  <div className="fw-semibold mb-1">Raw listo para mapear</div>
                  <div>Archivo: {rawPreview.original_filename}</div>
                  <div>Versión: {rawPreview.version_no}</div>
                  <div>Fila cabecera: {rawPreview.header_row_index ?? 'detección automática'}</div>
                  <div>Cabeceras: {rawPreview.headers.join(', ') || 'sin datos'}</div>
                </Alert>
              )}
            </Card.Body>
          </Card>
        </Col>

        <Col xl={4}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Sensor Rápido</h5>
                  <small className="text-muted">Alta mínima para habilitar el mapeo</small>
                </div>
                <Badge bg="secondary">{sensors.length}</Badge>
              </div>

              <Form onSubmit={handleCreateSensor}>
                <Row className="g-3">
                  <Col md={12}>
                    <Form.Label>Tipo</Form.Label>
                    <Form.Control
                      value={sensorForm.sensor_type}
                      onChange={(event) => setSensorForm((prev) => ({ ...prev, sensor_type: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Serial / Asset</Form.Label>
                    <Form.Control
                      value={sensorForm.serial_or_asset_id}
                      onChange={(event) => setSensorForm((prev) => ({ ...prev, serial_or_asset_id: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Unidad</Form.Label>
                    <Form.Control
                      value={sensorForm.unit}
                      onChange={(event) => setSensorForm((prev) => ({ ...prev, unit: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={sensorForm.notas}
                      onChange={(event) => setSensorForm((prev) => ({ ...prev, notas: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting} className="w-100">
                      Crear sensor
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col xs={12}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Mapeo y Normalización</h5>
                  <small className="text-muted">Relaciona columnas del CSV con sensor y tirante</small>
                </div>
                <Button onClick={handleNormalize} disabled={submitting || !mappingRows.length}>
                  Generar normalizado
                </Button>
              </div>

              {!mappingRows.length ? (
                <Alert variant="secondary" className="mb-0">
                  Guarda un raw y detecta cabeceras para habilitar esta sección.
                </Alert>
              ) : (
                <>
                  <Table responsive hover size="sm">
                    <thead className="table-light">
                      <tr>
                        <th>Columna CSV</th>
                        <th>Sensor</th>
                        <th>Tirante</th>
                        <th>Altura m</th>
                        <th>Multicanal intencional</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mappingRows.map((row, index) => (
                        <tr key={row.csv_column_name}>
                          <td className="fw-semibold">{row.csv_column_name}</td>
                          <td>
                            <Form.Select
                              value={row.sensor_id}
                              onChange={(event) => updateMappingRow(index, 'sensor_id', event.target.value)}
                            >
                              <option value="">Seleccionar…</option>
                              {sensors.map((sensor) => (
                                <option key={sensor.id} value={sensor.id}>
                                  {sensor.serial_or_asset_id}
                                </option>
                              ))}
                            </Form.Select>
                          </td>
                          <td>
                            <Form.Select
                              value={row.cable_id}
                              onChange={(event) => updateMappingRow(index, 'cable_id', event.target.value)}
                            >
                              <option value="">Seleccionar…</option>
                              {availableCables.map((cable) => (
                                <option key={cable.id} value={cable.id}>
                                  {cable.nombre_en_puente}
                                </option>
                              ))}
                            </Form.Select>
                          </td>
                          <td>
                            <Form.Control
                              type="number"
                              step="any"
                              value={row.height_m}
                              onChange={(event) => updateMappingRow(index, 'height_m', event.target.value)}
                            />
                          </td>
                          <td className="text-center">
                            <Form.Check
                              checked={row.multichannel_intentional}
                              onChange={(event) => updateMappingRow(index, 'multichannel_intentional', event.target.checked)}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>

                  {normalizeResponse && (
                  <Alert variant="light" className="border mb-0">
                      <div className="fw-semibold mb-1">Normalización completada</div>
                      <div>Archivo normalizado ID: {normalizeResponse.normalized_file_id}</div>
                      <div>Canales creados: {normalizeResponse.channels_created}</div>
                      <div>Versión: {normalizeResponse.version_no}</div>
                    </Alert>
                  )}
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
                  <h5 className="mb-0">Adquisiciones recientes</h5>
                  <small className="text-muted">Referencia rápida para continuar el flujo</small>
                </div>
                <Badge bg="secondary">{acquisitions.length}</Badge>
              </div>

              <Table hover responsive size="sm">
                <thead className="table-light">
                  <tr>
                    <th>ID</th>
                    <th>Puente</th>
                    <th>Fecha</th>
                    <th>Fs</th>
                    <th className="text-end">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {acquisitions.map((acquisition) => (
                    <tr key={acquisition.id} className={String(acquisition.id) === selectedAcquisitionId ? 'table-primary' : ''}>
                      <td>{acquisition.id}</td>
                      <td>{bridges.find((bridge) => bridge.id === acquisition.bridge_id)?.nombre || acquisition.bridge_id}</td>
                      <td>{formatDateTime(acquisition.acquired_at)}</td>
                      <td>{acquisition.Fs_Hz}</td>
                      <td className="text-end">
                        <Button size="sm" variant="outline-secondary" onClick={() => handleAcquisitionSelection(String(acquisition.id))}>
                          Usar
                        </Button>
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
