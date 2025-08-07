<template>
  <div class="model-manager">
    <el-card class="header-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>模型与轮询管理</span>
          <div class="header-actions">
            <el-button type="primary" @click="refreshCurrentTab" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 标签页 -->
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 模型管理标签页 -->
        <el-tab-pane label="模型管理" name="models">
          <!-- 当前模型信息 -->
          <div class="current-model-info" style="margin-bottom: 20px;">
            <el-alert
              title="当前使用的模型"
              :description="`${currentModel.path} (${currentModel.class_count} 个类别)`"
              type="info"
              show-icon
              :closable="false"
            />
          </div>
          
          <!-- 操作按钮 -->
          <div class="tab-actions">
            <el-button type="success" @click="showUploadDialog = true">
              <el-icon><Upload /></el-icon>
              上传模型
            </el-button>
          </div>
          
          <!-- 模型列表 -->
          <el-table :data="models" v-loading="loading" style="width: 100%; margin-top: 20px;">
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
                    <el-icon><VideoPlay /></el-icon>
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
        </el-tab-pane>
        
        <!-- 轮询配置标签页 -->
        <el-tab-pane label="轮询配置" name="polling">
          <!-- 操作按钮 -->
          <div class="tab-actions">
            <el-button type="primary" @click="showCreatePollingDialog = true">
              <el-icon><Plus /></el-icon>
              创建轮询配置
            </el-button>
            <el-button type="warning" @click="testPollingConfig" :disabled="selectedPollingModels.length === 0">
              <el-icon><ChatDotRound /></el-icon>
              测试配置
            </el-button>
          </div>
          
          <!-- 轮询配置列表 -->
          <el-table :data="pollingConfigs" v-loading="pollingLoading" style="width: 100%; margin-top: 20px;">
            <el-table-column label="配置名称" min-width="150">
              <template #default="scope">
                <div>
                  <span>{{ scope.row.name }}</span>
                  <el-tag v-if="!scope.row.is_active" type="info" size="small" style="margin-left: 8px;">已禁用</el-tag>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column label="轮询模式" width="120">
              <template #default="scope">
                <el-tag :type="scope.row.polling_type === 'frame' ? 'primary' : 'success'">
                  {{ scope.row.polling_type === 'frame' ? '按帧数' : '按时间' }}
                </el-tag>
              </template>
            </el-table-column>
            
            <el-table-column label="间隔" width="100">
              <template #default="scope">
                {{ scope.row.interval_value }}{{ scope.row.polling_type === 'frame' ? '帧' : '秒' }}
              </template>
            </el-table-column>
            
            <el-table-column label="模型数量" width="100">
              <template #default="scope">
                {{ scope.row.model_paths.length }} 个
              </template>
            </el-table-column>
            
            <el-table-column label="模型列表" min-width="200">
              <template #default="scope">
                <div class="model-list">
                  <el-tag 
                    v-for="(model, index) in scope.row.model_paths.slice(0, 3)" 
                    :key="index"
                    size="small"
                    style="margin-right: 4px; margin-bottom: 4px;"
                  >
                    {{ getModelName(model) }}
                  </el-tag>
                  <el-tag v-if="scope.row.model_paths.length > 3" size="small" type="info">
                    +{{ scope.row.model_paths.length - 3 }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column label="创建时间" width="150">
              <template #default="scope">
                {{ formatDate(scope.row.created_at) }}
              </template>
            </el-table-column>
            
            <el-table-column label="操作" width="200">
              <template #default="scope">
                <el-button-group>
                  <el-button size="small" @click="editPollingConfig(scope.row)">
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button 
                    size="small" 
                    type="danger" 
                    @click="deletePollingConfig(scope.row)"
                  >
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 上传模型对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传模型文件" width="600px">
      <el-upload
        ref="upload"
        class="upload-demo"
        drag
        :action="uploadUrl"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :file-list="fileList"
        :auto-upload="false"
        accept=".pt,.onnx,.torchscript"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">
          将模型文件拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .pt、.onnx、.torchscript 格式的模型文件
          </div>
        </template>
      </el-upload>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showUploadDialog = false">取消</el-button>
          <el-button type="primary" @click="submitUpload">确定上传</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 创建/编辑轮询配置对话框 -->
    <el-dialog 
      v-model="showCreatePollingDialog" 
      :title="editingPollingConfig ? '编辑轮询配置' : '创建轮询配置'" 
      width="800px"
    >
      <el-form :model="pollingForm" :rules="pollingRules" ref="pollingFormRef" label-width="100px">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="pollingForm.name" placeholder="请输入配置名称" />
        </el-form-item>
        
        <el-form-item label="轮询模式" prop="polling_type">
          <el-radio-group v-model="pollingForm.polling_type">
            <el-radio value="frame">按帧数轮询</el-radio>
            <el-radio value="time">按时间轮询</el-radio>
          </el-radio-group>
        </el-form-item>
        
        <el-form-item label="轮询间隔" prop="interval_value">
          <el-input-number 
            v-model="pollingForm.interval_value" 
            :min="1" 
            :max="pollingForm.polling_type === 'frame' ? 100 : 300"
            :step="pollingForm.polling_type === 'frame' ? 1 : 5"
          />
          <span style="margin-left: 8px; color: #606266;">
            {{ pollingForm.polling_type === 'frame' ? '帧' : '秒' }}
          </span>
        </el-form-item>
        
        <el-form-item label="选择模型" prop="model_paths">
          <div style="width: 100%;">
            <el-select
              v-model="selectedPollingModels"
              multiple
              placeholder="请选择要轮询的模型（最多10个）"
              style="width: 100%; margin-bottom: 10px;"
              :multiple-limit="10"
            >
              <el-option
                v-for="model in models"
                :key="model.path"
                :label="model.name"
                :value="model.path"
              >
                <span style="float: left">{{ model.name }}</span>
                <span style="float: right; color: #8492a6; font-size: 13px">
                  {{ model.pretrained ? '预训练' : '自定义' }}
                </span>
              </el-option>
            </el-select>
            
            <!-- 轮询顺序调整 -->
            <div v-if="selectedPollingModels.length > 1" style="margin-top: 10px;">
              <label style="font-size: 14px; margin-bottom: 8px; display: block;">轮询顺序（可拖拽调整）:</label>
              <div class="polling-order-list">
                <div 
                  v-for="(modelPath, index) in selectedPollingModels"
                  :key="modelPath"
                  class="polling-order-item"
                  draggable="true"
                  @dragstart="dragStart(index)"
                  @dragover.prevent
                  @drop="dragDrop(index)"
                >
                  <span class="order-number">{{ index + 1 }}</span>
                  <span class="model-name">{{ getModelName(modelPath) }}</span>
                  <el-button-group class="order-actions">
                    <el-button 
                      size="small" 
                      @click="moveUp(index)"
                      :disabled="index === 0"
                    >
                      <el-icon><ArrowUp /></el-icon>
                    </el-button>
                    <el-button 
                      size="small" 
                      @click="moveDown(index)"
                      :disabled="index === selectedPollingModels.length - 1"
                    >
                      <el-icon><ArrowDown /></el-icon>
                    </el-button>
                  </el-button-group>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>
        
        <el-form-item label="描述">
          <el-input 
            v-model="pollingForm.description" 
            type="textarea" 
            :rows="3"
            placeholder="请输入配置描述（可选）"
          />
        </el-form-item>
        
        <el-form-item label="状态">
          <el-switch v-model="pollingForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="cancelPollingForm">取消</el-button>
          <el-button type="primary" @click="savePollingConfig" :loading="pollingLoading">
            {{ editingPollingConfig ? '更新' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 模型详情对话框 -->
    <el-dialog v-model="showModelDetail" title="模型详情" width="600px">
      <div class="model-detail" v-if="selectedModel">
        <el-descriptions :column="1" border>
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
  VideoPlay, 
  Delete, 
  UploadFilled,
  Plus,
  Edit,
  ChatDotRound,
  ArrowUp,
  ArrowDown
} from '@element-plus/icons-vue'

export default {
  name: 'ModelManager',
  components: {
    Refresh,
    Upload,
    Star,
    VideoPlay,
    Delete,
    UploadFilled,
    Plus,
    Edit,
    ChatDotRound,
    ArrowUp,
    ArrowDown
  },
  data() {
    return {
      activeTab: 'models',
      
      // 模型相关
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
      uploadUrl: 'http://localhost:5000/api/models/upload',
      
      // 轮询配置相关
      pollingConfigs: [],
      pollingLoading: false,
      showCreatePollingDialog: false,
      editingPollingConfig: null,
      selectedPollingModels: [],
      dragFromIndex: -1,
      
      pollingForm: {
        name: '',
        polling_type: 'frame',
        interval_value: 10,
        model_paths: [],
        model_order: [],
        description: '',
        is_active: true
      },
      
      pollingRules: {
        name: [
          { required: true, message: '请输入配置名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        polling_type: [
          { required: true, message: '请选择轮询模式', trigger: 'change' }
        ],
        interval_value: [
          { required: true, message: '请输入轮询间隔', trigger: 'blur' },
          { type: 'number', min: 1, message: '间隔必须大于0', trigger: 'blur' }
        ],
        model_paths: [
          { required: true, message: '请至少选择一个模型', trigger: 'change' }
        ]
      }
    }
  },
  mounted() {
    this.loadCurrentModel()
    this.loadModels()
    this.loadPollingConfigs()
  },
  watch: {
    selectedPollingModels(newVal) {
      this.pollingForm.model_paths = [...newVal]
      this.pollingForm.model_order = newVal.map((_, index) => index)
    }
  },
  methods: {
    // 标签页相关
    refreshCurrentTab() {
      if (this.activeTab === 'models') {
        this.loadModels()
        this.loadCurrentModel()
      } else if (this.activeTab === 'polling') {
        this.loadPollingConfigs()
      }
    },
    
    // 模型相关方法（保持原有逻辑）
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
          ElMessage.success('模型加载成功')
          await this.loadCurrentModel()
          await this.loadModels()
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
          '确认删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
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
          ElMessage.success('模型删除成功')
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
    
    // 轮询配置相关方法
    async loadPollingConfigs() {
      this.pollingLoading = true
      try {
        // 修复：统一使用store中的用户ID
        const userId = this.$store.getters.currentUser?.id || 1
        const response = await fetch(`http://localhost:5000/api/polling/configs?user_id=${userId}`)
        const data = await response.json()
        
        if (data.success) {
          this.pollingConfigs = data.configs
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error('加载轮询配置失败: ' + error.message)
      } finally {
        this.pollingLoading = false
      }
    },
    
    editPollingConfig(config) {
      this.editingPollingConfig = config
      this.pollingForm = {
        name: config.name,
        polling_type: config.polling_type,
        interval_value: config.interval_value,
        model_paths: [...config.model_paths],
        model_order: [...config.model_order],
        description: config.description || '',
        is_active: config.is_active
      }
      this.selectedPollingModels = [...config.model_paths]
      this.showCreatePollingDialog = true
    },
    
    async savePollingConfig() {
      try {
        await this.$refs.pollingFormRef.validate()
        
        this.pollingLoading = true
        // 修复：统一使用store中的用户ID
        const userId = this.$store.getters.currentUser?.id || 1
        
        const payload = {
          user_id: parseInt(userId),
          ...this.pollingForm,
          model_paths: this.selectedPollingModels,
          model_order: this.selectedPollingModels.map((_, index) => index)
        }
        
        let response
        if (this.editingPollingConfig) {
          response = await fetch(`http://localhost:5000/api/polling/configs/${this.editingPollingConfig.id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          })
        } else {
          response = await fetch('http://localhost:5000/api/polling/configs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          })
        }
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(this.editingPollingConfig ? '轮询配置更新成功' : '轮询配置创建成功')
          this.cancelPollingForm()
          await this.loadPollingConfigs()
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        if (error !== false) { // 非表单验证错误
          ElMessage.error('保存配置失败: ' + error.message)
        }
      } finally {
        this.pollingLoading = false
      }
    },
    
    async deletePollingConfig(config) {
      try {
        await ElMessageBox.confirm(
          `确定要删除轮询配置 "${config.name}" 吗？此操作不可恢复。`,
          '确认删除',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
        
        // 修复：统一使用store中的用户ID
        const userId = this.$store.getters.currentUser?.id || 1
        const response = await fetch(`http://localhost:5000/api/polling/configs/${config.id}?user_id=${userId}`, {
          method: 'DELETE'
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success('轮询配置删除成功')
          await this.loadPollingConfigs()
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除配置失败: ' + error.message)
        }
      }
    },
    
    async testPollingConfig() {
      if (this.selectedPollingModels.length === 0) {
        ElMessage.warning('请先选择要测试的模型')
        return
      }
      
      this.pollingLoading = true
      try {
        const response = await fetch('http://localhost:5000/api/polling/test-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model_paths: this.selectedPollingModels
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(`测试完成：${data.success_count}/${data.total_count} 个模型加载成功`)
          
          // 显示详细测试结果
          let detailMessage = '测试结果详情：\n'
          data.test_results.forEach(result => {
            const status = result.status === 'success' ? '✅' : '❌'
            detailMessage += `${status} ${result.model_path}: ${result.message}\n`
          })
          
          ElMessageBox.alert(detailMessage, '测试结果', {
            confirmButtonText: '确定'
          })
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error('测试配置失败: ' + error.message)
      } finally {
        this.pollingLoading = false
      }
    },
    
    cancelPollingForm() {
      this.showCreatePollingDialog = false
      this.editingPollingConfig = null
      this.selectedPollingModels = []
      this.$refs.pollingFormRef?.resetFields()
      this.pollingForm = {
        name: '',
        polling_type: 'frame',
        interval_value: 10,
        model_paths: [],
        model_order: [],
        description: '',
        is_active: true
      }
    },
    
    // 拖拽排序相关方法
    dragStart(index) {
      this.dragFromIndex = index
    },
    
    dragDrop(toIndex) {
      if (this.dragFromIndex === -1 || this.dragFromIndex === toIndex) return
      
      const models = [...this.selectedPollingModels]
      const draggedModel = models.splice(this.dragFromIndex, 1)[0]
      models.splice(toIndex, 0, draggedModel)
      
      this.selectedPollingModels = models
      this.dragFromIndex = -1
    },
    
    moveUp(index) {
      if (index === 0) return
      const models = [...this.selectedPollingModels]
      ;[models[index], models[index - 1]] = [models[index - 1], models[index]]
      this.selectedPollingModels = models
    },
    
    moveDown(index) {
      if (index === this.selectedPollingModels.length - 1) return
      const models = [...this.selectedPollingModels]
      ;[models[index], models[index + 1]] = [models[index + 1], models[index]]
      this.selectedPollingModels = models
    },
    
    // 工具方法
    getModelName(modelPath) {
      return modelPath.split('/').pop() || modelPath
    },
    
    formatDate(timestamp) {
      if (!timestamp) return '--'
      
      let date
      if (typeof timestamp === 'string') {
        date = new Date(timestamp)
      } else {
        date = new Date(timestamp * 1000)
      }
      
      if (isNaN(date.getTime())) return '--'
      
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    
    // 上传相关方法（保持原有逻辑）
    submitUpload() {
      this.$refs.upload.submit()
    },
    
    handleUploadSuccess(response, file) {
      if (response.success) {
        ElMessage.success('模型上传成功')
        this.showUploadDialog = false
        this.fileList = []
        this.loadModels()
      } else {
        ElMessage.error(response.message)
      }
    },
    
    handleUploadError(error) {
      ElMessage.error('上传失败: ' + error.message)
    }
  }
}
</script>

<style scoped>
.model-manager {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.tab-actions {
  display: flex;
  gap: 10px;
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

.model-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.polling-order-list {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}

.polling-order-item {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  cursor: move;
  transition: background-color 0.2s;
}

.polling-order-item:hover {
  background-color: #f5f7fa;
}

.polling-order-item:last-child {
  border-bottom: none;
}

.order-number {
  min-width: 24px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  margin-right: 12px;
}

.model-name {
  flex: 1;
  font-weight: 500;
}

.order-actions {
  margin-left: 8px;
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

:deep(.el-tabs__content) {
  padding: 20px 0;
}
</style> 