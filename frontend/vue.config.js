const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  lintOnSave: false,
  devServer: {
    port: 8080,
    open: true,
    // 添加错误处理配置
    client: {
      overlay: {
        errors: true,
        warnings: false,
        runtimeErrors: (error) => {
          // 过滤ResizeObserver错误
          const errorMessage = error.message || ''
          if (errorMessage.includes('ResizeObserver loop completed with undelivered notifications')) {
            return false
          }
          return true
        }
      }
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      },
      '/static': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        secure: false
      }
    }
  },
  publicPath: process.env.NODE_ENV === 'production' ? './' : '/',
  outputDir: 'dist',
  assetsDir: 'static',
  
  // 优化构建配置
  configureWebpack: {
    optimization: {
      // 优化运行时性能
      runtimeChunk: 'single'
    }
  }
}) 