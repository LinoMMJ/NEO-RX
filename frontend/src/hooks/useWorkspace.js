import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import api from '../api/axios'
import { errorMessage } from '../api/errors'
export function useFilters(defaults = {}) {
  const [params, setParams] = useSearchParams()
  const filters = {...defaults, ...Object.fromEntries(params)}
  const setFilter = (key, value) => setParams(current => {
    const next = new URLSearchParams(current)
    if (value) next.set(key, value); else next.delete(key)
    if (key !== 'page') next.delete('page')
    return next
  }, {replace: true})
  return {filters, setFilter, reset: () => setParams({}, {replace: true})}
}
export function useResource(url, params = {}, revision = 0) {
  const query = new URLSearchParams(Object.entries(params).filter(([,v]) => v !== '' && v != null)).toString()
  const key = `${url}?${query}#${revision}`
  const [state, setState] = useState({key: '', data: null, error: '', loading: true})
  useEffect(() => {
    let active = true
    const controller = new AbortController()
    const timer = setTimeout(() => {
      setState(old => ({...old, key, error: '', loading: true}))
      api.get(`${url}?${query}`, {signal: controller.signal})
        .then(({data}) => {if (active) setState({key, data, error: '', loading: false})})
        .catch(error => {if (active && error.code !== 'ERR_CANCELED') setState({key, data: null, error: errorMessage(error, 'No se pudieron cargar los datos. Intente nuevamente.'), loading: false})})
    }, 250)
    return () => {active = false; clearTimeout(timer); controller.abort()}
  }, [url, query, key])
  return {...state, loading: state.key !== key || state.loading}
}
