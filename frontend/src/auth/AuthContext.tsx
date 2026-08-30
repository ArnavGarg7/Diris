import { createContext, useContext, useState, type ReactNode } from 'react'
import { getToken, setToken } from '../api'

type AuthState = {
  token: string | null
  email: string | null
  login: (token: string, email: string) => void
  logout: () => void
}

const AuthCtx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTok] = useState<string | null>(getToken())
  const [email, setEmail] = useState<string | null>(localStorage.getItem('diris_email'))

  const login = (t: string, e: string) => {
    setToken(t)
    localStorage.setItem('diris_email', e)
    setTok(t)
    setEmail(e)
  }
  const logout = () => {
    setToken(null)
    localStorage.removeItem('diris_email')
    setTok(null)
    setEmail(null)
  }

  return <AuthCtx.Provider value={{ token, email, login, logout }}>{children}</AuthCtx.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
