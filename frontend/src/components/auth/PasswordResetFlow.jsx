import {useEffect, useRef, useState} from 'react'
import {CheckCircle2, Mail, ShieldCheck, KeyRound} from 'lucide-react'
import {requestPasswordReset, verifyPasswordReset, confirmPasswordReset} from '../../api/auth'
import {clearSession} from '../../api/session'
import {errorMessage} from '../../api/errors'

export default function PasswordResetFlow({onDone}) {
  const [step,setStep]=useState('email'), [email,setEmail]=useState(''), [code,setCode]=useState('')
  const [proof,setProof]=useState(''), [password,setPassword]=useState(''), [confirmation,setConfirmation]=useState('')
  const [busy,setBusy]=useState(false), [error,setError]=useState(''), [notice,setNotice]=useState('')
  const field=useRef(null)
  useEffect(()=>{field.current?.focus()},[step])
  const resetFeedback=()=>{setError('');setNotice('')}
  async function send(event) {
    event?.preventDefault();resetFeedback();setBusy(true)
    try {
      const normalized=email.trim()
      const {data}=await requestPasswordReset(normalized)
      setEmail(normalized);setCode('');setProof('');setNotice(data.message);setStep('code')
    } catch(err) {setError(errorMessage(err,'No se pudo enviar el código. Intenta nuevamente.'))}
    finally {setBusy(false)}
  }
  async function verify(event) {
    event.preventDefault();resetFeedback()
    if(!/^\d{6}$/.test(code)){setError('Ingresa los seis dígitos del código recibido.');return}
    setBusy(true)
    try {const {data}=await verifyPasswordReset(email,code);setProof(data.reset_proof);setCode('');setNotice(data.message);setStep('password')}
    catch(err){setError(errorMessage(err,'El código no es válido. Solicita uno nuevo.'))}
    finally{setBusy(false)}
  }
  async function change(event) {
    event.preventDefault();resetFeedback()
    if(password!==confirmation){setError('Las contraseñas no coinciden.');return}
    setBusy(true)
    try {await confirmPasswordReset(email,proof,password);clearSession();setProof('');setPassword('');setConfirmation('');setStep('done');onDone?.()}
    catch(err){setError(errorMessage(err,'No se pudo cambiar la contraseña.'))}
    finally{setBusy(false)}
  }
  return <div className="space-y-5">
    <div className="flex items-center gap-3 text-navy">{step==='email'?<Mail size={24}/>:step==='code'?<ShieldCheck size={24}/>:step==='password'?<KeyRound size={24}/>:<CheckCircle2 size={24}/>}
      <h2 className="font-heading text-2xl font-bold">{step==='email'?'Recuperar contraseña':step==='code'?'Verifica tu correo':step==='password'?'Nueva contraseña':'Contraseña actualizada'}</h2></div>
    <p className="text-sm text-slate-600">{step==='email'?'Usa el correo de tu cuenta creada por el administrador.':step==='code'?`Escribe el código de seis dígitos enviado a ${email}. Vence en 10 minutos.`:step==='password'?'El código fue validado. Elige una contraseña segura.':'Ya puedes iniciar sesión con tu contraseña nueva.'}</p>
    {error&&<p role="alert" className="error-state text-sm">{error}</p>}
    {notice&&step!=='done'&&<p role="status" className="bg-emerald-50 text-emerald-900 rounded-lg p-3 text-sm">{notice}</p>}
    {step==='email'&&<form onSubmit={send} className="space-y-4"><div><label htmlFor="reset-email" className="label">Correo electrónico registrado</label><input ref={field} id="reset-email" className="input" type="email" autoComplete="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div><button disabled={busy} className="btn-primary w-full">{busy?'Enviando…':'Enviar código'}</button></form>}
    {step==='code'&&<form onSubmit={verify} className="space-y-4"><div><label htmlFor="reset-code" className="label">Código de seis dígitos</label><input ref={field} id="reset-code" className="input text-center text-xl tracking-[.35em] tabular-nums" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,'').slice(0,6))} required/></div><button disabled={busy} className="btn-primary w-full">{busy?'Verificando…':'Verificar código'}</button><div className="flex flex-wrap justify-between gap-2 text-sm"><button type="button" className="text-sky-800 underline underline-offset-4" onClick={()=>{resetFeedback();setStep('email')}}>Cambiar correo</button><button type="button" disabled={busy} className="text-sky-800 underline underline-offset-4" onClick={()=>send()}>Reenviar código</button></div></form>}
    {step==='password'&&<form onSubmit={change} className="space-y-4"><div><label htmlFor="reset-password" className="label">Nueva contraseña</label><input ref={field} id="reset-password" className="input" type="password" autoComplete="new-password" minLength={8} value={password} onChange={e=>setPassword(e.target.value)} required/></div><div><label htmlFor="reset-confirm" className="label">Confirmar contraseña</label><input id="reset-confirm" className="input" type="password" autoComplete="new-password" minLength={8} value={confirmation} onChange={e=>setConfirmation(e.target.value)} required/></div><button disabled={busy} className="btn-primary w-full">{busy?'Guardando…':'Guardar contraseña'}</button></form>}
    {step==='done'&&<a className="btn-primary w-full" href="/login">Ir a iniciar sesión</a>}
  </div>
}
