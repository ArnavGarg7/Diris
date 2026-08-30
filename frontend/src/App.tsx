import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import AppLayout from './components/AppLayout'
import Placeholder from './components/Placeholder'
import Login from './pages/Login'
import Register from './pages/Register'

function Protected({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/app"
            element={
              <Protected>
                <AppLayout />
              </Protected>
            }
          >
            <Route index element={<Navigate to="documents" replace />} />
            <Route path="documents" element={<Placeholder title="Documents" />} />
            <Route path="chat" element={<Placeholder title="Chat" />} />
            <Route path="graph" element={<Placeholder title="Graph" />} />
            <Route path="search" element={<Placeholder title="Search" />} />
            <Route path="entities" element={<Placeholder title="Entities" />} />
          </Route>
          <Route path="*" element={<Navigate to="/app" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
