import {useEffect,useState} from 'react'
import {Link,useNavigate,useParams} from 'react-router-dom'
import {ArrowLeft,FileText,RotateCcw} from 'lucide-react'
import {getEstudio} from '../api/pacientes'
import {getResultado,getGradCAM} from '../api/estudios'
import {errorMessage} from '../api/errors'
import {useAuth} from '../context/useAuth'
import PanelResultados from '../components/scan/PanelResultados'
import {Status} from '../components/ui/WorkspaceUI'
export default function AnalisisPage() {
  const {id}=useParams(), navigate=useNavigate(), {rol}=useAuth()
  const [state,setState]=useState({loading:true,study:null,result:null,error:''})
  const [revision,setRevision]=useState(0), [gradCAM,setGradCAM]=useState(null)
  const [gradLoading,setGradLoading]=useState(false),[gradError,setGradError]=useState(false),[pathology,setPathology]=useState(null)
  useEffect(()=>{
    let active=true
    getEstudio(id).then(async({data:study})=>{
      if(!study.ultima_imagen_id)return {study,result:null}
      const response=await getResultado(study.ultima_imagen_id)
      return {study,result:response.data}
    }).then(({study,result})=>{if(active)setState({loading:false,study,result,error:''})})
      .catch(err=>{if(active)setState({loading:false,study:null,result:null,error:errorMessage(err,'No se pudo recuperar el estudio.')})})
    return ()=>{active=false}
  },[id,revision])
  async function changePathology(name){
    if(!state.study?.ultima_imagen_id)return
    setPathology(name);setGradCAM(null);setGradLoading(true);setGradError(false)
    try {const {data}=await getGradCAM(state.study.ultima_imagen_id,name);setGradCAM(data)}
    catch {setGradError(true)}finally{setGradLoading(false)}
  }
  const {study,result,loading,error}=state
  return <div className="workspace"><header className="page-heading"><div><Link to="/estudios" className="inline-flex items-center gap-2 text-sky-800 text-sm underline underline-offset-4 mb-3"><ArrowLeft size={16}/>Volver a estudios</Link><h1>Análisis del estudio #{id}</h1><p>La interpretación clínica y la firma del informe corresponden al médico.</p></div>{rol==='medico'&&study?.informe_id&&<Link className="btn-primary" to={`/informes/${study.informe_id}`}><FileText size={17}/>Abrir informe</Link>}</header>
    {loading?<div role="status" className="panel empty-state">Cargando radiografía y resultado…</div>:error?<div role="alert" className="error-state">{error}<button className="btn-secondary ml-3" onClick={()=>setRevision(v=>v+1)}>Reintentar</button></div>:<>
      <section className="panel"><div className="panel-heading"><h2>{study.paciente_nombre}</h2><Status value={study.estado}/></div><dl className="grid sm:grid-cols-3 gap-4 p-5 text-sm"><div><dt className="text-slate-600">Tipo de estudio</dt><dd className="font-semibold">{study.tipo_estudio}</dd></div><div><dt className="text-slate-600">Fecha</dt><dd>{study.fecha}</dd></div><div><dt className="text-slate-600">Informe</dt><dd><Status value={study.informe_estado}/></dd></div></dl></section>
      {!study.ultima_imagen_id?<div className="panel empty-state"><h2>Este estudio aún no tiene radiografía</h2><p>Adjunta una imagen para iniciar el análisis.</p>{rol!=='administrador'&&<Link to={`/escaneo?paciente=${study.paciente}`} className="btn-primary mt-4">Cargar radiografía</Link>}</div>:!result?.patologias?<div className="panel empty-state"><h2>Análisis pendiente</h2><p>La imagen está registrada; el resultado todavía no está disponible ({result?.estado_procesamiento||'pendiente'}).</p><button className="btn-secondary mt-4" onClick={()=>setRevision(v=>v+1)}><RotateCcw size={16}/>Actualizar estado</button></div>:<PanelResultados resultado={result} gradCAM={gradCAM} gradCAMCargando={gradLoading} gradCAMError={gradError} estudioId={study.id} informeId={study.informe_id} patologiaSeleccionada={pathology} onPatologiaChange={changePathology} onInformeGenerado={informe=>navigate(`/informes/${informe.id}`)}/>}
    </>}
  </div>
}
