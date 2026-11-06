function pause(ms, signal) {
  return new Promise((resolve, reject) => {
    const abort = () => {
      clearTimeout(timer)
      reject(new DOMException('Consulta cancelada', 'AbortError'))
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', abort)
      resolve()
    }, ms)
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}

// Stop polling when the page leaves; transient network failures must not cause
// another upload. The deadline includes time spent waiting for each response.
export async function waitForInference(fetchState, { signal, timeoutMs = 300000, intervalMs = 1000 } = {}) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    await pause(Math.min(intervalMs, deadline - Date.now()), signal)
    if (Date.now() >= deadline) break
    try {
      const { data } = await fetchState(signal)
      signal?.throwIfAborted()
      if (['SUCCESS', 'STORED', 'FAILURE'].includes(data.status)) return data
    } catch (error) {
      if (signal?.aborted) throw error
      if (error.response?.data?.status === 'FAILURE') return error.response.data
      if ([400, 401, 403, 404].includes(error.response?.status)) throw error
      // Offline, throttled or temporarily unavailable: retry within deadline.
    }
  }
  return null
}
