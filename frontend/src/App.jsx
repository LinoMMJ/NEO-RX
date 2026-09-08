import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import Layout from './components/layout/Layout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import EscaneoPage from './pages/EscaneoPage'
import InformePage from './pages/InformePage'
import PacientesPage from './pages/PacientesPage'

function ProtectedRoute({ children, roles }) {
  const { isAuth, rol } = useAuth()
  if (!isAuth) return <Navigate to="/login" replace />
  if (roles && !roles.includes(rol)) return <Navigate to="/dashboard" replace />
  return children
}

function AppRoutes() {
  const { isAuth } = useAuth()
  return (
    <Routes>
      {/* Públicas */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={isAuth ? <Navigate to="/dashboard" replace /> : <LoginPage />} />

      {/* Protegidas */}
      <Route path="/dashboard" element={
        <ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>
      } />
      <Route path="/escaneo" element={
        <ProtectedRoute><Layout><EscaneoPage /></Layout></ProtectedRoute>
      } />
      <Route path="/informes/:id" element={
        <ProtectedRoute roles={['medico']}><Layout><InformePage /></Layout></ProtectedRoute>
      } />
      <Route path="/informes" element={
        <ProtectedRoute roles={['medico']}><Layout><InformePage /></Layout></ProtectedRoute>
      } />
      <Route path="/pacientes" element={
        <ProtectedRoute><Layout><PacientesPage /></Layout></ProtectedRoute>
      } />
      {/* /estudios redirige a escaneo (no hay página de lista separada aún) */}
      <Route path="/estudios" element={<Navigate to="/escaneo" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
