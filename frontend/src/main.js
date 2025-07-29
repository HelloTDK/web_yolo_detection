import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import store from './store'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

// 全局错误处理 - 静默处理ResizeObserver错误
const resizeObserverErrHandler = (error) => {
  if (error && error.message && error.message.includes('ResizeObserver loop completed with undelivered notifications')) {
    // 静默处理ResizeObserver错误，这是一个已知的非关键性错误
    return false
  }
  // 其他错误正常处理
  console.error('Global error:', error)
  return true
}

// 监听未捕获的错误
window.addEventListener('error', (event) => {
  resizeObserverErrHandler(event.error)
})

// 监听未处理的Promise拒绝
window.addEventListener('unhandledrejection', (event) => {
  if (resizeObserverErrHandler(event.reason)) {
    // 如果不是ResizeObserver错误，则正常处理
    console.error('Unhandled promise rejection:', event.reason)
  }
})

const app = createApp(App)

// 注册Element Plus图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(store)
app.use(router)
app.use(ElementPlus, {
  locale: zhCn,
})

app.mount('#app') 