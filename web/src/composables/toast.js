// 极简全局 toast（挂载到 body）
let toastEl = null
export function toast(msg, ms = 2600) {
  if (toastEl) toastEl.remove()
  toastEl = document.createElement('div')
  toastEl.className = 'capy-toast'
  toastEl.textContent = msg
  document.body.appendChild(toastEl)
  setTimeout(() => { toastEl.remove(); toastEl = null }, ms)
}
export function provideToast() { return toast }
