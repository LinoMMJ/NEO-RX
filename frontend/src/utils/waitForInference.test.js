import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { waitForInference } from './waitForInference'

describe('seguimiento del escaneo', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it.each(['SUCCESS', 'STORED', 'FAILURE'])('termina al recibir %s', async (status) => {
    const fetch = vi.fn().mockResolvedValueOnce({ data: { status: 'STARTED' } }).mockResolvedValue({ data: { status } })
    const result = waitForInference(fetch)
    await vi.advanceTimersByTimeAsync(2000)
    expect(await result).toEqual({ status })
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('tolera un error de red sin volver a subir la imagen', async () => {
    const fetch = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ data: { status: 'SUCCESS' } })
    const result = waitForInference(fetch)
    await vi.advanceTimersByTimeAsync(2000)
    expect((await result).status).toBe('SUCCESS')
  })

  it('cancela las consultas al salir de la pantalla', async () => {
    const controller = new AbortController()
    const fetch = vi.fn()
    const result = waitForInference(fetch, { signal: controller.signal }).catch(error => error)
    controller.abort()
    await vi.runAllTimersAsync()
    expect((await result).name).toBe('AbortError')
    expect(fetch).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('termina en el plazo definido aunque la tarea siga pendiente', async () => {
    const fetch = vi.fn().mockResolvedValue({ data: { status: 'PENDING' } })
    const result = waitForInference(fetch, { timeoutMs: 3000 })
    await vi.advanceTimersByTimeAsync(3000)
    expect(await result).toBeNull()
    expect(fetch).toHaveBeenCalledTimes(2)
  })

  it('no reintenta una tarea inexistente ni permisos rechazados', async () => {
    const error = { response: { status: 404 } }
    const fetch = vi.fn().mockRejectedValue(error)
    const result = waitForInference(fetch).catch(value => value)
    await vi.advanceTimersByTimeAsync(1000)
    expect(await result).toBe(error)
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('interpreta FAILURE aun si viene con HTTP 500', async () => {
    const failure = { status: 'FAILURE', error: 'Modelo no disponible' }
    const result = waitForInference(vi.fn().mockRejectedValue({ response: { status: 500, data: failure } }))
    await vi.advanceTimersByTimeAsync(1000)
    expect(await result).toEqual(failure)
  })
})
