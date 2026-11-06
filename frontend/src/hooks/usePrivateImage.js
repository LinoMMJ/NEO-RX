import { useEffect, useState } from 'react'
import api from '../api/axios'

// Private media requires JWT; render an authenticated Blob URL instead of public URLs.
export default function usePrivateImage(source) {
  const [image, setImage] = useState(null)
  useEffect(() => {
    let active = true
    let objectUrl
    const controller = new AbortController()
    if (!source) return
    if (source.startsWith('blob:') || source.startsWith('data:image/')) {
      return
    }
    const backend = new URL(api.defaults.baseURL || '/api/', window.location.href)
    const target = new URL(source, backend.origin)
    // La API puede responder localhost, 127.0.0.1 o el host del proxy. Solo
    // conservamos la ruta privada /media/ y la solicitamos al origen configurado.
    if (!target.pathname.startsWith('/media/')) return
    const authenticatedUrl = `${backend.origin}${target.pathname}${target.search}`
    api.get(authenticatedUrl, { responseType: 'blob', signal: controller.signal })
      .then(({ data }) => {
        if (!active) return
        objectUrl = URL.createObjectURL(data)
        setImage({source, url: objectUrl})
      })
      .catch(() => { if (active) setImage(null) })
    return () => {
      active = false
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [source])
  if (source?.startsWith('blob:') || source?.startsWith('data:image/')) return source
  return image?.source === source ? image.url : null
}
