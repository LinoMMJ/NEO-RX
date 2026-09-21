import { useEffect, useRef, useState } from 'react'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
export default function Layout({children}) {
  const [open, setOpen] = useState(false)
  const sidebarRef = useRef(null), toggleRef = useRef(null)
  function close() { setOpen(false); toggleRef.current?.focus() }
  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    sidebarRef.current?.querySelector('button, a')?.focus()
    function keyboard(event) {
      if (event.key === 'Escape') { setOpen(false); toggleRef.current?.focus() }
      if (event.key !== 'Tab') return
      const controls = sidebarRef.current?.querySelectorAll('a, button')
      const first = controls?.[0], last = controls?.[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    document.addEventListener('keydown', keyboard)
    return () => { document.body.style.overflow = previous; document.removeEventListener('keydown', keyboard) }
  }, [open])
  return <div className="min-h-screen"><a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:z-[100] focus:bg-white focus:p-4">Ir al contenido</a>
    {open && <button tabIndex={-1} aria-label="Cerrar navegación" onClick={close} className="fixed inset-0 bg-black/40 z-40 lg:hidden"/>}
    <Sidebar open={open} onClose={close} sidebarRef={sidebarRef}/>
    <div className="app-content"><Navbar open={open} toggleRef={toggleRef} onToggle={() => setOpen(v => !v)}/><main id="main-content" className="app-main" tabIndex={-1}>{children}</main></div>
  </div>
}
