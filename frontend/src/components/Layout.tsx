import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Navbar, Nav, Container, Button, Badge } from 'react-bootstrap'
import { useAuth } from '../contexts/AuthContext'
import api from '../lib/apiClient'

const navItems = [
  { to: '/', label: 'Inicio' },
  { to: '/catalogo', label: 'Catálogo' },
  { to: '/adquisiciones', label: 'Adquisiciones' },
  { to: '/pesajes', label: 'Pesajes' },
  { to: '/analisis', label: 'Análisis' },
  { to: '/historico', label: 'Histórico' },
  { to: '/semaforo', label: 'Semáforo' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    const rt = localStorage.getItem('refresh_token')
    if (rt) {
      try { await api.post('/auth/logout', { refresh_token: rt }) } catch {}
    }
    logout()
    navigate('/login')
  }

  return (
    <>
      <Navbar bg="dark" variant="dark" expand="lg" sticky="top">
        <Container fluid>
          <Navbar.Brand href="/">TCeMPEI</Navbar.Brand>
          <Navbar.Toggle />
          <Navbar.Collapse>
            <Nav className="me-auto">
              {navItems.map(({ to, label }) => (
                <Nav.Link key={to} as={NavLink} to={to} end={to === '/'}>
                  {label}
                </Nav.Link>
              ))}
            </Nav>
            <Nav className="align-items-center gap-2">
              {user && (
                <span className="text-light small">
                  {user.full_name || user.username}{' '}
                  <Badge bg="secondary">{user.role}</Badge>
                </span>
              )}
              <Button size="sm" variant="outline-light" onClick={handleLogout}>
                Salir
              </Button>
            </Nav>
          </Navbar.Collapse>
        </Container>
      </Navbar>
      <Container fluid className="py-4">
        <Outlet />
      </Container>
    </>
  )
}
