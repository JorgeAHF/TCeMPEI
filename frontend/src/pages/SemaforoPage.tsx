import { useEffect, useState } from 'react'
import { Form, Button, Table, Badge, Alert, Spinner, Row, Col, Card } from 'react-bootstrap'
import api from '../lib/apiClient'
import { Bridge, Acquisition, SemaforoResponse } from '../types/api'

function estadoBadge(estado: string) {
  if (estado === 'ALERTA') return <Badge bg="danger">ALERTA</Badge>
  return <Badge bg="success">OK</Badge>
}

function pctBar(pct: number) {
  const color = pct > 90 ? 'danger' : pct > 70 ? 'warning' : 'success'
  return (
    <div className="d-flex align-items-center gap-2">
      <div className="progress flex-grow-1" style={{ height: 12 }}>
        <div className={`progress-bar bg-${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="small">{pct.toFixed(1)}%</span>
    </div>
  )
}

export default function SemaforoPage() {
  const [bridges, setBridges] = useState<Bridge[]>([])
  const [acquisitions, setAcquisitions] = useState<Acquisition[]>([])
  const [bridgeId, setBridgeId] = useState('')
  const [acqId, setAcqId] = useState('')
  const [result, setResult] = useState<SemaforoResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { api.get('/bridges').then(r => setBridges(r.data)) }, [])

  useEffect(() => {
    if (!bridgeId) { setAcquisitions([]); setAcqId(''); return }
    api.get('/acquisitions').then(r => {
      setAcquisitions(r.data.filter((a: Acquisition) => String(a.bridge_id) === bridgeId))
      setAcqId('')
    })
  }, [bridgeId])

  async function handleQuery() {
    if (!bridgeId || !acqId) return
    setLoading(true); setError(''); setResult(null)
    try {
      const { data } = await api.get(`/bridges/${bridgeId}/semaforo`, { params: { acquisition_id: acqId } })
      setResult(data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Error al consultar semáforo')
    } finally { setLoading(false) }
  }

  return (
    <>
      <h4 className="fw-bold mb-4">Semáforo de Salud</h4>
      <Card className="mb-4">
        <Card.Body>
          <Row className="g-3 align-items-end">
            <Col md={4}>
              <Form.Label>Puente</Form.Label>
              <Form.Select value={bridgeId} onChange={e => setBridgeId(e.target.value)}>
                <option value="">Seleccionar…</option>
                {bridges.map(b => <option key={b.id} value={b.id}>{b.nombre}</option>)}
              </Form.Select>
            </Col>
            <Col md={4}>
              <Form.Label>Adquisición</Form.Label>
              <Form.Select value={acqId} onChange={e => setAcqId(e.target.value)} disabled={!bridgeId}>
                <option value="">Seleccionar…</option>
                {acquisitions.map(a => (
                  <option key={a.id} value={a.id}>#{a.id} — {new Date(a.acquired_at).toLocaleString()}</option>
                ))}
              </Form.Select>
            </Col>
            <Col md={2}>
              <Button onClick={handleQuery} disabled={!bridgeId || !acqId || loading} className="w-100">
                {loading ? <Spinner size="sm" /> : 'Consultar'}
              </Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {error && <Alert variant="danger">{error}</Alert>}

      {result && (
        <>
          <Row className="g-3 mb-4">
            <Col xs={6} md={3}>
              <Card className="text-center py-3">
                <Card.Body>
                  <h3 className="fw-bold mb-0">{result.total}</h3>
                  <small className="text-muted">Tirantes analizados</small>
                </Card.Body>
              </Card>
            </Col>
            <Col xs={6} md={3}>
              <Card className={`text-center py-3 ${result.exceden > 0 ? 'border-danger' : 'border-success'}`}>
                <Card.Body>
                  <h3 className={`fw-bold mb-0 text-${result.exceden > 0 ? 'danger' : 'success'}`}>{result.exceden}</h3>
                  <small className="text-muted">En alerta</small>
                </Card.Body>
              </Card>
            </Col>
          </Row>

          <Table hover bordered size="sm" responsive>
            <thead className="table-dark">
              <tr>
                <th>Tirante</th>
                <th>Tensión (tf)</th>
                <th>Fu (tf)</th>
                <th>% Fu</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {result.items.map(item => (
                <tr key={item.cable_id} className={item.estado === 'ALERTA' ? 'table-danger' : ''}>
                  <td className="fw-semibold">{item.nombre_en_puente}</td>
                  <td>{item.tension_tf.toFixed(2)}</td>
                  <td>{item.fu.toFixed(2)}</td>
                  <td style={{ minWidth: 160 }}>{pctBar(item.pct_fu)}</td>
                  <td>{estadoBadge(item.estado)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
    </>
  )
}
