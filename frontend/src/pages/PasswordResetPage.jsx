import {Link} from 'react-router-dom'
import PasswordResetFlow from '../components/auth/PasswordResetFlow'
export default function PasswordResetPage() {
  return <main className="min-h-screen bg-slate-50 flex items-center justify-center p-4"><section className="panel w-full max-w-md p-6 sm:p-8"><PasswordResetFlow/><Link className="block text-center text-sky-800 underline underline-offset-4 mt-6" to="/login">Volver a iniciar sesión</Link></section></main>
}
