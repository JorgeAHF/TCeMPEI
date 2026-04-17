import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Alert, Badge, Button, Card, Col, Form, Row, Spinner, Table } from 'react-bootstrap'
import api from '../lib/apiClient'
import { apiErrorMessage, formatDateTime, fromDateTimeLocalInput, toDateTimeLocalInput } from '../lib/utils'
import {
  Bridge,
  Cable,
  CableConfigSnapshot,
  CableStateVersion,
  KCalibration,
  StrandType,
  WeighingCampaign,
  WeighingMeasurement,
} from '../types/api'

type CampaignFormState = {
  bridge_id: string
  performed_at: string
  performed_by: string
  method: string
  equipment: string
  temperature_C: string
  notes: string
}

type MeasurementFormState = {
  weighing_campaign_id: string
  cable_id: string
  measured_tension_tf: string
  measured_temperature_C: string
  notes: string
}

type SnapshotFormState = {
  cable_id: string
  source_state_version_id: string
  effective_length_m: string
  mu_basis: string
  mu_value_kg_m: string
  strands_active: string
  strands_total: string
  strand_type_id: string
  notes: string
}

type CalibrationFormState = {
  cable_id: string
  derived_from_weighing_measurement_id: string
  config_snapshot_id: string
  k_value: string
  valid_from: string
  valid_to: string
  algorithm_version: string
  notes: string
}

const emptyCampaignForm = (): CampaignFormState => ({
  bridge_id: '',
  performed_at: toDateTimeLocalInput(new Date().toISOString()),
  performed_by: '',
  method: '',
  equipment: '',
  temperature_C: '',
  notes: '',
})

const emptyMeasurementForm = (): MeasurementFormState => ({
  weighing_campaign_id: '',
  cable_id: '',
  measured_tension_tf: '',
  measured_temperature_C: '',
  notes: '',
})

const emptySnapshotForm = (): SnapshotFormState => ({
  cable_id: '',
  source_state_version_id: '',
  effective_length_m: '',
  mu_basis: 'active',
  mu_value_kg_m: '',
  strands_active: '',
  strands_total: '',
  strand_type_id: '',
  notes: '',
})

const emptyCalibrationForm = (): CalibrationFormState => ({
  cable_id: '',
  derived_from_weighing_measurement_id: '',
  config_snapshot_id: '',
  k_value: '',
  valid_from: toDateTimeLocalInput(new Date().toISOString()),
  valid_to: '',
  algorithm_version: 'v1.0',
  notes: '',
})

