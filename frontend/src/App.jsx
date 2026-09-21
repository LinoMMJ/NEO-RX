import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { useAuth } from './context/useAuth'
import { ToastProvider } from './context/ToastContext'
import Layout from './components/layout/Layout'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
const PasswordResetPage = lazy(() => import('./pages/PasswordResetPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const EscaneoPage = lazy(() => import('./pages/EscaneoPage'))
const AnalisisPage = lazy(() => import('./pages/AnalisisPage'))
const InformePage = lazy(() => import('./pages/InformePage'))
const PacientesPage = lazy(() => import('./pages/PacientesPage'))
const EstudiosPage = lazy(() => import('./pages/EstudiosPage'))
const ActividadPage = lazy(() => import('./pages/ActividadPage'))
const AdminUsuariosPage = lazy(() => import('./pages/AdminUsuariosPage'))

function ProtectedRoute({ children, roles }) {
  const { isAuth, rol } = useAuth()
  if (!isAuth) return <Navigate to="/login" replace />
  if (roles && !roles.includes(rol)) return <Navigate to="/dashboard" replace />
  return children
}

function AppRoutes() {
  const { isAuth, ready } = useAuth()
  if (!ready) return <div role="status" className="p-8 text-center">Comprobando sesión…</div>
  return (
    <Routes>
      {/* Públicas */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={isAuth ? <Navigate to="/dashboard" replace /> : <LoginPage />} />

      <Route path="/recuperar-contrasena" element={<PasswordResetPage />} />

      {/* Protegidas */}
      <Route path="/dashboard" element={
        <ProtectedRoute><Layout><DashboardPage /></Layout></ProtectedRoute>
      } />
      <Route path="/escaneo" element={
        <ProtectedRoute roles={['recepcionista', 'medico']}><Layout><EscaneoPage /></Layout></ProtectedRoute>
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
      <Route path="/admin/usuarios" element={
        <ProtectedRoute roles={['administrador']}><Layout><AdminUsuariosPage /></Layout></ProtectedRoute>
      } />
      <Route path="/analisis/:id" element={<ProtectedRoute><Layout><AnalisisPage /></Layout></ProtectedRoute>} />
      <Route path="/estudios" element={<ProtectedRoute><Layout><EstudiosPage /></Layout></ProtectedRoute>} />
      <Route path="/pendientes" element={<ProtectedRoute><Layout><EstudiosPage pending /></Layout></ProtectedRoute>} />
      <Route path="/actividad" element={<ProtectedRoute><Layout><ActividadPage /></Layout></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Suspense fallback={<div role="status" className="p-8 text-center">Cargando página…</div>}><AppRoutes /></Suspense>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
