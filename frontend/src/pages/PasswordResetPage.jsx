import {Link} from 'react-router-dom'
import PasswordResetFlow from '../components/auth/PasswordResetFlow'
import ThemeSwitcher from '../components/layout/ThemeSwitcher'
export default function PasswordResetPage() {
  return <main className="public-reset-page min-h-screen bg-slate-50 flex items-center justify-center p-4"><div className="public-theme-control"><ThemeSwitcher/></div><section className="panel w-full max-w-md p-6 sm:p-8"><PasswordResetFlow/><Link className="block text-center text-sky-800 underline underline-offset-4 mt-6" to="/login">Volver a iniciar sesión</Link></section></main>
}