export default function PesajesPage() {
  const [bridges, setBridges] = useState<Bridge[]>([])
  const [cables, setCables] = useState<Cable[]>([])
  const [strandTypes, setStrandTypes] = useState<StrandType[]>([])
  const [campaigns, setCampaigns] = useState<WeighingCampaign[]>([])
  const [measurements, setMeasurements] = useState<WeighingMeasurement[]>([])
  const [snapshots, setSnapshots] = useState<CableConfigSnapshot[]>([])
  const [calibrations, setCalibrations] = useState<KCalibration[]>([])
  const [cableStates, setCableStates] = useState<CableStateVersion[]>([])
  const [campaignForm, setCampaignForm] = useState<CampaignFormState>(emptyCampaignForm())
  const [measurementForm, setMeasurementForm] = useState<MeasurementFormState>(emptyMeasurementForm())
  const [snapshotForm, setSnapshotForm] = useState<SnapshotFormState>(emptySnapshotForm())
  const [calibrationForm, setCalibrationForm] = useState<CalibrationFormState>(emptyCalibrationForm())
  const [selectedCampaignId, setSelectedCampaignId] = useState('')
  const [selectedCableId, setSelectedCableId] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const selectedCampaign = campaigns.find((campaign) => String(campaign.id) === selectedCampaignId) || null
  const bridgeIdForCableSelectors = selectedCampaign ? String(selectedCampaign.bridge_id) : campaignForm.bridge_id
  const cablesForBridge = useMemo(
    () => cables.filter((cable) => String(cable.bridge_id) === bridgeIdForCableSelectors),
    [bridgeIdForCableSelectors, cables],
  )
  const snapshotsForCable = useMemo(
    () => snapshots.filter((snapshot) => String(snapshot.cable_id) === (calibrationForm.cable_id || snapshotForm.cable_id || selectedCableId)),
    [calibrationForm.cable_id, selectedCableId, snapshotForm.cable_id, snapshots],
  )
  const measurementsForCable = useMemo(
    () => measurements.filter((measurement) => String(measurement.cable_id) === (calibrationForm.cable_id || selectedCableId)),
    [calibrationForm.cable_id, measurements, selectedCableId],
  )

  useEffect(() => {
    loadContext()
  }, [])

  useEffect(() => {
    const cableId = snapshotForm.cable_id || selectedCableId
    if (!cableId) {
      setCableStates([])
      return
    }
    loadCableStates(Number(cableId))
  }, [snapshotForm.cable_id, selectedCableId])

  async function loadContext() {
    setLoading(true)
    try {
      const [bridgesRes, cablesRes, strandsRes, campaignsRes, measurementsRes, snapshotsRes, calibrationsRes] = await Promise.all([
        api.get('/bridges'),
        api.get('/cables'),
        api.get('/strand-types'),
        api.get('/weighing-campaigns'),
        api.get('/weighing-measurements'),
        api.get('/cable-config-snapshots'),
        api.get('/k-calibrations'),
      ])
      setBridges(bridgesRes.data)
      setCables(cablesRes.data)
      setStrandTypes(strandsRes.data)
      setCampaigns(campaignsRes.data)
      setMeasurements(measurementsRes.data)
      setSnapshots(snapshotsRes.data)
      setCalibrations(calibrationsRes.data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo cargar el módulo de pesajes'))
    } finally {
      setLoading(false)
    }
  }

  async function loadCableStates(cableId: number) {
    try {
      const { data } = await api.get(`/cables/${cableId}/states`)
      setCableStates(data)
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudieron cargar los estados del tirante'))
    }
  }

  function resetMessages() {
    setError('')
    setSuccess('')
  }

  function fillSnapshotFromState(stateVersionId: string) {
    const stateVersion = cableStates.find((item) => String(item.id) === stateVersionId)
    if (!stateVersion) return
    setSnapshotForm((prev) => ({
      ...prev,
      source_state_version_id: stateVersionId,
      effective_length_m: String(stateVersion.length_effective_m),
      mu_value_kg_m: String(stateVersion.mu_active_basis_kg_m),
      strands_active: String(stateVersion.strands_active),
      strands_total: String(stateVersion.strands_total),
      strand_type_id: String(stateVersion.strand_type_id),
    }))
  }

  async function handleCampaignSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const { data } = await api.post('/weighing-campaigns', {
        bridge_id: Number(campaignForm.bridge_id),
        performed_at: fromDateTimeLocalInput(campaignForm.performed_at),
        performed_by: campaignForm.performed_by,
        method: campaignForm.method,
        equipment: campaignForm.equipment,
        temperature_C: campaignForm.temperature_C ? Number(campaignForm.temperature_C) : undefined,
        notes: campaignForm.notes || undefined,
      })
      await loadContext()
      setSelectedCampaignId(String(data.id))
      setMeasurementForm((prev) => ({ ...prev, weighing_campaign_id: String(data.id) }))
      setSuccess(`Campaña de pesaje ${data.id} creada`)
      setCampaignForm(emptyCampaignForm())
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo crear la campaña de pesaje'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleMeasurementSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const { data } = await api.post('/weighing-measurements', {
        weighing_campaign_id: Number(measurementForm.weighing_campaign_id),
        cable_id: Number(measurementForm.cable_id),
        measured_tension_tf: Number(measurementForm.measured_tension_tf),
        measured_temperature_C: measurementForm.measured_temperature_C ? Number(measurementForm.measured_temperature_C) : undefined,
        notes: measurementForm.notes || undefined,
      })
      await loadContext()
      setSelectedCableId(String(data.cable_id))
      setSnapshotForm((prev) => ({ ...prev, cable_id: String(data.cable_id) }))
      setCalibrationForm((prev) => ({
        ...prev,
        cable_id: String(data.cable_id),
        derived_from_weighing_measurement_id: String(data.id),
      }))
      setSuccess(`Medición ${data.id} registrada`)
      setMeasurementForm((prev) => ({
        ...emptyMeasurementForm(),
        weighing_campaign_id: prev.weighing_campaign_id,
        cable_id: prev.cable_id,
      }))
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo registrar la medición'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleSnapshotSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      const { data } = await api.post('/cable-config-snapshots', {
        cable_id: Number(snapshotForm.cable_id),
        source_state_version_id: snapshotForm.source_state_version_id ? Number(snapshotForm.source_state_version_id) : undefined,
        effective_length_m: Number(snapshotForm.effective_length_m),
        mu_basis: snapshotForm.mu_basis,
        mu_value_kg_m: Number(snapshotForm.mu_value_kg_m),
        strands_active: Number(snapshotForm.strands_active),
        strands_total: Number(snapshotForm.strands_total),
        strand_type_id: snapshotForm.strand_type_id ? Number(snapshotForm.strand_type_id) : undefined,
        notes: snapshotForm.notes || undefined,
      })
      await loadContext()
      setCalibrationForm((prev) => ({
        ...prev,
        cable_id: String(data.cable_id),
        config_snapshot_id: String(data.id),
      }))
      setSuccess(`Snapshot ${data.id} creado`)
      setSnapshotForm((prev) => ({ ...emptySnapshotForm(), cable_id: prev.cable_id }))
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo crear el snapshot'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleCalibrationSubmit(event: FormEvent) {
    event.preventDefault()
    resetMessages()
    setSubmitting(true)
    try {
      await api.post('/k-calibrations', {
        cable_id: Number(calibrationForm.cable_id),
        derived_from_weighing_measurement_id: Number(calibrationForm.derived_from_weighing_measurement_id),
        config_snapshot_id: Number(calibrationForm.config_snapshot_id),
        k_value: Number(calibrationForm.k_value),
        valid_from: fromDateTimeLocalInput(calibrationForm.valid_from),
        valid_to: fromDateTimeLocalInput(calibrationForm.valid_to),
        algorithm_version: calibrationForm.algorithm_version,
        notes: calibrationForm.notes || undefined,
      })
      await loadContext()
      setSuccess('Calibración K registrada')
      setCalibrationForm((prev) => ({
        ...emptyCalibrationForm(),
        cable_id: prev.cable_id,
        derived_from_weighing_measurement_id: prev.derived_from_weighing_measurement_id,
        config_snapshot_id: prev.config_snapshot_id,
      }))
    } catch (err) {
      setError(apiErrorMessage(err, 'No se pudo registrar la calibración K'))
    } finally {
      setSubmitting(false)
    }
  }

  function selectCampaign(campaign: WeighingCampaign) {
    setSelectedCampaignId(String(campaign.id))
    setCampaignForm({
      bridge_id: String(campaign.bridge_id),
      performed_at: toDateTimeLocalInput(campaign.performed_at),
      performed_by: campaign.performed_by,
      method: campaign.method,
      equipment: campaign.equipment,
      temperature_C: campaign.temperature_C ? String(campaign.temperature_C) : '',
      notes: campaign.notes || '',
    })
    setMeasurementForm((prev) => ({ ...prev, weighing_campaign_id: String(campaign.id) }))
  }

  if (loading) {
    return (
      <div className="d-flex align-items-center gap-2">
        <Spinner size="sm" />
        <span>Cargando pesajes…</span>
      </div>
    )
  }

  return (
    <>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="fw-bold mb-1">Pesajes</h4>
          <p className="text-muted mb-0">Campañas, mediciones directas, snapshots y calibración K</p>
        </div>
        <Button variant="outline-secondary" onClick={loadContext} disabled={submitting}>
          Recargar
        </Button>
      </div>

      {error && <Alert variant="danger">{error}</Alert>}
      {success && <Alert variant="success">{success}</Alert>}

      <Row className="g-4">
        <Col xl={6}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">1. Campaña de pesaje</h5>
                  <small className="text-muted">Crea la campaña base para registrar mediciones</small>
                </div>
                <Badge bg="secondary">{campaigns.length}</Badge>
              </div>

              <Form onSubmit={handleCampaignSubmit}>
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Puente</Form.Label>
                    <Form.Select
                      value={campaignForm.bridge_id}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, bridge_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {bridges.map((bridge) => (
                        <option key={bridge.id} value={bridge.id}>
                          {bridge.nombre}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>Fecha</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      value={campaignForm.performed_at}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, performed_at: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Responsable</Form.Label>
                    <Form.Control
                      value={campaignForm.performed_by}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, performed_by: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Método</Form.Label>
                    <Form.Control
                      value={campaignForm.method}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, method: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Equipo</Form.Label>
                    <Form.Control
                      value={campaignForm.equipment}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, equipment: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Temperatura C</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={campaignForm.temperature_C}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, temperature_C: event.target.value }))}
                    />
                  </Col>
                  <Col md={8}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={campaignForm.notes}
                      onChange={(event) => setCampaignForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting}>
                      Crear campaña
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">2. Medición por tirante</h5>
                  <small className="text-muted">Asocia la lectura al tirante dentro de la campaña</small>
                </div>
                <Badge bg="secondary">{measurements.length}</Badge>
              </div>

              <Form onSubmit={handleMeasurementSubmit}>
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Campaña</Form.Label>
                    <Form.Select
                      value={measurementForm.weighing_campaign_id}
                      onChange={(event) => {
                        const campaignId = event.target.value
                        const campaign = campaigns.find((item) => String(item.id) === campaignId)
                        setMeasurementForm((prev) => ({ ...prev, weighing_campaign_id: campaignId }))
                        if (campaign) setSelectedCampaignId(campaignId)
                      }}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {campaigns.map((campaign) => (
                        <option key={campaign.id} value={campaign.id}>
                          #{campaign.id} · {formatDateTime(campaign.performed_at)}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>Tirante</Form.Label>
                    <Form.Select
                      value={measurementForm.cable_id}
                      onChange={(event) => {
                        const cableId = event.target.value
                        setMeasurementForm((prev) => ({ ...prev, cable_id: cableId }))
                        setSelectedCableId(cableId)
                      }}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {cablesForBridge.map((cable) => (
                        <option key={cable.id} value={cable.id}>
                          {cable.nombre_en_puente}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Tensión tf</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={measurementForm.measured_tension_tf}
                      onChange={(event) => setMeasurementForm((prev) => ({ ...prev, measured_tension_tf: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Temperatura C</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={measurementForm.measured_temperature_C}
                      onChange={(event) => setMeasurementForm((prev) => ({ ...prev, measured_temperature_C: event.target.value }))}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={measurementForm.notes}
                      onChange={(event) => setMeasurementForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting}>
                      Guardar medición
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">3. Snapshot para K</h5>
                  <small className="text-muted">Congela la configuración usada para calibrar</small>
                </div>
                <Badge bg="secondary">{snapshots.length}</Badge>
              </div>

              <Form onSubmit={handleSnapshotSubmit}>
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Tirante</Form.Label>
                    <Form.Select
                      value={snapshotForm.cable_id}
                      onChange={(event) => {
                        const cableId = event.target.value
                        setSnapshotForm((prev) => ({ ...prev, cable_id: cableId, source_state_version_id: '' }))
                        setSelectedCableId(cableId)
                      }}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {cablesForBridge.map((cable) => (
                        <option key={cable.id} value={cable.id}>
                          {cable.nombre_en_puente}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>Estado fuente</Form.Label>
                    <Form.Select
                      value={snapshotForm.source_state_version_id}
                      onChange={(event) => fillSnapshotFromState(event.target.value)}
                    >
                      <option value="">Opcional…</option>
                      {cableStates.map((stateVersion) => (
                        <option key={stateVersion.id} value={stateVersion.id}>
                          #{stateVersion.id} · {formatDateTime(stateVersion.valid_from)}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Longitud efectiva</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={snapshotForm.effective_length_m}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, effective_length_m: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Mu basis</Form.Label>
                    <Form.Select
                      value={snapshotForm.mu_basis}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, mu_basis: event.target.value }))}
                    >
                      <option value="active">active</option>
                      <option value="total">total</option>
                      <option value="custom">custom</option>
                    </Form.Select>
                  </Col>
                  <Col md={4}>
                    <Form.Label>Mu kg/m</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={snapshotForm.mu_value_kg_m}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, mu_value_kg_m: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Torones activos</Form.Label>
                    <Form.Control
                      type="number"
                      value={snapshotForm.strands_active}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, strands_active: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Torones totales</Form.Label>
                    <Form.Control
                      type="number"
                      value={snapshotForm.strands_total}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, strands_total: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Tipo de torón</Form.Label>
                    <Form.Select
                      value={snapshotForm.strand_type_id}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, strand_type_id: event.target.value }))}
                    >
                      <option value="">Opcional…</option>
                      {strandTypes.map((strandType) => (
                        <option key={strandType.id} value={strandType.id}>
                          {strandType.nombre}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={12}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={snapshotForm.notes}
                      onChange={(event) => setSnapshotForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting}>
                      Crear snapshot
                    </Button>
                  </Col>
                </Row>
              </Form>
            </Card.Body>
          </Card>
        </Col>

        <Col xl={6}>
          <Card>
            <Card.Body>
              <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                  <h5 className="mb-0">4. Calibración K</h5>
                  <small className="text-muted">Vincula medición y snapshot para dejar K vigente</small>
                </div>
                <Badge bg="secondary">{calibrations.length}</Badge>
              </div>

              <Form onSubmit={handleCalibrationSubmit}>
                <Row className="g-3">
                  <Col md={6}>
                    <Form.Label>Tirante</Form.Label>
                    <Form.Select
                      value={calibrationForm.cable_id}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, cable_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {cablesForBridge.map((cable) => (
                        <option key={cable.id} value={cable.id}>
                          {cable.nombre_en_puente}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>Medición</Form.Label>
                    <Form.Select
                      value={calibrationForm.derived_from_weighing_measurement_id}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, derived_from_weighing_measurement_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {measurementsForCable.map((measurement) => (
                        <option key={measurement.id} value={measurement.id}>
                          #{measurement.id} · {measurement.measured_tension_tf} tf
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>Snapshot</Form.Label>
                    <Form.Select
                      value={calibrationForm.config_snapshot_id}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, config_snapshot_id: event.target.value }))}
                      required
                    >
                      <option value="">Seleccionar…</option>
                      {snapshotsForCable.map((snapshot) => (
                        <option key={snapshot.id} value={snapshot.id}>
                          #{snapshot.id} · L={snapshot.effective_length_m}
                        </option>
                      ))}
                    </Form.Select>
                  </Col>
                  <Col md={6}>
                    <Form.Label>K value</Form.Label>
                    <Form.Control
                      type="number"
                      step="any"
                      value={calibrationForm.k_value}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, k_value: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Vigente desde</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      value={calibrationForm.valid_from}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, valid_from: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Vigente hasta</Form.Label>
                    <Form.Control
                      type="datetime-local"
                      value={calibrationForm.valid_to}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, valid_to: event.target.value }))}
                    />
                  </Col>
                  <Col md={4}>
                    <Form.Label>Versión algoritmo</Form.Label>
                    <Form.Control
                      value={calibrationForm.algorithm_version}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, algorithm_version: event.target.value }))}
                      required
                    />
                  </Col>
                  <Col md={12}>
                    <Form.Label>Notas</Form.Label>
                    <Form.Control
                      value={calibrationForm.notes}
                      onChange={(event) => setCalibrationForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                  </Col>
                  <Col md={12}>
                    <Button type="submit" disabled={submitting}>
                      Registrar K
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
              <h5 className="mb-3">Resumen reciente</h5>
              <Row className="g-4">
                <Col lg={4}>
                  <Table hover responsive size="sm">
                    <thead className="table-light">
                      <tr>
                        <th>Campaña</th>
                        <th>Fecha</th>
                        <th className="text-end">Acción</th>
                      </tr>
                    </thead>
                    <tbody>
                      {campaigns.slice(0, 6).map((campaign) => (
                        <tr key={campaign.id} className={String(campaign.id) === selectedCampaignId ? 'table-primary' : ''}>
                          <td>#{campaign.id}</td>
                          <td>{formatDateTime(campaign.performed_at)}</td>
                          <td className="text-end">
                            <Button size="sm" variant="outline-secondary" onClick={() => selectCampaign(campaign)}>
                              Usar
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Col>
                <Col lg={4}>
                  <Table hover responsive size="sm">
                    <thead className="table-light">
                      <tr>
                        <th>Medición</th>
                        <th>Tirante</th>
                        <th>Tensión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {measurements.slice(0, 6).map((measurement) => (
                        <tr key={measurement.id}>
                          <td>#{measurement.id}</td>
                          <td>{cables.find((cable) => cable.id === measurement.cable_id)?.nombre_en_puente || measurement.cable_id}</td>
                          <td>{measurement.measured_tension_tf}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Col>
                <Col lg={4}>
                  <Table hover responsive size="sm">
                    <thead className="table-light">
                      <tr>
                        <th>K</th>
                        <th>Tirante</th>
                        <th>Desde</th>
                      </tr>
                    </thead>
                    <tbody>
                      {calibrations.slice(0, 6).map((calibration) => (
                        <tr key={calibration.id}>
                          <td>{calibration.k_value}</td>
                          <td>{cables.find((cable) => cable.id === calibration.cable_id)?.nombre_en_puente || calibration.cable_id}</td>
                          <td>{formatDateTime(calibration.valid_from)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  )
}
