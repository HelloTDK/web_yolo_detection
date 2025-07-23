<template>
  <div class="watermark-removal-container">
    <!-- 功能说明 -->
    <el-card class="info-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><InfoFilled /></el-icon>
          <span>去除水印功能说明</span>
        </div>
      </template>
      <div class="info-content">
        <p>🎯 <strong>智能水印检测与去除</strong></p>
        <p>• 支持图片和视频中的水印自动检测和去除</p>
        <p>• 基于AI深度学习技术，智能修复水印区域</p>
        <p>• 支持多种水印类型：文字水印、图像水印、半透明水印等</p>
        <p>• 处理后的文件将保持原始分辨率和质量</p>
      </div>
    </el-card>

    <el-row :gutter="20">
      <!-- 左侧：上传和设置区域 -->
      <el-col :span="12">
        <el-card class="upload-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>文件上传</span>
              <el-radio-group v-model="fileType" size="small">
                <el-radio-button label="image">图片</el-radio-button>
                <el-radio-button label="video">视频</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <!-- 图片上传 -->
          <div v-if="fileType === 'image'" class="upload-section">
            <el-upload
              class="image-uploader"
              :action="uploadAction"
              :show-file-list="false"
              :before-upload="beforeImageUpload"
              :on-success="handleUploadSuccess"
              :on-error="handleUploadError"
              :data="getUploadData()"
              drag
            >
              <div v-if="!imageUrl" class="upload-placeholder">
                <el-icon class="upload-icon"><Plus /></el-icon>
                <div class="upload-text">
                  <p>拖拽图片到此处，或<em>点击上传</em></p>
                  <p class="upload-tip">支持 JPG、PNG、GIF 格式，大小不超过 10MB</p>
                </div>
              </div>
              <img v-else :src="imageUrl" class="uploaded-image" alt="上传的图片">
            </el-upload>
          </div>

          <!-- 视频上传 -->
          <div v-if="fileType === 'video'" class="upload-section">
            <el-upload
              class="video-uploader"
              :auto-upload="false"
              :show-file-list="false"
              :before-upload="beforeVideoUpload"
              :on-change="handleVideoChange"
              drag
            >
              <div v-if="!videoUrl" class="upload-placeholder">
                <el-icon class="upload-icon"><VideoPlay /></el-icon>
                <div class="upload-text">
                  <p>拖拽视频到此处，或<em>点击上传</em></p>
                  <p class="upload-tip">支持 MP4、AVI、MOV 格式，大小不超过 100MB</p>
                </div>
              </div>
              <video v-else :src="videoUrl" class="uploaded-video" controls>
                您的浏览器不支持视频播放
              </video>
            </el-upload>
          </div>

          <!-- 水印检测设置 -->
          <el-card class="settings-card" shadow="never">
            <template #header>
              <div class="card-header">
                <el-icon><Setting /></el-icon>
                <span>检测设置</span>
              </div>
            </template>

            <el-form label-width="120px" size="small">
              <el-form-item label="水印检测模型">
                <el-select 
                  v-model="selectedWatermarkModel" 
                  placeholder="选择水印检测模型" 
                  style="width: 300px;"
                  @change="handleModelChange"
                >
                  <el-option
                    v-for="model in availableWatermarkModels"
                    :key="model.path"
                    :label="model.name"
                    :value="model.path"
                  >
                    <span style="float: left">{{ model.name }}</span>
                    <span style="float: right; color: #8492a6; font-size: 13px">{{ model.size_mb }}MB</span>
                  </el-option>
                </el-select>
                <el-button 
                  type="primary" 
                  size="small" 
                  @click="loadWatermarkModel"
                  :loading="modelLoading"
                  style="margin-left: 10px;"
                >
                  加载模型
                </el-button>
                <div class="setting-desc">
                  使用本地训练的水印检测模型进行精确定位
                </div>
                <div v-if="currentWatermarkModel.loaded" class="model-info">
                  <el-tag type="success" size="small">已加载: {{ currentWatermarkModel.model_path }}</el-tag>
                  <span v-if="currentWatermarkModel.classes.length > 0" class="class-info">
                    支持类别: {{ currentWatermarkModel.classes.join(', ') }}
                  </span>
                </div>
              </el-form-item>

              <el-form-item label="置信度阈值">
                <el-slider 
                  v-model="confidenceThreshold" 
                  :min="0.05" 
                  :max="0.9" 
                  :step="0.05"
                  show-input
                  style="width: 200px;"
                />
                <div class="setting-desc">
                  只处理置信度大于此阈值的水印检测结果。如果检测不到水印，请降低此值
                </div>
                <div class="setting-tip">
                  <el-tag size="small" type="info">建议值: 0.1-0.3</el-tag>
                  <el-tag size="small" type="warning">过高可能检测不到水印</el-tag>
                </div>
              </el-form-item>

              <el-form-item label="检测模式">
                <el-radio-group v-model="detectionMode">
                  <el-radio label="auto">自动检测</el-radio>
                  <el-radio label="manual">指定类别</el-radio>
                </el-radio-group>
                <div class="setting-desc">
                  自动检测：处理所有检测到的水印；指定类别：只处理特定类别的水印
                </div>
              </el-form-item>

              <el-form-item label="水印类别" v-if="detectionMode === 'manual'">
                <el-select v-model="selectedWatermarkClass" placeholder="选择水印类别" style="width: 200px;">
                  <el-option
                    v-for="watermarkClass in watermarkClasses"
                    :key="watermarkClass.value"
                    :label="watermarkClass.label"
                    :value="watermarkClass.value"
                  />
                </el-select>
                <div class="setting-desc">
                  选择要去除的特定水印类别，如文字水印、Logo等
                </div>
              </el-form-item>

              <el-form-item label="去除强度">
                <el-slider 
                  v-model="removalStrength" 
                  :min="1" 
                  :max="5" 
                  :step="1"
                  show-input
                  style="width: 200px;"
                />
                <div class="setting-desc">
                  强度越高去除效果越彻底，但可能影响图像质量
                </div>
              </el-form-item>

              <el-form-item label="边缘修复">
                <el-switch v-model="edgeRepair" />
                <div class="setting-desc">
                  启用边缘修复可以让去除后的区域更自然
                </div>
              </el-form-item>

              <el-form-item label="质量优化">
                <el-switch v-model="qualityOptimization" />
                <div class="setting-desc">
                  启用质量优化可以提升处理后的图像质量
                </div>
              </el-form-item>
            </el-form>
          </el-card>

          <!-- 操作按钮 -->
          <div class="action-buttons">
            <el-button 
              type="primary" 
              size="large"
              :disabled="!canProcess"
              :loading="$store.state.isLoading"
              @click="startWatermarkRemoval"
            >
              <el-icon><MagicStick /></el-icon>
              开始去除水印
            </el-button>
            <el-button @click="resetUpload">
              <el-icon><RefreshRight /></el-icon>
              重新上传
            </el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：结果展示区域 -->
      <el-col :span="12">
        <el-card class="result-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>处理结果</span>
              <div class="result-stats" v-if="processResult.watermarks_detected">
                <el-tag type="success">
                  检测到 {{ processResult.watermarks_detected.length }} 个水印
                </el-tag>
                <el-tag type="warning">
                  已去除 {{ processResult.watermarks_removed || 0 }} 个
                </el-tag>
              </div>
            </div>
          </template>

          <div class="result-content">
            <!-- 处理前后对比 -->
            <div v-if="processResult.result_file" class="comparison-section">
              <div class="comparison-tabs">
                <el-tabs v-model="activeTab" type="card">
                  <el-tab-pane label="处理前" name="before">
                    <div class="image-container">
                      <img 
                        v-if="fileType === 'image' && imageUrl" 
                        :src="imageUrl" 
                        class="comparison-image" 
                        alt="处理前"
                        @click="openPreview(imageUrl, '处理前')"
                      >
                      <video 
                        v-if="fileType === 'video' && videoUrl" 
                        :src="videoUrl" 
                        class="comparison-video" 
                        controls
                      >
                        您的浏览器不支持视频播放
                      </video>
                    </div>
                  </el-tab-pane>
                  <el-tab-pane label="处理后" name="after">
                    <div class="image-container">
                      <img 
                        v-if="fileType === 'image' && processResult.result_file" 
                        :src="getResultUrl()" 
                        class="comparison-image" 
                        alt="处理后"
                        @click="openPreview(getResultUrl(), '处理后')"
                      >
                      <video 
                        v-if="fileType === 'video' && processResult.result_file" 
                        :src="getResultUrl()" 
                        class="comparison-video" 
                        controls
                      >
                        您的浏览器不支持视频播放
                      </video>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </div>
            </div>

            <!-- 水印检测详情 -->
            <div v-if="processResult.watermarks_detected && processResult.watermarks_detected.length > 0" class="watermark-details">
              <h4>检测到的水印</h4>
              <el-table :data="processResult.watermarks_detected" style="width: 100%" size="small">
                <el-table-column prop="type" label="类型" width="100">
                  <template #default="scope">
                    <el-tag :type="getWatermarkTagType(scope.row.type)">
                      {{ scope.row.type }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="confidence" label="置信度" width="100">
                  <template #default="scope">
                    <el-progress 
                      :percentage="Math.round(scope.row.confidence * 100)" 
                      :stroke-width="8"
                    />
                  </template>
                </el-table-column>
                <el-table-column prop="location" label="位置">
                  <template #default="scope">
                    <span class="location-info">
                      {{ formatLocation(scope.row.location) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="80">
                  <template #default="scope">
                    <el-tag :type="scope.row.removed ? 'success' : 'warning'">
                      {{ scope.row.removed ? '已去除' : '未处理' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- 处理统计 -->
            <div v-if="processResult.processing_stats" class="processing-stats">
              <h4>处理统计</h4>
              <el-row :gutter="20">
                <el-col :span="6">
                  <el-statistic title="处理时间" :value="processResult.processing_stats.processing_time" suffix="秒" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="检测精度" :value="processResult.processing_stats.detection_accuracy" suffix="%" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="去除成功率" :value="processResult.processing_stats.removal_success_rate" suffix="%" />
                </el-col>
                <el-col :span="6">
                  <el-statistic title="图像质量" :value="processResult.processing_stats.image_quality" suffix="%" />
                </el-col>
              </el-row>
            </div>

            <!-- 下载按钮 -->
            <div v-if="processResult.result_file" class="download-section">
              <el-button type="success" @click="downloadResult">
                <el-icon><Download /></el-icon>
                下载处理后的文件
              </el-button>
            </div>

            <!-- 空状态 -->
            <div v-if="!processResult.result_file && !$store.state.isLoading" class="empty-result">
              <el-empty description="暂无处理结果">
                <el-button type="primary" @click="startWatermarkRemoval" v-if="canProcess">
                  开始去除水印
                </el-button>
              </el-empty>
            </div>

            <!-- 加载状态 -->
            <div v-if="$store.state.isLoading" class="loading-result">
              <el-loading 
                element-loading-text="正在处理水印去除..."
                element-loading-spinner="el-icon-loading"
                element-loading-background="rgba(0, 0, 0, 0.8)"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图片预览对话框 -->
    <el-dialog
      v-model="showPreview"
      :title="previewTitle"
      width="90%"
      top="5vh"
      destroy-on-close
    >
      <div class="preview-container">
        <img 
          v-if="previewImageUrl" 
          :src="previewImageUrl" 
          class="preview-image" 
          alt="预览图"
        >
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { 
  Plus, 
  VideoPlay, 
  Setting, 
  MagicStick,
  RefreshRight,
  Download,
  InfoFilled
} from '@element-plus/icons-vue'

export default {
  name: 'WatermarkRemoval',
  components: {
    Plus,
    VideoPlay,
    Setting,
    MagicStick,
    RefreshRight,
    Download,
    InfoFilled
  },
  data() {
    return {
      fileType: 'image',
      imageUrl: '',
      videoUrl: '',
      videoFile: null,
      uploadAction: 'http://localhost:5000/api/watermark/remove',
      
      // 水印检测模型相关
      selectedWatermarkModel: '',
      availableWatermarkModels: [],
      currentWatermarkModel: {
        loaded: false,
        model_path: null,
        classes: []
      },
      modelLoading: false,
      
      // 检测设置
      detectionMode: 'auto',
      selectedWatermarkClass: '',
      confidenceThreshold: 0.25,
      removalStrength: 3,
      edgeRepair: true,
      qualityOptimization: true,
      
      // 水印类别选项（备用）
      watermarkClasses: [
        { label: '文字水印', value: 'text' },
        { label: 'Logo水印', value: 'logo' },
        { label: '图片水印', value: 'image' },
        { label: '半透明水印', value: 'transparent' },
        { label: '网站水印', value: 'website' },
        { label: '其他水印', value: 'other' }
      ],
      
      // 处理结果
      processResult: {},
      activeTab: 'before',
      
      // 调试信息
      debugInfo: {
        show: false,
        logs: []
      },
      
      // 预览相关
      showPreview: false,
      previewImageUrl: '',
      previewTitle: ''
    }
  },
  computed: {
    canProcess() {
      return (this.fileType === 'image' && this.imageUrl) || 
             (this.fileType === 'video' && this.videoFile)
    }
  },
  async mounted() {
    await this.loadAvailableWatermarkModels()
    await this.loadCurrentWatermarkModelInfo()
  },
  methods: {
    getUploadData() {
      return {
        user_id: this.$store.getters.currentUser?.id || 1,
        file_type: this.fileType,
        detection_mode: this.detectionMode,
        watermark_class: this.selectedWatermarkClass,
        confidence_threshold: this.confidenceThreshold,
        removal_strength: this.removalStrength,
        edge_repair: this.edgeRepair,
        quality_optimization: this.qualityOptimization
      }
    },
    
    // 水印检测模型相关方法
    async loadAvailableWatermarkModels() {
      try {
        const response = await fetch('http://localhost:5000/api/watermark/models')
        const data = await response.json()
        
        if (data.success) {
          this.availableWatermarkModels = data.models
          if (data.models.length > 0 && !this.selectedWatermarkModel) {
            this.selectedWatermarkModel = data.models[0].path
          }
        }
      } catch (error) {
        console.error('加载水印模型列表失败:', error)
      }
    },
    
    async loadCurrentWatermarkModelInfo() {
      try {
        const response = await fetch('http://localhost:5000/api/watermark/model/info')
        const data = await response.json()
        
        if (data.success) {
          this.currentWatermarkModel = data.model_info
        }
      } catch (error) {
        console.error('获取当前模型信息失败:', error)
      }
    },
    
    handleModelChange() {
      // 模型选择变化时的处理
      console.log('选择的模型:', this.selectedWatermarkModel)
    },
    
    async loadWatermarkModel() {
      if (!this.selectedWatermarkModel) {
        ElMessage.error('请先选择水印检测模型')
        return
      }
      
      try {
        this.modelLoading = true
        
        const response = await fetch('http://localhost:5000/api/watermark/model/load', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            model_path: this.selectedWatermarkModel
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          this.currentWatermarkModel = data.model_info
          ElMessage.success('水印检测模型加载成功')
          
          // 更新水印类别选项
          if (data.model_info.classes && data.model_info.classes.length > 0) {
            this.watermarkClasses = data.model_info.classes.map(cls => ({
              label: cls,
              value: cls
            }))
          }
        } else {
          ElMessage.error(data.message || '模型加载失败')
        }
      } catch (error) {
        console.error('加载模型失败:', error)
        ElMessage.error('加载模型失败: ' + error.message)
      } finally {
        this.modelLoading = false
      }
    },
    
    // 图片上传相关
    beforeImageUpload(file) {
      const isImage = file.type.startsWith('image/')
      const isLt10M = file.size / 1024 / 1024 < 10
      
      if (!isImage) {
        ElMessage.error('只能上传图片文件!')
        return false
      }
      if (!isLt10M) {
        ElMessage.error('图片大小不能超过 10MB!')
        return false
      }
      
      this.imageUrl = URL.createObjectURL(file)
      return true
    },
    
    // 视频上传相关
    beforeVideoUpload(file) {
      const isVideo = file.type.startsWith('video/')
      const isLt100M = file.size / 1024 / 1024 < 100
      
      if (!isVideo) {
        ElMessage.error('只能上传视频文件!')
        return false
      }
      if (!isLt100M) {
        ElMessage.error('视频大小不能超过 100MB!')
        return false
      }
      
      return true
    },
    
    handleVideoChange(uploadFile) {
      this.videoUrl = URL.createObjectURL(uploadFile.raw)
      this.videoFile = uploadFile.raw
      ElMessage.success('视频上传成功，请点击"开始去除水印"进行处理')
    },
    
    handleUploadSuccess(response) {
      if (response.success) {
        this.processResult = { ...response }
        this.activeTab = 'after'
        ElMessage.success('水印去除完成!')
      } else {
        ElMessage.error(response.message)
      }
    },
    
    handleUploadError(error) {
      console.error('上传错误:', error)
      ElMessage.error('处理失败，请重试')
    },
    
    async startWatermarkRemoval() {
      if (this.fileType === 'image' && this.imageUrl) {
        ElMessage.info('请重新上传图片以触发处理')
      } else if (this.fileType === 'video' && this.videoFile) {
        await this.processVideo()
      }
    },
    
    async processVideo() {
      if (!this.videoFile) {
        ElMessage.error('请先上传视频文件')
        return
      }
      
      try {
        this.$store.commit('SET_LOADING', true)
        
        const formData = new FormData()
        formData.append('file', this.videoFile)
        formData.append('user_id', this.$store.getters.currentUser?.id || 1)
        formData.append('file_type', this.fileType)
        formData.append('detection_mode', this.detectionMode)
        formData.append('watermark_class', this.selectedWatermarkClass)
        formData.append('removal_strength', this.removalStrength)
        formData.append('edge_repair', this.edgeRepair)
        formData.append('quality_optimization', this.qualityOptimization)
        
        const response = await fetch('http://localhost:5000/api/watermark/remove_video', {
          method: 'POST',
          body: formData
        })
        
        const data = await response.json()
        
        if (data.success) {
          this.handleUploadSuccess(data)
        } else {
          ElMessage.error(data.message || '视频处理失败')
        }
      } catch (error) {
        console.error('视频处理失败:', error)
        ElMessage.error('视频处理失败: ' + error.message)
      } finally {
        this.$store.commit('SET_LOADING', false)
      }
    },
    
    resetUpload() {
      // 清理旧的URL
      if (this.imageUrl && this.imageUrl.startsWith('blob:')) {
        URL.revokeObjectURL(this.imageUrl)
      }
      if (this.videoUrl && this.videoUrl.startsWith('blob:')) {
        URL.revokeObjectURL(this.videoUrl)
      }
      
      this.imageUrl = ''
      this.videoUrl = ''
      this.videoFile = null
      this.processResult = {}
      this.activeTab = 'before'
    },
    
    getResultUrl() {
      return `http://localhost:5000${this.processResult.result_file}`
    },
    
    openPreview(imageUrl, title) {
      this.previewImageUrl = imageUrl
      this.previewTitle = title
      this.showPreview = true
    },
    
    downloadResult() {
      if (!this.processResult.result_file) return
      
      const link = document.createElement('a')
      link.href = this.getResultUrl()
      link.download = `去除水印_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.${this.fileType === 'image' ? 'jpg' : 'mp4'}`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      ElMessage.success('文件下载已开始')
    },
    
    getWatermarkTagType(type) {
      const tagTypes = {
        'text': 'primary',
        'logo': 'success',
        'image': 'warning',
        'transparent': 'info',
        'website': 'danger',
        'other': 'info'
      }
      return tagTypes[type] || 'info'
    },
    
    formatLocation(location) {
      if (!location || location.length !== 4) return ''
      const [x1, y1, x2, y2] = location
      return `(${Math.round(x1)}, ${Math.round(y1)}) - (${Math.round(x2)}, ${Math.round(y2)})`
    }
  }
}
</script>

<style scoped>
.watermark-removal-container {
  max-width: 1400px;
  margin: 0 auto;
}

.info-card {
  margin-bottom: 20px;
}

.info-content {
  line-height: 1.8;
  color: #606266;
}

.info-content p {
  margin: 8px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.result-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.upload-card, .result-card {
  min-height: 600px;
}

.upload-section {
  margin-bottom: 20px;
}

.image-uploader, .video-uploader {
  width: 100%;
}

:deep(.el-upload) {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
  height: 250px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 20px;
}

.upload-text {
  text-align: center;
}

.upload-text p {
  margin: 5px 0;
}

.upload-tip {
  color: #999;
  font-size: 12px;
}

.uploaded-image, .uploaded-video {
  max-width: 100%;
  max-height: 250px;
  border-radius: 8px;
}

.settings-card {
  margin-bottom: 20px;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
}

.settings-card :deep(.el-card__header) {
  background: #ffffff;
  border-bottom: 1px solid #e9ecef;
}

.setting-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  line-height: 1.4;
}

.action-buttons {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 20px;
}

.result-content {
  position: relative;
  min-height: 400px;
}

.comparison-section {
  margin-bottom: 20px;
}

.comparison-tabs {
  width: 100%;
}

.image-container {
  text-align: center;
  padding: 20px;
}

.comparison-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.3s ease;
}

.comparison-image:hover {
  transform: scale(1.02);
}

.comparison-video {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.watermark-details {
  margin-top: 20px;
}

.watermark-details h4 {
  margin-bottom: 15px;
  color: #333;
}

.location-info {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

.processing-stats {
  margin-top: 20px;
  padding: 15px;
  background: #f0f2f5;
  border-radius: 6px;
}

.processing-stats h4 {
  margin-bottom: 15px;
  color: #333;
}

.processing-stats :deep(.el-statistic__content) {
  font-size: 16px;
  color: #409eff;
}

.download-section {
  margin-top: 20px;
  text-align: center;
}

.empty-result {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 300px;
}

.loading-result {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-container {
  text-align: center;
  padding: 20px;
}

.preview-image {
  max-width: 100%;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 8px;
}

:deep(.el-radio-button__inner) {
  padding: 8px 16px;
}

:deep(.el-tabs__item) {
  padding: 0 20px;
}

:deep(.el-tabs__content) {
  padding-top: 10px;
}

/* 模型相关样式 */
.model-info {
  margin-top: 8px;
  padding: 8px;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 4px;
}

.class-info {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.model-info .el-tag {
  margin-right: 8px;
}

.setting-tip {
  margin-top: 5px;
}

.setting-tip .el-tag {
  margin-right: 8px;
}
</style> 