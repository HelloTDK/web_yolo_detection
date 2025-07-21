<template>
  <div class="dashboard-container">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="250px" class="sidebar">
        <div class="logo">
          <h2>🔍 检测系统</h2>
        </div>
        
        <el-menu
          :default-active="$route.path"
          router
          background-color="#2c3e50"
          text-color="#ecf0f1"
          active-text-color="#3498db"
          class="sidebar-menu"
        >
          <el-menu-item index="/dashboard/detection">
            <el-icon><Camera /></el-icon>
            <span>目标检测</span>
          </el-menu-item>
          
          <el-menu-item index="/dashboard/history">
            <el-icon><Clock /></el-icon>
            <span>检测历史</span>
          </el-menu-item>
          
          <el-menu-item index="/dashboard/alerts">
            <el-icon><Warning /></el-icon>
            <span>预警记录</span>
          </el-menu-item>
          
          <el-menu-item index="/dashboard/models">
            <el-icon><Setting /></el-icon>
            <span>模型管理</span>
          </el-menu-item>
          
          <el-menu-item @click="handleLogout">
            <el-icon><SwitchButton /></el-icon>
            <span>退出登录</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <!-- 主内容区域 -->
      <el-container>
        <!-- 顶部导航 -->
        <el-header class="header">
          <div class="header-left">
            <h3>{{ getPageTitle() }}</h3>
          </div>
          <div class="header-right">
            <el-dropdown>
              <span class="user-info">
                <el-icon><User /></el-icon>
                {{ $store.getters.currentUser?.username || '用户' }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleLogout">
                    <el-icon><SwitchButton /></el-icon>
                    退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>
        
        <!-- 主内容 -->
        <el-main class="main-content">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script>
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Camera, 
  Clock, 
  SwitchButton, 
  User, 
  ArrowDown,
  Setting,
  Warning
} from '@element-plus/icons-vue'

export default {
  name: 'Dashboard',
  components: {
    Camera,
    Clock,
    SwitchButton,
    User,
    ArrowDown,
    Setting,
    Warning
  },
  mounted() {
    // 初始化认证状态
    this.$store.dispatch('initializeAuth')
    
    // 检查登录状态
    if (!this.$store.getters.isAuthenticated) {
      this.$router.push('/login')
    }
  },
  methods: {
    getPageTitle() {
      const routeMap = {
        '/dashboard/detection': '目标检测',
        '/dashboard/history': '检测历史',
        '/dashboard/alerts': '预警记录',
        '/dashboard/models': '模型管理'
      }
      return routeMap[this.$route.path] || '检测系统'
    },
    
    async handleLogout() {
      try {
        await ElMessageBox.confirm(
          '确定要退出登录吗？',
          '提示',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        this.$store.dispatch('logout')
        ElMessage.success('已退出登录')
        this.$router.push('/login')
      } catch {
        // 用户取消操作
      }
    }
  }
}
</script>

<style scoped>
.dashboard-container {
  height: 100vh;
  background: #f5f7fa;
}

.sidebar {
  background: #2c3e50;
  box-shadow: 2px 0 6px rgba(0, 0, 0, 0.1);
}

.logo {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid #34495e;
}

.logo h2 {
  color: #ecf0f1;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.sidebar-menu {
  border: none;
}

:deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
  margin: 5px 10px;
  border-radius: 8px;
}

:deep(.el-menu-item:hover) {
  background-color: #34495e !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #3498db !important;
  color: white !important;
}

.header {
  background: white;
  border-bottom: 1px solid #e8eaec;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.header-left h3 {
  margin: 0;
  color: #2c3e50;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 6px;
  transition: background-color 0.3s;
  color: #606266;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.main-content {
  background: #f5f7fa;
  padding: 20px;
  overflow-y: auto;
}

:deep(.el-container) {
  height: 100vh;
}

:deep(.el-header) {
  height: 65px !important;
}

:deep(.el-aside) {
  height: 100vh;
}
</style> 