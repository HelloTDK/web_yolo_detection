import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Dashboard from '../views/Dashboard.vue'
import Detection from '../views/Detection.vue'
import History from '../views/History.vue'
import ModelManager from '../views/ModelManager.vue'
import AlertRecord from '../views/AlertRecord.vue'
import WatermarkRemoval from '../views/WatermarkRemoval.vue'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    children: [
      {
        path: '',
        redirect: '/dashboard/detection'
      },
      {
        path: 'detection',
        name: 'Detection',
        component: Detection
      },
      {
        path: 'history',
        name: 'History',
        component: History
      },
      {
        path: 'models',
        name: 'ModelManager',
        component: ModelManager
      },
      {
        path: 'alerts',
        name: 'AlertRecord',
        component: AlertRecord
      },
      {
        path: 'watermark-removal',
        name: 'WatermarkRemoval',
        component: WatermarkRemoval
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('user')
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router 