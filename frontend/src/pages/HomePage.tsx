import { useEffect, useState } from 'react'
import { Row, Col, Card, ListGroup } from 'react-bootstrap'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import api from '../lib/apiClient'

export default function HomePage() {
  const { user } = useAuth()
  const [stats, setStats] = useState({ bridges: 0, cables: 0, acquisitions: 0 })

  useEffect(() => {
    Promise.all([
      api.get('/bridges'),
      api.get('/cables'),
      api.get('/acquisitions').catch(() => ({ data: [] })),
    ]).then(([b, c, a]) => {
      setStats({ bridges: b.data.length, cables: c.data.length, acquisitions: a.data.length })
    }).catch(() => {})
  }, [])

  const modules = [
    { to: '/catalogo', title: 'Catálogo', desc: 'Gestionar puentes, tirantes y tipos de torón', icon: '🏗️' },
    { to: '/adquisiciones', title: 'Adquisiciones', desc: 'Registrar campañas de medición de vibración', icon: '📡' },
    { to: '/pesajes', title: 'Pesajes', desc: 'Registrar pesajes directos de tirantes', icon: '⚖️' },
    { to: '/analisis', title: 'Análisis', desc: 'Ejecutar FFT/PSD y calcular tensión', icon: '📊' },
    { to: '/historico', title: 'Histórico', desc: 'Evolución de tensión y frecuencia', icon: '📈' },
    { to: '/semaforo', title: 'Semáforo', desc: 'Estado actual de salud de tirantes', icon: '🚦' },
  ]

  return (
    <>
      <div className="mb-4">
        <h4 className="fw-bold">Bienvenido, {user?.full_name || user?.username}</h4>
        <p className="text-muted">Sistema de monitoreo y análisis de tirantes de puentes atirantados</p>
      </div>

      <Row className="g-3 mb-4">
        {[
          { label: 'Puentes', value: stats.bridges },
          { label: 'Tirantes', value: stats.cables },
          { label: 'Adquisiciones', value: stats.acquisitions },
        ].map(s => (
          <Col key={s.label} xs={6} md={3}>
            <Card className="text-center py-3">
              <Card.Body>
                <h2 className="fw-bold mb-0">{s.value}</h2>
                <small className="text-muted">{s.label}</small>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Row className="g-3">
        {modules.map(m => (
          <Col key={m.to} xs={12} sm={6} lg={4}>
            <Card as={Link} to={m.to} className="h-100 text-decoration-none text-dark card-hover"
              style={{ cursor: 'pointer', transition: 'box-shadow .2s' }}
              onMouseOver={e => (e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,.15)')}
              onMouseOut={e => (e.currentTarget.style.boxShadow = '')}>
              <Card.Body>
                <div className="fs-2 mb-2">{m.icon}</div>
                <Card.Title className="fw-semibold">{m.title}</Card.Title>
                <Card.Text className="text-muted small">{m.desc}</Card.Text>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    </>
  )
}
