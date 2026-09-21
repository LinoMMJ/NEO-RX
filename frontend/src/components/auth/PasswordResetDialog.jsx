import {useEffect,useRef} from 'react'
import PasswordResetFlow from './PasswordResetFlow'
export default function PasswordResetDialog({onClose}) {
  const dialog=useRef(null)
  useEffect(()=>{
    const element=dialog.current
    if (!element.open) element.showModal()
  },[])
  return <dialog ref={dialog} onClose={onClose} onClick={e=>{if(e.target===dialog.current)dialog.current.close()}} aria-label="Recuperar contraseña" className="w-[min(440px,calc(100%-32px))] rounded-xl border border-slate-200 p-0 shadow-xl backdrop:bg-slate-950/60">
    <div className="p-6 sm:p-8"><div className="flex justify-end"><button type="button" className="btn-secondary px-3 mb-4" onClick={()=>dialog.current?.close()} aria-label="Cerrar recuperación">Cerrar</button></div><PasswordResetFlow/></div>
  </dialog>
}
