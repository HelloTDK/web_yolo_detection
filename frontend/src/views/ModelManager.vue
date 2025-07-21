<template>
  <div class="model-manager">
    <el-card class="header-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>模型管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="refreshModels" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新列表
            </el-button>
            <el-button type="success" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon>
              上传模型
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 当前模型信息 -->
      <div class="current-model-info">
        <el-alert
          title="当前使用的模型"
          :description="`${currentModel.path} (${currentModel.class_count} 个类别)`"
          type="info"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>

    <!-- 模型列表 -->
    <el-card class="models-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>可用模型列表</span>
          <el-tag type="success">共 {{ models.length }} 个模型</el-tag>
        </div>
      </template>
      
      <el-table :data="models" v-loading="loading" style="width: 100%">
        <el-table-column label="模型名称" min-width="200">
          <template #default="scope">
            <div class="model-name">
              <el-icon v-if="scope.row.pretrained" color="#409EFF"><Star /></el-icon>
              <span>{{ scope.row.name }}</span>
              <el-tag v-if="scope.row.pretrained" type="primary" size="small">预训练</el-tag>
              <el-tag v-if="scope.row.path === currentModel.path" type="success" size="small">当前使用</el-tag>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="size_mb" label="大小" width="100">
          <template #default="scope">
            <span v-if="scope.row.size_mb > 0">{{ scope.row.size_mb }} MB</span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        
        <el-table-column label="路径" min-width="200">
          <template #default="scope">
            <el-text class="model-path" truncated>{{ scope.row.relative_path }}</el-text>
          </template>
        </el-table-column>
        
        <el-table-column label="修改时间" width="180">
          <template #default="scope">
            <span v-if="scope.row.modified > 0">
              {{ formatDate(scope.row.modified) }}
            </span>
            <span v-else>--</span>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button-group>
              <el-button 
                type="primary" 
                size="small" 
                @click="loadModel(scope.row)"
                :disabled="scope.row.path === currentModel.path"
                :loading="loadingModel === scope.row.path"
              >
                <el-icon><Play /></el-icon>
                {{ scope.row.path === currentModel.path ? '使用中' : '加载' }}
              </el-button>
              
              <el-button 
                v-if="!scope.row.pretrained" 
                type="danger" 
                size="small" 
                @click="deleteModel(scope.row)"
                :disabled="scope.row.path === currentModel.path"
              >
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      title="上传模型文件"
      width="600px"
      @close="resetUpload"
    >
      <el-upload
        class="upload-demo"
        drag
        :action="uploadUrl"
        :before-upload="beforeUpload"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :file-list="fileList"
        accept=".pt,.onnx,.torchscript,.engine"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          将模型文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .pt、.onnx、.torchscript、.engine 格式的模型文件，大小不超过 500MB
          </div>
        </template>
      </el-upload>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showUploadDialog = false">取消</el-button>
          <el-button type="primary" @click="showUploadDialog = false">确定</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 模型详情对话框 -->
    <el-dialog
      v-model="showModelDetail"
      title="模型详细信息"
      width="800px"
    >
      <div v-if="selectedModel" class="model-detail">
        <el-descriptions border :column="2">
          <el-descriptions-item label="模型名称">{{ selectedModel.name }}</el-descriptions-item>
          <el-descriptions-item label="文件路径">{{ selectedModel.path }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ selectedModel.size_mb }} MB</el-descriptions-item>
          <el-descriptions-item label="类别数量">{{ currentModel.class_count }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider>支持的检测类别</el-divider>
        <div class="model-classes">
          <el-tag 
            v-for="(className, index) in currentModel.classes" 
            :key="index"
            class="class-tag"
            type="info"
          >
            {{ className }}
          </el-tag>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Upload, 
  Star, 
  Play, 
  Delete, 
  UploadFilled 
} from '@element-plus/icons-vue'

export default {
  name: 'ModelManager',
  components: {
    Refresh,
    Upload,
    Star,
    Play,
    Delete,
    UploadFilled
  },
  data() {
    return {
      models: [],
      currentModel: {
        path: '',
        class_count: 0,
        classes: []
      },
      loading: false,
      loadingModel: '',
      showUploadDialog: false,
      showModelDetail: false,
      selectedModel: null,
      fileList: [],
      uploadUrl: 'http://localhost:5000/api/models/upload'
    }
  },
  mounted() {
    this.loadCurrentModel()
    this.loadModels()
  },
  methods: {
    async loadModels() {
      this.loading = true
      try {
        const response = await fetch('http://localhost:5000/api/models')
        const data = await response.json()
        
        if (data.success) {
          this.models = data.models
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error('加载模型列表失败: ' + error.message)
      } finally {
        this.loading = false
      }
    },
    
    async loadCurrentModel() {
      try {
        const response = await fetch('http://localhost:5000/api/models/current')
        const data = await response.json()
        
        if (data.success) {
          this.currentModel = data.model_info
        }
      } catch (error) {
        console.error('获取当前模型信息失败:', error)
      }
    },
    
    async loadModel(model) {
      this.loadingModel = model.path
      
      try {
        const response = await fetch('http://localhost:5000/api/models/load', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model_path: model.path
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          this.currentModel = data.model_info
          await this.loadModels() // 刷新列表
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error('加载模型失败: ' + error.message)
      } finally {
        this.loadingModel = ''
      }
    },
    
    async deleteModel(model) {
      try {
        await ElMessageBox.confirm(
          `确定要删除模型 "${model.name}" 吗？此操作不可恢复。`,
          '删除确认',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        const response = await fetch('http://localhost:5000/api/models/delete', {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model_path: model.path
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          await this.loadModels()
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除模型失败: ' + error.message)
        }
      }
    },
    
    refreshModels() {
      this.loadCurrentModel()
      this.loadModels()
    },
    
    beforeUpload(file) {
      const isModel = ['pt', 'onnx', 'torchscript', 'engine'].some(ext => 
        file.name.toLowerCase().endsWith('.' + ext)
      )
      const isLt500M = file.size / 1024 / 1024 < 500
      
      if (!isModel) {
        ElMessage.error('只能上传模型文件 (.pt, .onnx, .torchscript, .engine)!')
        return false
      }
      if (!isLt500M) {
        ElMessage.error('模型文件大小不能超过 500MB!')
        return false
      }
      
      return true
    },
    
    handleUploadSuccess(response, file) {
      if (response.success) {
        ElMessage.success('模型上传成功!')
        this.showUploadDialog = false
        this.loadModels()
      } else {
        ElMessage.error(response.message)
      }
    },
    
    handleUploadError(error) {
      ElMessage.error('上传失败: ' + error.message)
    },
    
    resetUpload() {
      this.fileList = []
    },
    
    formatDate(timestamp) {
      return new Date(timestamp * 1000).toLocaleString('zh-CN')
    },
    
    showModelDetails(model) {
      this.selectedModel = model
      this.showModelDetail = true
    }
  }
}
</script>

<style scoped>
.model-manager {
  max-width: 1200px;
  margin: 0 auto;
}

.header-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.current-model-info {
  margin-top: 20px;
}

.models-card {
  margin-bottom: 20px;
}

.model-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-path {
  font-family: monospace;
  font-size: 12px;
}

.model-detail {
  padding: 20px 0;
}

.model-classes {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.class-tag {
  margin: 2px;
}

.upload-demo {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
}

:deep(.el-table .el-button-group) {
  display: flex;
}

:deep(.el-table .el-button-group .el-button) {
  margin-left: 0;
}
</style> 