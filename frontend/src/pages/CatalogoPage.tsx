import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner, Table } from 'react-bootstrap'
import api from '../lib/apiClient'
import { apiErrorMessage, formatDateTime, fromDateTimeLocalInput, numberOrUndefined, toDateTimeLocalInput } from '../lib/utils'
import { Bridge, Cable, CableStateVersion, StrandType } from '../types/api'

type BridgeFormState = {
  id?: number
  nombre: string
  clave_interna: string
  num_tirantes: string
  notas: string
}

type CableFormState = {
  id?: number
  nombre_en_puente: string
  notas: string
}

type StrandFormState = {
  id?: number
  nombre: string
  diametro_mm: string
  area_mm2: string
  E_MPa: string
  Fu_default: string
  mu_por_toron_kg_m: string
  notas: string
}

type CableStateFormState = {
  valid_from: string
  valid_to: string
  length_effective_m: string
  strands_total: string
  strands_active: string
  strand_type_id: string
  diametro_mm: string
  area_mm2: string
  E_MPa: string
  mu_total_kg_m: string
  mu_active_basis_kg_m: string
  design_tension_tf: string
  Fu_override: string
  antivandalic_length_m: string
  notes: string
}

const emptyBridgeForm = (): BridgeFormState => ({
  nombre: '',
  clave_interna: '',
  num_tirantes: '',
  notas: '',
})

const emptyCableForm = (): CableFormState => ({
  nombre_en_puente: '',
  notas: '',
})

const emptyStrandForm = (): StrandFormState => ({
  nombre: '',
  diametro_mm: '',
  area_mm2: '',
  E_MPa: '',
  Fu_default: '',
  mu_por_toron_kg_m: '',
  notas: '',
})

const emptyCableStateForm = (): CableStateFormState => ({
  valid_from: toDateTimeLocalInput(new Date().toISOString()),
  valid_to: '',
  length_effective_m: '',
  strands_total: '',
  strands_active: '',
  strand_type_id: '',
  diametro_mm: '',
  area_mm2: '',
  E_MPa: '',
  mu_total_kg_m: '',
  mu_active_basis_kg_m: '',
  design_tension_tf: '',
  Fu_override: '',
  antivandalic_length_m: '',
  notes: '',
})

