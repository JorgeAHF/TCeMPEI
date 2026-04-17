import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { User } from '../types/api'

interface AuthState {
  accessToken: string | null
  user: User | null
}

interface AuthContextType extends AuthState {
  login: (accessToken: string, refreshToken: string, user: User) => void
  logout: () => void
  setNewTokens: (accessToken: string, refreshToken: string) => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ accessToken: null, user: null })

  const login = useCallback((accessToken: string, refreshToken: string, user: User) => {
    localStorage.setItem('refresh_token', refreshToken)
    setState({ accessToken, user })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('refresh_token')
    setState({ accessToken: null, user: null })
  }, [])

  const setNewTokens = useCallback((accessToken: string, refreshToken: string) => {
    localStorage.setItem('refresh_token', refreshToken)
    setState(prev => ({ ...prev, accessToken }))
  }, [])

  return (
    <AuthContext.Provider value={{ ...state, login, logout, setNewTokens, isAuthenticated: !!state.accessToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
