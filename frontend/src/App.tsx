import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { configureApiClient, setAccessToken } from './lib/apiClient'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import HomePage from './pages/HomePage'
import CatalogoPage from './pages/CatalogoPage'
import AdquisicionesPage from './pages/AdquisicionesPage'
import PesajesPage from './pages/PesajesPage'
import AnalisisPage from './pages/AnalisisPage'
import HistoricoPage from './pages/HistoricoPage'
import SemaforoPage from './pages/SemaforoPage'

function ApiSetup() {
  const { accessToken, logout, setNewTokens } = useAuth()
  useEffect(() => {
    setAccessToken(accessToken)
  }, [accessToken])
  useEffect(() => {
    configureApiClient({
      getAccessToken: () => accessToken,
      onAuthFailed: logout,
      onTokensRefreshed: setNewTokens,
    })
  }, [logout, setNewTokens])
  return null
}

export default function App() {
  return (
    <AuthProvider>
      <ApiSetup />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/catalogo" element={<CatalogoPage />} />
              <Route path="/adquisiciones" element={<AdquisicionesPage />} />
              <Route path="/pesajes" element={<PesajesPage />} />
              <Route path="/analisis" element={<AnalisisPage />} />
              <Route path="/historico" element={<HistoricoPage />} />
              <Route path="/semaforo" element={<SemaforoPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
