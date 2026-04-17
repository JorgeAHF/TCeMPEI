import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Form, Button, Alert, Container, Row, Col } from 'react-bootstrap'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { setAccessToken } from '../lib/apiClient'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ username, password })
      const { data } = await axios.post('/api/auth/token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      setAccessToken(data.access_token)
      login(data.access_token, data.refresh_token, data.user)
      navigate('/')
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error de autenticación')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container className="d-flex align-items-center justify-content-center" style={{ minHeight: '100vh' }}>
      <Row className="w-100 justify-content-center">
        <Col xs={12} sm={8} md={5} lg={4}>
          <Card className="shadow-sm">
            <Card.Body className="p-4">
              <h4 className="mb-1 fw-bold">TCeMPEI</h4>
              <p className="text-muted small mb-4">Monitoreo de Tirantes de Puentes</p>
              {error && <Alert variant="danger">{error}</Alert>}
              <Form onSubmit={handleSubmit}>
                <Form.Group className="mb-3">
                  <Form.Label>Usuario</Form.Label>
                  <Form.Control
                    type="text"
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    autoFocus
                    required
                  />
                </Form.Group>
                <Form.Group className="mb-4">
                  <Form.Label>Contraseña</Form.Label>
                  <Form.Control
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required
                  />
                </Form.Group>
                <Button type="submit" className="w-100" disabled={loading}>
                  {loading ? 'Ingresando…' : 'Ingresar'}
                </Button>
              </Form>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  )
}
