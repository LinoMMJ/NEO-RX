import { useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { UploadCloud, FileCheck } from 'lucide-react'

export default function ZonaUpload({ onArchivo, archivo }) {
  const inputRef = useRef(null)
  const [drag, setDrag] = useState(false)

  const handleDrop = (e) => {
    e.preventDefault()
    setDrag(false)
    const file = e.dataTransfer.files[0]
    if (file) onArchivo(file)
  }

  return (
    <motion.div
      className={`
        relative rounded-2xl border-2 border-dashed p-8 flex flex-col items-center justify-center
        min-h-[220px] cursor-pointer transition-all duration-200
        ${drag
          ? 'border-teal-med bg-teal-med/5 scale-[1.01]'
          : archivo
            ? 'border-success/60 bg-success/5'
            : 'border-slate-300 hover:border-teal-med/50 bg-slate-50 hover:bg-slate-100'
        }
      `}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      whileHover={{ scale: 1.005 }}
      aria-label="Zona de carga de archivo DICOM"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".dcm,.dicom,.png,.jpg,.jpeg"
        className="hidden"
        onChange={(e) => e.target.files[0] && onArchivo(e.target.files[0])}
      />

      {archivo ? (
        <>
          <FileCheck className="w-12 h-12 text-success mb-3" />
          <p className="font-heading font-semibold text-navy text-base">{archivo.name}</p>
          <p className="font-body text-sm text-slate-500 mt-1">
            {(archivo.size / 1024).toFixed(0)} KB · listo para análisis
          </p>
          <button
            className="mt-3 text-xs text-slate-400 hover:text-danger underline"
            onClick={(e) => { e.stopPropagation(); onArchivo(null) }}
          >
            Cambiar archivo
          </button>
        </>
      ) : (
        <>
          <div className="relative mb-4 w-14 h-14 flex items-center justify-center">
            {/* Halo de pulsación suave en estado idle */}
            {!drag && (
              <motion.span
                className="absolute inset-0 rounded-full bg-teal-med/15"
                animate={{ scale: [1, 1.35, 1], opacity: [0.6, 0, 0.6] }}
                transition={{ repeat: Infinity, duration: 2.4, ease: 'easeInOut' }}
              />
            )}
            <motion.div
              animate={drag ? { scale: 1.15 } : { scale: [1, 1.06, 1] }}
              transition={drag ? { duration: 0.2 } : { repeat: Infinity, duration: 2.4, ease: 'easeInOut' }}
              className="relative w-14 h-14 rounded-full bg-teal-med/10 flex items-center justify-center"
            >
              <UploadCloud className="w-7 h-7 text-teal-med" />
            </motion.div>
          </div>
          <p className="font-heading font-semibold text-navy text-base">
            {drag ? 'Suelta el archivo aquí' : 'Arrastra tu archivo o haz clic'}
          </p>
          <p className="font-body text-sm text-slate-400 mt-1 text-center">
            Formatos aceptados: .dcm · .dicom · .png · .jpg
          </p>
          <p className="font-body text-xs text-slate-400 mt-4 text-center max-w-xs">
            Las imágenes se vinculan al paciente seleccionado.
            El análisis automatizado requiere revisión médica.
          </p>
        </>
      )}
    </motion.div>
  )
}
