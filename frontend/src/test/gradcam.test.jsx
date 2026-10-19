import { act, renderHook } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import useGradCAM from '../hooks/useGradCAM'
import { getGradCAM } from '../api/estudios'
import { formatModelScore } from '../utils/modelScore'

vi.mock('../api/estudios', () => ({ getGradCAM: vi.fn() }))

it('ignores an older heatmap response after the selected pathology changes', async () => {
  const deferred = []
  getGradCAM.mockImplementation(() => new Promise((resolve) => deferred.push(resolve)))
  const { result } = renderHook(() => useGradCAM())
  let first, second
  act(() => { first = result.current.load(1, 'Mass') })
  act(() => { second = result.current.load(1, 'Nodule') })
  await act(async () => { deferred[1]({ data: { patologia: 'Nodule' } }); await second })
  await act(async () => { deferred[0]({ data: { patologia: 'Mass' } }); await first })
  expect(result.current.data.patologia).toBe('Nodule')
  await act(async () => { await result.current.load(1, 'Nodule') })
  expect(getGradCAM).toHaveBeenCalledTimes(2)
})

it('deduplicates clicks and permits retry after failure', async () => {
  let reject
  getGradCAM.mockImplementationOnce(() => new Promise((resolve, fail) => { reject = fail }))
  const { result } = renderHook(() => useGradCAM())
  let pending
  act(() => { pending = result.current.load(2, 'Mass'); result.current.load(2, 'Mass') })
  expect(getGradCAM).toHaveBeenCalledTimes(1)
  await act(async () => { reject(new Error('network')); await pending })
  expect(result.current.error).toBe(true)
  getGradCAM.mockResolvedValueOnce({ data: { patologia: 'Mass' } })
  await act(async () => { await result.current.load(2, 'Mass') })
  expect(result.current.error).toBe(false)
})

it('does not round a high score into diagnostic certainty', () => {
  expect(formatModelScore(0.996)).toBe('99.6/100')
  expect(formatModelScore(1)).toBe('≥99.9/100')
  expect(formatModelScore(Number.NaN)).toBe('—')
})
