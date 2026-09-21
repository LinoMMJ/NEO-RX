import {useEffect, useState} from 'react'
export default function useObjectUrl(file) {
  const [preview,setPreview]=useState(null)
  useEffect(() => {
    if (!file) return
    const url=URL.createObjectURL(file)
    let active=true
    queueMicrotask(()=>{if(active) setPreview({file,url})})
    return ()=>{active=false;URL.revokeObjectURL(url)}
  },[file])
  return preview?.file === file ? preview.url : null
}
