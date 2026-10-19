import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Archive, ArrowLeft, FileText, RotateCcw } from 'lucide-react'

import { getEstudio } from '../api/pacientes'
import { getResultado } from '../api/estudios'
import useGradCAM from '../hooks/useGradCAM'
import { errorMessage } from '../api/errors'
import { useAuth } from '../context/useAuth'
import PanelResultados from '../components/scan/PanelResultados'
import VisorImagen from '../components/scan/VisorImagen'
import { Status } from '../components/ui/WorkspaceUI'

function RadiografiaGuardada({ result }) {
  return (
    <section className="grid gap-5 lg:grid-cols-[minmax(0,1.15fr)_minmax(280px,.85fr)]">
      <div className="rounded-2xl border border-white/10 bg-scan-bg p-5">
        <VisorImagen
          imagenUrl={result.imagen_png_url}
          esNitida={result.es_nitida}
          varianza={result.varianza_laplaciana}
          analysisEnabled={false}
          altText={`Radiografía de ${result.region_anatomica || 'región no determinada'}`}
        />
      </div>
      <div className="panel overflow-hidden">
        <div className="flex items-start gap-4 bg-sky-50 p-5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-sky-700 text-white">
            <Archive size={21} aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <h2>Radiografía guardada sin CNN</h2>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              La imagen forma parte del expediente, pero no corresponde a un estudio torácico elegible para este modelo.
            </p>
          </div>
        </div>
        <dl className="space-y-4 p-5 text-sm">
          <div>
            <dt className="text-slate-600">Región anatómica</dt>
            <dd className="mt-1 font-semibold text-navy">{result.region_anatomica || 'No determinada'}</dd>
          </div>
          <div>
            <dt className="text-slate-600">Clasificación</dt>
            <dd className="mt-1 font-semibold text-navy">Otra radiografía</dd>
          </div>
          <div>
            <dt className="text-slate-600">Motivo</dt>
            <dd className="mt-1 leading-6 text-slate-700">{result.motivo_no_cnn || 'El modelo está habilitado únicamente para radiografías de tórax.'}</dd>
          </div>
        </dl>
      </div>
    </section>
  )
}

export default function AnalisisPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { rol } = useAuth()
  const [state, setState] = useState({ loading: true, study: null, result: null, error: '' })
  const [revision, setRevision] = useState(0)
  const maps = useGradCAM()
  const { data: gradCAM, loading: gradLoading, error: gradError, pathology } = maps

  useEffect(() => {
    let active = true
    getEstudio(id)
      .then(async ({ data: study }) => {
        if (!study.ultima_imagen_id) return { study, result: null }
        const response = await getResultado(study.ultima_imagen_id)
        return { study, result: response.data }
      })
      .then(({ study, result }) => {
        if (active) setState({ loading: false, study, result, error: '' })
      })
      .catch((error) => {
        if (active) setState({ loading: false, study: null, result: null, error: errorMessage(error, 'No se pudo recuperar el estudio.') })
      })
    return () => { active = false }
  }, [id, revision])

  async function changePathology(name) {
    if (!state.study?.ultima_imagen_id) return
    await maps.load(state.study.ultima_imagen_id, name)
  }

  const { study, result, loading, error } = state
  const storedWithoutCnn = result?.estado_procesamiento === 'sin_analisis' && result?.apta_para_cnn === false

  return (
    <div className="workspace">
      <header className="page-heading">
        <div>
          <Link to="/estudios" className="mb-3 inline-flex items-center gap-2 text-sm text-sky-800 underline underline-offset-4">
            <ArrowLeft size={16} /> Volver a estudios
          </Link>
          <h1>Estudio #{id}</h1>
          <p>La interpretación clínica y la firma del informe corresponden al médico.</p>
        </div>
        {rol === 'medico' && study?.informe_id && (
          <Link className="btn-primary" to={`/informes/${study.informe_id}`}>
            <FileText size={17} /> Abrir informe
          </Link>
        )}
      </header>

      {loading ? (
        <div role="status" className="panel empty-state">Cargando radiografía y resultado…</div>
      ) : error ? (
        <div role="alert" className="error-state">
          {error}
          <button className="btn-secondary ml-3" onClick={() => setRevision((value) => value + 1)}>Reintentar</button>
        </div>
      ) : (
        <>
          <section className="panel">
            <div className="panel-heading"><h2>{study.paciente_nombre}</h2><Status value={study.estado} /></div>
            <dl className="grid gap-4 p-5 text-sm sm:grid-cols-3">
              <div><dt className="text-slate-600">Tipo de estudio</dt><dd className="font-semibold">{study.tipo_estudio}</dd></div>
              <div><dt className="text-slate-600">Fecha</dt><dd>{study.fecha}</dd></div>
              <div><dt className="text-slate-600">Informe</dt><dd><Status value={study.informe_estado} /></dd></div>
            </dl>
          </section>

          {!study.ultima_imagen_id ? (
            <div className="panel empty-state">
              <h2>Este estudio aún no tiene radiografía</h2>
              <p>Adjunta una imagen para iniciar la validación.</p>
              {rol !== 'administrador' && <Link to={`/escaneo?paciente=${study.paciente}`} className="btn-primary mt-4">Cargar radiografía</Link>}
            </div>
          ) : storedWithoutCnn ? (
            <RadiografiaGuardada result={result} />
          ) : !result?.patologias ? (
            <div className="panel empty-state">
              <h2>Análisis pendiente</h2>
              <p>La imagen está registrada; el resultado todavía no está disponible ({result?.estado_procesamiento || 'pendiente'}).</p>
              <button className="btn-secondary mt-4" onClick={() => setRevision((value) => value + 1)}>
                <RotateCcw size={16} /> Actualizar estado
              </button>
            </div>
          ) : (
            <PanelResultados
              resultado={result}
              gradCAM={gradCAM}
              gradCAMCargando={gradLoading}
              gradCAMError={gradError}
              estudioId={study.id}
              informeId={study.informe_id}
              patologiaSeleccionada={pathology}
              onPatologiaChange={changePathology}
              onInformeGenerado={(report) => navigate(`/informes/${report.id}`)}
            />
          )}
        </>
      )}
    </div>
  )
}
