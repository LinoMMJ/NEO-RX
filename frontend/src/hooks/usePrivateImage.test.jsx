import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import api from '../api/axios'
import usePrivateImage from './usePrivateImage'

vi.mock('../api/axios', () => ({
  default: {
    defaults: { baseURL: 'http://localhost:8000/api' },
    get: vi.fn(),
  },
}))

describe('usePrivateImage', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', class extends globalThis.URL {
      static createObjectURL = vi.fn(() => 'blob:private-image')
      static revokeObjectURL = vi.fn()
    })
  })

  it('solicita la ruta privada al origen configurado aunque la API devuelva otro host', async () => {
    api.get.mockResolvedValue({ data: new Blob(['image'], { type: 'image/png' }) })

    const { result } = renderHook(() => usePrivateImage('http://127.0.0.1:8000/media/png/example.png'))

    await waitFor(() => expect(result.current).toBe('blob:private-image'))
    expect(api.get).toHaveBeenCalledWith(
      'http://localhost:8000/media/png/example.png',
      expect.objectContaining({ responseType: 'blob' }),
    )
  })

  it('no envía credenciales para rutas que no pertenecen al almacén privado', () => {
    const { result } = renderHook(() => usePrivateImage('https://example.com/image.png'))

    expect(result.current).toBeNull()
    expect(api.get).not.toHaveBeenCalled()
  })
})