export default function CatalogoPage() {
  const [bridges, setBridges] = useState<Bridge[]>([])
  const [cables, setCables] = useState<Cable[]>([])
  const [strandTypes, setStrandTypes] = useState<StrandType[]>([])
  const [cableStates, setCableStates] = useState<CableStateVersion[]>([])
  const [selectedBridgeId, setSelectedBridgeId] = useState<number | null>(null)
  const [selectedCableId, setSelectedCableId] = useState<number | null>(null)
  const [bridgeForm, setBridgeForm] = useState<BridgeFormState>(emptyBridgeForm())
  const [cableForm, setCableForm] = useState<CableFormState>(emptyCableForm())
  const [strandForm, setStrandForm] = useState<StrandFormState>(emptyStrandForm())
  const [cableStateForm, setCableStateForm] = useState<CableStateFormState>(emptyCableStateForm())
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const selectedBridge = bridges.find((bridge) => bridge.id === selectedBridgeId) || null
  const selectedCable = cables.find((cable) => cable.id === selectedCableId) || null
  const cablesForBridge = useMemo(
    () => cables.filter((cable) => cable.bridge_id === selectedBridgeId),
    [cables, selectedBridgeId],
  )

  useEffect(() => {
    loadCatalog()
  }, [])

  useEffect(() => {
    if (!selectedCableId) {
      setCableStates([])
      return
    }
    loadCableStates(selectedCableId)
  }, [selectedCableId])

  async function loadCatalog() {
    setLoading(true)
    try {
      const [bridgesRes, cablesRes, strandsRes] = await Promise.all([
        api.get('/bridges'),
        api.get('/cables'),
        api.get('/strand-types'),
      ])
      const nextBridges = bridgesRes.data as Bridge[]
      const nextCables = cablesRes.data as Cable[]
      const nextStrands = strandsRes.data as StrandType[]
      setBridges(nextBridges)
      setCables(nextCables)
      setStrandTypes(nextStrands)

      if (selectedBridgeId && !nextBridges.some((bridge) => bridge.id === selectedBridgeId)) {
        setSelectedBridgeId(null)
        setSelectedCableId(null)
      }
      if (selectedCableId && !nextCables.some((cable) => cable.id === selectedCableId)) {
        setSelectedCableId(null)
      }
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el catálogo'))
    } finally {
      setLoading(false)
    }
  }

  async function loadCableStates(cableId: number) {
    try {
      const { data } = await api.get(`/cables/${cableId}/states`)
      setCableStates(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el histórico de estados'))
    }
  }

  function resetMessages() {
    setError('')
    setSuccess('')
  }

  function syncCableStateWithStrand(next: CableStateFormState) {
    const strand = strandTypes.find((item) => String(item.id) === next.strand_type_id)
    if (!strand) return next

    const total = numberOrUndefined(next.strands_total) || 0
    const active = numberOrUndefined(next.strands_active) || 0

    return {
      ...next,
      diametro_mm: strand.diametro_mm ? String(strand.diametro_mm) : next.diametro_mm,
      area_mm2: strand.area_mm2 ? String(strand.area_mm2) : next.area_mm2,
      E_MPa: strand.E_MPa ? String(strand.E_MPa) : next.E_MPa,
      mu_total_kg_m: total > 0 ? String((strand.mu_por_toron_kg_m * total).toFixed(3)) : next.mu_total_kg_m,
      mu_active_basis_kg_m: active > 0 ? String((strand.mu_por_toron_kg_m * active).toFixed(3)) : next.mu_active_basis_kg_m,
    }
  }

  async function handleBridgeSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const payload = {
        nombre: bridgeForm.nombre,
        clave_interna: bridgeForm.clave_interna || undefined,
        num_tirantes: numberOrUndefined(bridgeForm.num_tirantes),
        notas: bridgeForm.notas || undefined,
      }
      const { data } = bridgeForm.id
        ? await api.put(`/bridges/${bridgeForm.id}`, payload)
        : await api.post('/bridges', payload)

      await loadCatalog()
      setSelectedBridgeId(data.id)
      setSuccess(bridgeForm.id ? 'Puente actualizado' : 'Puente creado')
      setBridgeForm(emptyBridgeForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo guardar el puente'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleBridgeDelete(bridgeId: number) {
    resetMessages()
    setSubmitting(true)
    try {
      await api.delete(`/bridges/${bridgeId}`)
      await loadCatalog()
      if (selectedBridgeId === bridgeId) {
        setSelectedBridgeId(null)
        setSelectedCableId(null)
        setCableStates([])
      }
      setSuccess(`Puente ${bridgeId} eliminado`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo eliminar el puente'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCableSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedBridgeId) {
      setError('Selecciona un puente antes de guardar tirantes')
      return
    }
    resetMessages()
    setSubmitting(true)
    try {
      const payload = {
        bridge_id: selectedBridgeId,
        nombre_en_puente: cableForm.nombre_en_puente,
        notas: cableForm.notas || undefined,
      }
      const { data } = cableForm.id
        ? await api.put(`/cables/${cableForm.id}`, payload)
        : await api.post('/cables', payload)

      await loadCatalog()
      setSelectedCableId(data.id)
      setSuccess(cableForm.id ? 'Tirante actualizado' : 'Tirante creado')
      setCableForm(emptyCableForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo guardar el tirante'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCableDelete(cableId: number) {
    resetMessages()
    setSubmitting(true)
    try {
      await api.delete(`/cables/${cableId}`)
      await loadCatalog()
      if (selectedCableId === cableId) {
        setSelectedCableId(null)
        setCableStates([])
      }
      setSuccess(`Tirante ${cableId} eliminado`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo eliminar el tirante'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStrandSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const payload = {
        nombre: strandForm.nombre,
        diametro_mm: Number(strandForm.diametro_mm),
        area_mm2: Number(strandForm.area_mm2),
        E_MPa: Number(strandForm.E_MPa),
        Fu_default: Number(strandForm.Fu_default),
        mu_por_toron_kg_m: Number(strandForm.mu_por_toron_kg_m),
        notas: strandForm.notas || undefined,
      }
      await (strandForm.id
        ? api.put(`/strand-types/${strandForm.id}`, payload)
        : api.post('/strand-types', payload))

      await loadCatalog()
      setSuccess(strandForm.id ? 'Tipo de torón actualizado' : 'Tipo de torón creado')
      setStrandForm(emptyStrandForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo guardar el tipo de torón'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleStrandDelete(strandId: number) {
    resetMessages()
    setSubmitting(true)
    try {
      await api.delete(`/strand-types/${strandId}`)
      await loadCatalog()
      setSuccess(`Tipo de torón ${strandId} eliminado`)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo eliminar el tipo de torón'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCableStateSubmit(event: FormEvent) {
    event.preventDefault()
    if (!selectedCableId) {
      setError('Selecciona un tirante antes de registrar un estado')
      return
    }
    resetMessages()
    setSubmitting(true)
    try {
      const strandsTotal = Number(cableStateForm.strands_total)
      const strandsActive = Number(cableStateForm.strands_active)
      const payload = {
        cable_id: selectedCableId,
        valid_from: fromDateTimeLocalInput(cableStateForm.valid_from),
        valid_to: fromDateTimeLocalInput(cableStateForm.valid_to),
        length_effective_m: Number(cableStateForm.length_effective_m),
        length_total_m: Number(cableStateForm.length_effective_m),
        strands_total: strandsTotal,
        strands_active: strandsActive,
        strands_inactive: Math.max(0, strandsTotal - strandsActive),
        strand_type_id: Number(cableStateForm.strand_type_id),
        diametro_mm: Number(cableStateForm.diametro_mm),
        area_mm2: Number(cableStateForm.area_mm2),
        E_MPa: Number(cableStateForm.E_MPa),
        mu_total_kg_m: Number(cableStateForm.mu_total_kg_m),
        mu_active_basis_kg_m: Number(cableStateForm.mu_active_basis_kg_m),
        design_tension_tf: Number(cableStateForm.design_tension_tf),
        Fu_override: numberOrUndefined(cableStateForm.Fu_override),
        antivandalic_enabled: !!numberOrUndefined(cableStateForm.antivandalic_length_m),
        antivandalic_length_m: numberOrUndefined(cableStateForm.antivandalic_length_m),
        source: cableStateForm.notes || undefined,
        notes: cableStateForm.notes || undefined,
      }
      await api.post('/cable-states', payload)
      await loadCableStates(selectedCableId)
      setSuccess('Estado de tirante registrado')
      setCableStateForm(emptyCableStateForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo registrar el estado del tirante'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <Spinner size="sm" />
        <span>Cargando catálogo…</span>
      </div>
    )
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="fw-bold mb-1">Catálogo</h4>
          <p className="text-muted mb-0">Puentes, tirantes, tipos de torón y estados vigentes</p>
        </div>
        <Button variant="outline-secondary" onClick={loadCatalog} disabled={submitting}>
          Recargar
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      <Row className="g-4">
        <Col xl={6}>
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Puentes</h5>
                  <small className="text-muted">Crea o edita la base del puente</small>
                </div>
                <Badge bg="secondary">{bridges.length}</Badge>
              </div>

              <Form onSubmit={handleBridgeSubmit} className="mb-3">
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Nombre</Form.Label>
                    <Form.Control
                      value={bridgeForm.nombre}
                      onChange={(event) => setBridgeForm((prev) => ({ ...prev, nombre: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Clave interna</Form.Label>
                    <Form.Control
                      value={bridgeForm.clave_interna}
                      onChange={(event) => setBridgeForm((prev) => ({ ...prev, clave_interna: event.target.value }))}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>No. tirantes</Form.Label>
                    <Form.Control
                      type="number"
                      min={0}
                      value={bridgeForm.num_tirantes}
                      onChange={(event) => setBridgeForm((prev) => ({ ...prev, num_tirantes: event.target.value }))}
                    />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={bridgeForm.notas}
                      onChange={(event) => setBridgeForm((prev) => ({ ...prev, notas: event.target.value }))}
                    />
                  </Col>
                </Row>
                <div className="d-flex gap-2 mt-3">
                  <Button type="submit" disabled={submitting}>
                    {bridgeForm.id ? 'Actualizar puente' : 'Crear puente'}
                  </Button>
                  <Button variant="outline-secondary" onClick={() => setBridgeForm(emptyBridgeForm())} disabled={submitting}>
                    Limpiar
                  </Button>
                </div>
              </Form>

              <Table hover responsive size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Puente</th>
                    <th>Clave</th>
                    <th>Tirantes</th>
                    <th className="text-end">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {bridges.map((bridge) => (
                    <tr key={bridge.id} className={selectedBridgeId === bridge.id ? 'table-primary' : ''}>
                      <td>
                        <button
                          type="button"
                          className="btn btn-link btn-sm p-0 text-decoration-none"
                          onClick={() => {
                            setSelectedBridgeId(bridge.id)
                            setSelectedCableId(null)
                          }}
                        >
                          {bridge.nombre}
                        </button>
                      </td>
                      <td>{bridge.clave_interna || '—'}</td>
                      <td>{bridge.num_tirantes ?? '—'}</td>
                      <td className="text-end">
                        <Button
                          size="sm"
                          variant="outline-secondary"
                          className="me-2"
                          onClick={() => setBridgeForm({
                            id: bridge.id,
                            nombre: bridge.nombre,
                            clave_interna: bridge.clave_interna || '',
                            num_tirantes: bridge.num_tirantes ? String(bridge.num_tirantes) : '',
                            notas: bridge.notas || '',
                          })}
                        >
                          Editar
                        </Button>
                        <Button size="sm" variant="outline-danger" onClick={() => handleBridgeDelete(bridge.id)}>
                          Eliminar
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Tipos de Torón</h5>
                  <small className="text-muted">Propiedades base para estados de tirante</small>
                </div>
                <Badge bg="secondary">{strandTypes.length}</Badge>
              </div>

              <Form onSubmit={handleStrandSubmit} className="mb-3">
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Nombre</Form.Label>
                    <Form.Control
                      value={strandForm.nombre}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, nombre: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Diámetro mm</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={strandForm.diametro_mm}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, diametro_mm: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={3}>
                    <Form.Label>Área mm²</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={strandForm.area_mm2}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, area_mm2: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>E MPa</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={strandForm.E_MPa}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, E_MPa: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Fu default</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={strandForm.Fu_default}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, Fu_default: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Mu por torón</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={strandForm.mu_por_toron_kg_m}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, mu_por_toron_kg_m: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={strandForm.notas}
                      onChange={(event) => setStrandForm((prev) => ({ ...prev, notas: event.target.value }))}
                    />
                  </Col>
                </Row>
                <div className="d-flex gap-2 mt-3">
                  <Button type="submit" disabled={submitting}>
                    {strandForm.id ? 'Actualizar torón' : 'Crear torón'}
                  </Button>
                  <Button variant="outline-secondary" onClick={() => setStrandForm(emptyStrandForm())} disabled={submitting}>
                    Limpiar
                  </Button>
                </div>
              </Form>

              <Table hover responsive size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Nombre</th>
                    <th>Área</th>
                    <th>Fu</th>
                    <th className="text-end">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {strandTypes.map((strandType) => (
                    <tr key={strandType.id}>
                      <td>{strandType.nombre}</td>
                      <td>{strandType.area_mm2}</td>
                      <td>{strandType.Fu_default}</td>
                      <td className="text-end">
                        <Button
                          size="sm"
                          variant="outline-secondary"
                          className="me-2"
                          onClick={() => setStrandForm({
                            id: strandType.id,
                            nombre: strandType.nombre,
                            diametro_mm: String(strandType.diametro_mm),
                            area_mm2: String(strandType.area_mm2),
                            E_MPa: String(strandType.E_MPa),
                            Fu_default: String(strandType.Fu_default),
                            mu_por_toron_kg_m: String(strandType.mu_por_toron_kg_m),
                            notas: strandType.notas || '',
                          })}
                        >
                          Editar
                        </Button>
                        <Button size="sm" variant="outline-danger" onClick={() => handleStrandDelete(strandType.id)}>
                          Eliminar
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Tirantes</h5>
                  <small className="text-muted">
                    {selectedBridge ? `Puente seleccionado: ${selectedBridge.nombre}` : 'Selecciona un puente para administrar tirantes'}
                  </small>
                </div>
                <Badge bg={selectedBridge ? 'primary' : 'secondary'}>{cablesForBridge.length}</Badge>
              </div>

              <Form onSubmit={handleCableSubmit} className="mb-3">
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Nombre en puente</Form.Label>
                    <Form.Control
                      value={cableForm.nombre_en_puente}
                      onChange={(event) => setCableForm((prev) => ({ ...prev, nombre_en_puente: event.target.value }))}
                      required
                      disabled={!selectedBridgeId}
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={cableForm.notas}
                      onChange={(event) => setCableForm((prev) => ({ ...prev, notas: event.target.value }))}
                      disabled={!selectedBridgeId}
                    />
                  </Col>
                </Row>
                <div className="d-flex gap-2 mt-3">
                  <Button type="submit" disabled={submitting || !selectedBridgeId}>
                    {cableForm.id ? 'Actualizar tirante' : 'Crear tirante'}
                  </Button>
                  <Button variant="outline-secondary" onClick={() => setCableForm(emptyCableForm())} disabled={submitting}>
                    Limpiar
                  </Button>
                </div>
              </Form>

              <Table hover responsive size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Tirante</th>
                    <th>Notas</th>
                    <th className="text-end">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {cablesForBridge.map((cable) => (
                    <tr key={cable.id} className={selectedCableId === cable.id ? 'table-primary' : ''}>
                      <td>
                        <button
                          type="button"
                          className="btn btn-link btn-sm p-0 text-decoration-none"
                          onClick={() => setSelectedCableId(cable.id)}
                        >
                          {cable.nombre_en_puente}
                        </button>
                      </td>
                      <td>{cable.notas || '—'}</td>
                      <td className="text-end">
                        <Button
                          size="sm"
                          variant="outline-secondary"
                          className="me-2"
                          onClick={() => setCableForm({
                            id: cable.id,
                            nombre_en_puente: cable.nombre_en_puente,
                            notas: cable.notas || '',
                          })}
                        >
                          Editar
                        </Button>
                        <Button size="sm" variant="outline-danger" onClick={() => handleCableDelete(cable.id)}>
                          Eliminar
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card className="h-100">
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">Estados de Tirante</h5>
                  <small className="text-muted">
                    {selectedCable ? `Tirante seleccionado: ${selectedCable.nombre_en_puente}` : 'Selecciona un tirante para registrar versiones'}
                  </small>
                </div>
                <Badge bg={selectedCable ? 'primary' : 'secondary'}>{cableStates.length}</Badge>
              </div>

              <Form onSubmit={handleCableStateSubmit} className="mb-3">
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Vigente desde</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      value={cableStateForm.valid_from}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, valid_from: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={6}>
                    <Form.Label>Vigente hasta</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      value={cableStateForm.valid_to}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, valid_to: event.target.value }))}
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Longitud efectiva</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.length_effective_m}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, length_effective_m: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Torones totales</Form.Label>
                    <Form.Control
                      type="number"
                      value={cableStateForm.strands_total}
                      onChange={(event) => setCableStateForm((prev) => syncCableStateWithStrand({ ...prev, strands_total: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Torones activos</Form.Label>
                    <Form.Control
                      type="number"
                      value={cableStateForm.strands_active}
                      onChange={(event) => setCableStateForm((prev) => syncCableStateWithStrand({ ...prev, strands_active: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Tipo de torón</Form.Label>
                    <Form.Select
                      value={cableStateForm.strand_type_id}
                      onChange={(event) => setCableStateForm((prev) => syncCableStateWithStrand({ ...prev, strand_type_id: event.target.value }))}
                      disabled={!selectedCableId}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {strandTypes.map((strandType) => (
                        <option key={strandType.id} value={strandType.id}>
                          {strandType.nombre}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Mu total kg/m</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.mu_total_kg_m}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, mu_total_kg_m: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Mu activo kg/m</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.mu_active_basis_kg_m}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, mu_active_basis_kg_m: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>E MPa</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.E_MPa}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, E_MPa: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Área mm²</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.area_mm2}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, area_mm2: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Diámetro mm</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.diametro_mm}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, diametro_mm: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Tensión de diseño</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.design_tension_tf}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, design_tension_tf: event.target.value }))}
                      required
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Fu override</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.Fu_override}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, Fu_override: event.target.value }))}
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Longitud antivandálica</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={cableStateForm.antivandalic_length_m}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, antivandalic_length_m: event.target.value }))}
                      disabled={!selectedCableId}
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Notas / fuente</Form.Label>
                    <Form.Control
                      value={cableStateForm.notes}
                      onChange={(event) => setCableStateForm((prev) => ({ ...prev, notes: event.target.value }))}
                      disabled={!selectedCableId}
                    />
                  </Col>
                </Row>
                <div className="d-flex gap-2 mt-3">
                  <Button type="submit" disabled={submitting || !selectedCableId}>
                    Registrar estado
                  </Button>
                  <Button variant="outline-secondary" onClick={() => setCableStateForm(emptyCableStateForm())} disabled={submitting}>
                    Limpiar
                  </Button>
                </div>
              </Form>

              <Table hover responsive size="sm">
                <thead className="table-light">
                  <tr>
                    <th>Desde</th>
                    <th>Hasta</th>
                    <th>Activos / Total</th>
                    <th>Mu activo</th>
                  </tr>
                </thead>
                <tbody>
                  {cableStates.map((stateVersion) => (
                    <tr key={stateVersion.id}>
                      <td>{formatDateTime(stateVersion.valid_from)}</td>
                      <td>{formatDateTime(stateVersion.valid_to)}</td>
                      <td>{stateVersion.strands_active} / {stateVersion.strands_total}</td>
                      <td>{stateVersion.mu_active_basis_kg_m}</td>
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
