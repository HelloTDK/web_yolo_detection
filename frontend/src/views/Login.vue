<template>
  <div class="login-container">
    <div class="login-card">
      <div class="system-title">
        <h1>【YOLO检测识别系统】</h1>
      </div>
      
      <div class="login-form-container">
        <div class="form-header">
          <h2>基于YOLO识别的检测系统</h2>
          <p class="subtitle">YOLOv11 based Crop Disease and Pest Detection System</p>
        </div>
        
        <el-form 
          ref="loginForm" 
          :model="loginData" 
          :rules="rules" 
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginData.username"
              placeholder="请输入用户名"
              prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>
          
          <el-form-item prop="password">
            <el-input
              v-model="loginData.password"
              type="password"
              placeholder="请输入密码"
              prefix-icon="Lock"
              size="large"
              show-password
              clearable
            />
          </el-form-item>
          
          <el-form-item>
            <el-button 
              type="primary" 
              size="large" 
              class="login-button"
              :loading="$store.state.isLoading"
              @click="handleLogin"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>
        
        <div class="form-footer">
          <el-link @click="showRegister = true">注册账号</el-link>
          <el-link>忘记密码</el-link>
        </div>
        
        <div class="footer-info">
          <p></p>
        </div>
      </div>
    </div>
    
    <!-- 注册对话框 -->
    <el-dialog v-model="showRegister" title="用户注册" width="400px">
      <el-form 
        ref="registerForm" 
        :model="registerData" 
        :rules="registerRules"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="registerData.username" placeholder="请输入用户名" />
        </el-form-item>
        
        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="registerData.password" 
            type="password" 
            placeholder="请输入密码" 
            show-password 
          />
        </el-form-item>
        
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input 
            v-model="registerData.confirmPassword" 
            type="password" 
            placeholder="请确认密码" 
            show-password 
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showRegister = false">取消</el-button>
        <el-button 
          type="primary" 
          :loading="$store.state.isLoading"
          @click="handleRegister"
        >
          注册
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'

export default {
  name: 'Login',
  data() {
    const validatePassword = (rule, value, callback) => {
      if (value === '') {
        callback(new Error('请输入密码'))
      } else if (value.length < 6) {
        callback(new Error('密码长度不能少于6位'))
      } else {
        callback()
      }
    }
    
    const validateConfirmPassword = (rule, value, callback) => {
      if (value === '') {
        callback(new Error('请确认密码'))
      } else if (value !== this.registerData.password) {
        callback(new Error('两次输入的密码不一致'))
      } else {
        callback()
      }
    }
    
    return {
      loginData: {
        username: '',
        password: ''
      },
      registerData: {
        username: '',
        password: '',
        confirmPassword: ''
      },
      showRegister: false,
      rules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' }
        ],
        password: [
          { required: true, validator: validatePassword, trigger: 'blur' }
        ]
      },
      registerRules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 3, max: 20, message: '用户名长度在3到20个字符', trigger: 'blur' }
        ],
        password: [
          { required: true, validator: validatePassword, trigger: 'blur' }
        ],
        confirmPassword: [
          { required: true, validator: validateConfirmPassword, trigger: 'blur' }
        ]
      }
    }
  },
  mounted() {
    // 如果已经登录则直接跳转
    if (this.$store.getters.isAuthenticated) {
      this.$router.push('/dashboard')
    }
    
    // 初始化认证状态
    this.$store.dispatch('initializeAuth')
  },
  methods: {
    async handleLogin() {
      try {
        await this.$refs.loginForm.validate()
        const result = await this.$store.dispatch('login', this.loginData)
        
        if (result.success) {
          ElMessage.success(result.message)
          this.$router.push('/dashboard')
        } else {
          ElMessage.error(result.message)
        }
      } catch (error) {
        console.error('登录失败:', error)
      }
    },
    
    async handleRegister() {
      try {
        await this.$refs.registerForm.validate()
        const result = await this.$store.dispatch('register', {
          username: this.registerData.username,
          password: this.registerData.password
        })
        
        if (result.success) {
          ElMessage.success(result.message)
          this.showRegister = false
          this.registerData = { username: '', password: '', confirmPassword: '' }
        } else {
          ElMessage.error(result.message)
        }
      } catch (error) {
        console.error('注册失败:', error)
      }
    }
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: rgba(255, 255, 255, 0.95);
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(10px);
  overflow: hidden;
  width: 100%;
  max-width: 450px;
}

.system-title {
  background: linear-gradient(135deg, #ff6b6b, #ff8e53);
  color: white;
  text-align: center;
  padding: 20px;
  margin: 0;
}

.system-title h1 {
  margin: 0;
  font-size: 24px;
  font-weight: bold;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.login-form-container {
  padding: 40px;
}

.form-header {
  text-align: center;
  margin-bottom: 30px;
}

.form-header h2 {
  color: #333;
  font-size: 18px;
  margin-bottom: 10px;
  font-weight: 600;
}

.subtitle {
  color: #666;
  font-size: 12px;
  margin: 0;
}

.login-form {
  margin-bottom: 20px;
}

.login-button {
  width: 100%;
  height: 45px;
  font-size: 16px;
  font-weight: 600;
  background: linear-gradient(135deg, #667eea, #764ba2);
  border: none;
  border-radius: 8px;
}

.login-button:hover {
  background: linear-gradient(135deg, #5a6fd8, #6a42a0);
}

.form-footer {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
}

.footer-info {
  text-align: center;
  color: #999;
  font-size: 12px;
}

:deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.el-input__inner) {
  height: 45px;
  line-height: 45px;
}
</style> 