import { useCallback, useEffect, useRef, useState } from 'react'
import { getGradCAM } from '../api/estudios'

export default function useGradCAM() {
  const [state, setState] = useState({ data: null, loading: false, error: false, pathology: null })
  const cache = useRef(new Map())
  const pending = useRef(null)
  useEffect(() => () => pending.current?.abort(), [])

  const load = useCallback(async (imageId, pathology) => {
    if (!imageId || !pathology) return
    const key = `${imageId}:${pathology}`
    if (pending.current?.key === key) return
    pending.current?.abort()
    const controller = new AbortController()
    controller.key = key
    pending.current = controller
    if (cache.current.has(key)) {
      setState({ data: cache.current.get(key), loading: false, error: false, pathology })
      pending.current = null
      return
    }
    setState({ data: null, loading: true, error: false, pathology })
    try {
      const { data } = await getGradCAM(imageId, pathology, controller.signal)
      if (controller.signal.aborted) return
      cache.current.set(key, data)
      if (cache.current.size > 12) cache.current.delete(cache.current.keys().next().value)
      setState({ data, loading: false, error: false, pathology })
    } catch {
      if (!controller.signal.aborted) setState({ data: null, loading: false, error: true, pathology })
    } finally {
      if (pending.current === controller) pending.current = null
    }
  }, [])

  const reset = useCallback(() => {
    pending.current?.abort()
    pending.current = null
    cache.current.clear()
    setState({ data: null, loading: false, error: false, pathology: null })
  }, [])
  return { ...state, load, reset }
}
