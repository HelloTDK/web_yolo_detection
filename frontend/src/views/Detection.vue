<template>
  <div class="detection-container">
    <!-- 检测方式选择 -->
    <el-card class="mode-selector" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>检测方式选择</span>
        </div>
      </template>
      
      <el-radio-group v-model="detectionMode" size="large" @change="handleModeChange">
        <el-radio-button label="image">
          <el-icon><Picture /></el-icon>
          图片检测
        </el-radio-button>
        <el-radio-button label="image_seg">
          <el-icon><Picture /></el-icon>
          图片分割
        </el-radio-button>
        <el-radio-button label="video">
          <el-icon><VideoPlay /></el-icon>
          视频检测
        </el-radio-button>
        <el-radio-button label="video_seg">
          <el-icon><VideoPlay /></el-icon>
          视频分割
        </el-radio-button>
        <el-radio-button label="camera">
          <el-icon><Camera /></el-icon>
          摄像头检测
        </el-radio-button>
        <el-radio-button label="rtsp">
          <el-icon><VideoPlay /></el-icon>
          RTSP流检测
        </el-radio-button>
      </el-radio-group>
    </el-card>
    
    <el-row :gutter="20">
      <!-- 左侧：上传和控制区域 -->
      <el-col :span="detectionMode === 'rtsp' ? 24 : 12">
        <el-card class="upload-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ getModeTitle() }}</span>
            </div>
          </template>
          
          <!-- 图片上传 -->
          <div v-if="detectionMode === 'image' || detectionMode === 'image_seg'" class="upload-section">
            <el-upload
              class="image-uploader"
              :action="getUploadAction()"
              :show-file-list="false"
              :before-upload="beforeImageUpload"
              :on-success="handleImageSuccess"
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
              <img v-else :src="imageUrl" class="uploaded-image" alt="上传的图片" />
            </el-upload>
          </div>
          
          <!-- 视频上传 -->
          <div v-if="detectionMode === 'video' || detectionMode === 'video_seg'" class="upload-section">
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
          
          <!-- 摄像头 -->
          <div v-if="detectionMode === 'camera'" class="camera-section">
            <div class="camera-container">
              <video 
                ref="cameraVideo" 
                class="camera-video" 
                autoplay 
                muted
                v-show="isCameraActive"
              ></video>
              <canvas 
                ref="cameraCanvas" 
                class="camera-canvas" 
                style="display: none;"
              ></canvas>
              
              <div v-if="!isCameraActive" class="camera-placeholder">
                <el-icon class="camera-icon"><Camera /></el-icon>
                <p>点击"启动摄像头"开始实时检测</p>
              </div>
            </div>
            
            <div class="camera-controls">
              <el-button 
                v-if="!isCameraActive"
                type="primary" 
                @click="startCamera"
              >
                启动摄像头
              </el-button>
              <el-button 
                v-if="isCameraActive"
                type="danger" 
                @click="stopCamera"
              >
                停止摄像头
              </el-button>
            </div>
          </div>
          
          <!-- RTSP流检测 -->
          <div v-if="detectionMode === 'rtsp'" class="rtsp-section">
            <el-card class="rtsp-manager-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>RTSP流管理</span>
                  <div class="rtsp-controls">
                    <el-button 
                      type="primary" 
                      size="small"
                      @click="showAddStreamDialog = true"
                    >
                      <el-icon><Plus /></el-icon>
                      添加流
                    </el-button>
                    <el-button 
                      type="success" 
                      size="small"
                      @click="startAllStreams"
                    >
                      <el-icon><VideoPlay /></el-icon>
                      启动全部
                    </el-button>
                    <el-button 
                      type="danger" 
                      size="small"
                      @click="stopAllStreams"
                    >
                      <el-icon><VideoPause /></el-icon>
                      停止全部
                    </el-button>
                  </div>
                </div>
              </template>
              
              <!-- 四宫格显示 -->
              <div class="rtsp-grid">
                <div 
                  v-for="(position, index) in gridPositions" 
                  :key="`grid-${position.x}-${position.y}`"
                  class="rtsp-grid-item"
                  :class="{ 'has-stream': getStreamByPosition(position.x, position.y) }"
                >
                  <div v-if="getStreamByPosition(position.x, position.y)" class="stream-container">
                    <!-- 流信息标题栏 -->
                    <div class="stream-header-bar">
                      <div class="stream-title-info">
                        <h4 class="stream-name">{{ getStreamByPosition(position.x, position.y).name }}</h4>
                        <el-tag 
                          :type="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running' ? 'success' : 'danger'"
                          size="small"
                        >
                          {{ getStreamStatusText(getStreamByPosition(position.x, position.y).id) }}
                        </el-tag>
                      </div>
                      
                      <!-- 控制按钮 -->
                      <div class="stream-control-buttons">
                        <el-button-group size="mini">
                          <el-button 
                            :type="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running' ? 'danger' : 'success'"
                            @click="toggleStream(getStreamByPosition(position.x, position.y))"
                            :title="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running' ? '停止' : '播放'"
                          >
                            <el-icon v-if="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running'">
                              <VideoPause />
                            </el-icon>
                            <el-icon v-else><VideoPlay /></el-icon>
                          </el-button>
                          <el-button 
                            type="primary"
                            @click="openStreamPreview(getStreamByPosition(position.x, position.y))"
                            v-if="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running'"
                            title="全屏预览"
                          >
                            <el-icon><ZoomIn /></el-icon>
                          </el-button>
                          <el-button 
                            @click="editStream(getStreamByPosition(position.x, position.y))"
                            title="设置"
                          >
                            <el-icon><Setting /></el-icon>
                          </el-button>
                          <el-button 
                            type="danger" 
                            @click="deleteStream(getStreamByPosition(position.x, position.y))"
                            :loading="deletingStreamIds.has(getStreamByPosition(position.x, position.y).id)"
                            :disabled="deletingStreamIds.has(getStreamByPosition(position.x, position.y).id)"
                            title="删除"
                          >
                            <el-icon v-if="!deletingStreamIds.has(getStreamByPosition(position.x, position.y).id)"><Delete /></el-icon>
                          </el-button>
                        </el-button-group>
                      </div>
                    </div>
                    
                    <!-- 流视频显示 -->
                    <div class="stream-video-container" @click="openStreamPreview(getStreamByPosition(position.x, position.y))">
                      <img 
                        v-if="streamFrames[getStreamByPosition(position.x, position.y).id]"
                        :src="streamFrames[getStreamByPosition(position.x, position.y).id]"
                        class="stream-frame"
                        :alt="`${getStreamByPosition(position.x, position.y).name} - 实时画面`"
                      />
                      <div v-else class="stream-placeholder">
                        <el-icon class="stream-icon"><VideoPlay /></el-icon>
                        <p>{{ getStreamByPosition(position.x, position.y).name }}</p>
                        <p class="stream-status">等待连接...</p>
                      </div>
                      
                      <!-- 预览提示覆盖层 -->
                      <div v-if="streamFrames[getStreamByPosition(position.x, position.y).id]" class="preview-overlay">
                        <el-icon><ZoomIn /></el-icon>
                        <span>点击全屏预览</span>
                      </div>
                    </div>
                    
                    <!-- 流统计信息 -->
                    <div v-if="getStreamStatus(getStreamByPosition(position.x, position.y).id) === 'running'" class="stream-stats-bar">
                      <small>{{ getStreamStats(getStreamByPosition(position.x, position.y).id) }}</small>
                    </div>
                  </div>
                  
                  <!-- 空位置 -->
                  <div v-else class="empty-grid-item">
                    <el-icon class="add-stream-icon"><Plus /></el-icon>
                    <p>点击添加RTSP流</p>
                    <div class="quick-actions">
                      <el-button type="primary" size="small" @click="showAddStreamDialog = true">
                        添加流
                      </el-button>
                      <el-button type="success" size="small" @click="createTestStream">
                        创建测试流
                      </el-button>
                    </div>
                  </div>
                </div>
              </div>
            </el-card>
          </div>
          
          <!-- 检测控制 -->
          <div class="detection-controls" v-if="detectionMode !== 'camera' && detectionMode !== 'rtsp'">
            <el-button 
              type="primary" 
              size="large"
              :disabled="!canDetect"
              :loading="$store.state.isLoading"
              @click="startDetection"
            >
              <el-icon><Search /></el-icon>
              开始检测
            </el-button>
            <el-button @click="resetUpload">
              <el-icon><RefreshRight /></el-icon>
              重新上传
            </el-button>
          </div>
        </el-card>
      </el-col>
      
      <!-- 右侧：检测结果区域 -->
      <el-col :span="12" v-if="detectionMode !== 'rtsp'">
        <el-card class="result-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>检测结果</span>
            </div>
          </template>
          
          <div class="result-content">
            <!-- 检测结果图片 -->
            <div v-if="detectionResult.result_image && (detectionMode === 'image' || detectionMode === 'image_seg')" class="result-media">
              <img 
                :src="getResultImageUrl()" 
                class="result-image" 
                :alt="detectionMode === 'image_seg' ? '分割结果' : '检测结果'" 
                @error="handleImageError"
              />
            </div>
            
            <!-- 检测结果视频 -->
            <div v-if="detectionResult.result_video && (detectionMode === 'video' || detectionMode === 'video_seg')" class="result-media">
              <video 
                :src="getResultVideoUrl()" 
                class="result-video" 
                controls 
                preload="metadata"
                @error="handleVideoError"
              >
                您的浏览器不支持视频播放
              </video>
            </div>
            
            <!-- 检测结果列表 -->
            <div v-if="detectionResult.detections && detectionResult.detections.length > 0" class="detection-list">
              <h4>检测详情</h4>
              <el-table :data="detectionResult.detections" style="width: 100%" size="small">
                <el-table-column prop="class" label="类别" width="120" />
                <el-table-column label="置信度" width="100">
                  <template #default="scope">
                    <el-progress 
                      :percentage="Math.round(scope.row.confidence * 100)" 
                      :stroke-width="8"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="位置">
                  <template #default="scope">
                    <span class="bbox-info">
                      {{ formatBbox(scope.row.bbox) }}
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <!-- 空状态 -->
            <div v-if="!detectionResult.detections && !$store.state.isLoading && detectionMode !== 'camera' && detectionMode !== 'rtsp'" class="empty-result">
              <el-empty description="暂无检测结果">
                <el-button type="primary" @click="startDetection" v-if="canDetect">
                  开始检测
                </el-button>
              </el-empty>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 流预览对话框 -->
    <el-dialog
      v-model="showPreviewDialog"
      :title="`${currentPreviewStream?.name || ''} - 实时预览`"
      width="80%"
      top="5vh"
      destroy-on-close
      :before-close="closeStreamPreview"
    >
      <div class="preview-container">
        <div class="preview-video">
          <img 
            v-if="currentPreviewStream && streamFrames[currentPreviewStream.id]"
            :src="streamFrames[currentPreviewStream.id]"
            class="preview-frame"
            :alt="`${currentPreviewStream.name} - 实时预览`"
          />
          <div v-else class="preview-placeholder">
            <el-icon class="preview-icon"><VideoPlay /></el-icon>
            <p>等待视频流...</p>
          </div>
        </div>
        
        <!-- 预览控制栏 -->
        <div class="preview-controls">
          <div class="preview-info">
            <el-tag 
              :type="getStreamStatus(currentPreviewStream?.id) === 'running' ? 'success' : 'danger'"
              size="large"
            >
              {{ getStreamStatusText(currentPreviewStream?.id) }}
            </el-tag>
            <span class="preview-stats">{{ getStreamStats(currentPreviewStream?.id) }}</span>
          </div>
          
          <div class="preview-buttons">
            <el-button-group>
              <el-button 
                :type="getStreamStatus(currentPreviewStream?.id) === 'running' ? 'danger' : 'success'"
                @click="toggleStream(currentPreviewStream)"
                v-if="currentPreviewStream"
              >
                <el-icon v-if="getStreamStatus(currentPreviewStream.id) === 'running'">
                  <VideoPause />
                </el-icon>
                <el-icon v-else><VideoPlay /></el-icon>
                {{ getStreamStatus(currentPreviewStream.id) === 'running' ? '停止' : '播放' }}
              </el-button>
              <el-button @click="refreshPreview">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
              <el-button @click="closeStreamPreview">
                <el-icon><Close /></el-icon>
                关闭
              </el-button>
            </el-button-group>
          </div>
        </div>
      </div>
    </el-dialog>
    
    <!-- RTSP流配置对话框 -->
    <el-dialog
      v-model="showAddStreamDialog"
      :title="editingStream ? '编辑RTSP流' : '添加RTSP流'"
      width="600px"
      destroy-on-close
      @close="resetStreamForm"
    >
      <el-form
        ref="streamFormRef"
        :model="streamForm"
        :rules="streamFormRules"
        label-width="100px"
        size="default"
      >
        <el-form-item label="流名称" prop="name">
          <el-input 
            v-model="streamForm.name" 
            placeholder="请输入流名称"
            clearable
          />
        </el-form-item>
        
        <el-form-item label="RTSP地址" prop="url">
          <el-input 
            v-model="streamForm.url" 
            placeholder="rtsp://username:password@ip:port/path"
            clearable
          />
          <div class="form-tip">
            例如: rtsp://admin:123456@192.168.1.100:554/stream1
          </div>
          <el-button 
            type="primary" 
            size="small" 
            :loading="testingConnection"
            @click="testRTSPConnection"
            style="margin-top: 10px;"
          >
            <el-icon><Link /></el-icon>
            测试连接
          </el-button>
        </el-form-item>
        
        <el-form-item label="用户名">
          <el-input 
            v-model="streamForm.username" 
            placeholder="RTSP用户名（可选）"
            clearable
          />
        </el-form-item>
        
        <el-form-item label="密码">
          <el-input 
            v-model="streamForm.password" 
            type="password" 
            placeholder="RTSP密码（可选）"
            show-password
            clearable
          />
        </el-form-item>
        
        <el-form-item label="检测模型">
          <el-select 
            v-model="streamForm.model_path" 
            placeholder="选择检测模型"
            style="width: 100%"
          >
            <el-option
              v-for="model in availableModels"
              :key="model.path"
              :label="model.name"
              :value="model.path"
            />
          </el-select>
        </el-form-item>
        
        <el-form-item label="功能设置">
          <div class="feature-settings">
            <el-checkbox v-model="streamForm.detection_enabled">启用检测</el-checkbox>
            <el-checkbox v-model="streamForm.tracking_enabled">启用跟踪</el-checkbox>
            <el-checkbox v-model="streamForm.counting_enabled">启用计数</el-checkbox>
            <el-checkbox v-model="streamForm.alert_enabled">启用预警</el-checkbox>
          </div>
        </el-form-item>
        
        <el-form-item label="状态">
          <el-switch 
            v-model="streamForm.is_active"
            active-text="启用"
            inactive-text="禁用"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showAddStreamDialog = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="saveStream"
            :loading="streamSaving"
          >
            {{ editingStream ? '更新' : '添加' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage, ElNotification } from 'element-plus'
import { reactive } from 'vue'
import { 
  Picture, 
  VideoPlay, 
  Camera, 
  Plus, 
  Search, 
  RefreshRight,
  VideoPause,
  Setting,
  Delete,
  Link
} from '@element-plus/icons-vue'

export default {
  name: 'Detection',
  components: {
    Picture,
    VideoPlay,
    Camera,
    Plus,
    Search,
    RefreshRight,
    VideoPause,
    Setting,
    Delete,
    Link
  },
  data() {
    return {
      detectionMode: 'image',
      imageUrl: '',
      videoUrl: '',
      videoFile: null,
      isCameraActive: false,
      detectionResult: {},
      cameraStream: null,
      
      // RTSP流相关数据
      showAddStreamDialog: false,
      editingStream: null,
      
      // 预览相关
      showPreviewDialog: false,
      currentPreviewStream: null,
      
      // 删除状态
      deletingStreamIds: new Set(),
      streamSaving: false,
      testingConnection: false,
      rtspStreams: [],
      streamFrames: reactive({}), // 使用响应式对象
      streamStatus: reactive({}), // 使用响应式对象
      rtspUpdateInterval: null,
      
      // 四宫格位置
      gridPositions: [
        { x: 0, y: 0 },
        { x: 1, y: 0 },
        { x: 0, y: 1 },
        { x: 1, y: 1 }
      ],
      
      // 流配置表单
      streamForm: {
        name: '',
        url: '',
        username: '',
        password: '',
        model_path: 'yolov8n.pt',
        detection_enabled: true,
        tracking_enabled: false,
        counting_enabled: false,
        alert_enabled: false,
        is_active: true
      },
      
      // 表单验证规则
      streamFormRules: {
        name: [
          { required: true, message: '请输入流名称', trigger: 'blur' },
          { min: 1, max: 50, message: '流名称长度在1到50个字符', trigger: 'blur' }
        ],
        url: [
          { required: true, message: '请输入RTSP地址', trigger: 'blur' },
          { pattern: /^rtsp:\/\//, message: 'RTSP地址必须以rtsp://开头', trigger: 'blur' }
        ]
      },
      
      // 可用模型列表 - 从API动态加载
      availableModels: []
    }
  },
  
  computed: {
    canDetect() {
      return (this.detectionMode === 'image' && this.imageUrl) || 
             (this.detectionMode === 'image_seg' && this.imageUrl) ||
             (this.detectionMode === 'video' && this.videoFile) ||
             (this.detectionMode === 'video_seg' && this.videoFile)
    }
  },
  
  async mounted() {
    // 加载可用模型列表
    await this.loadAvailableModels()
    
    // 如果是RTSP模式，初始化RTSP流
    if (this.detectionMode === 'rtsp') {
      await this.initRTSPStreams()
    }
    
    // 添加resize事件监听器，使用防抖处理
    this.debouncedHandleResize = this.debounce(this.handleResize, 150)
    window.addEventListener('resize', this.debouncedHandleResize)
  },
  
  methods: {
    // 防抖函数
    debounce(func, wait) {
      let timeout
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout)
          func(...args)
        }
        clearTimeout(timeout)
        timeout = setTimeout(later, wait)
      }
    },
    
    // 处理窗口大小变化
    handleResize() {
      // 强制重新渲染某些组件以避免ResizeObserver问题
      if (this.detectionMode === 'rtsp') {
        this.$nextTick(() => {
          // 触发RTSP网格重新计算
          const gridElement = this.$el.querySelector('.rtsp-grid')
          if (gridElement) {
            gridElement.style.display = 'none'
            gridElement.offsetHeight // 强制重排
            gridElement.style.display = 'grid'
          }
        })
      }
    },
    
    getModeTitle() {
      const titles = {
        image: '图片上传检测',
        image_seg: '图片分割检测',
        video: '视频上传检测',
        video_seg: '视频分割检测',
        camera: '摄像头实时检测',
        rtsp: 'RTSP流实时检测'
      }
      return titles[this.detectionMode]
    },
    
    handleModeChange() {
      // 停止摄像头和RTSP更新
      this.silentStopCamera()
      this.stopRTSPUpdate()
      this.resetUpload()
      this.detectionResult = {}
      
      // 如果切换到RTSP模式，初始化RTSP流并重新加载模型列表
      if (this.detectionMode === 'rtsp') {
        this.$nextTick(async () => {
          // 重新加载模型列表，确保获取最新的可用模型
          await this.loadAvailableModels()
          await this.initRTSPStreams()
        })
      }
    },
    
    // 加载可用模型列表
    async loadAvailableModels() {
      try {
        const response = await fetch('http://localhost:5000/api/models')
        const data = await response.json()
        if (data.success) {
          // 将模型数据转换为下拉选择需要的格式
          this.availableModels = data.models.map(model => ({
            name: model.name + (model.pretrained ? ' (预训练)' : ''),
            path: model.path,
            type: model.type || 'detection',
            pretrained: model.pretrained || false
          }))
          console.log('✅ 加载可用模型列表成功:', this.availableModels.length, '个模型')
        } else {
          console.error('❌ 加载模型列表失败:', data.message)
          ElMessage.error('加载模型列表失败: ' + data.message)
        }
      } catch (error) {
        console.error('❌ 加载模型列表异常:', error)
        ElMessage.error('加载模型列表失败: ' + error.message)
      }
    },
    
    getUploadAction() {
      if (this.detectionMode === 'image_seg') {
        return 'http://localhost:5000/api/segment_image'
      } else if (this.detectionMode === 'video_seg') {
        return 'http://localhost:5000/api/segment_video'
      } else if (this.detectionMode === 'image') {
        return 'http://localhost:5000/api/detect_image'
      } else {
        return 'http://localhost:5000/api/detect_video'
      }
    },
    
    getUploadData() {
      return {
        user_id: this.$store.getters.currentUser?.id || 1
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
    
    handleImageSuccess(response) {
      if (response.success) {
        this.detectionResult = { ...response }
        ElMessage.success('图片检测完成')
      } else {
        ElMessage.error(response.message)
      }
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
      ElMessage.success('视频上传成功，请点击"开始检测"进行分析')
    },
    
    handleUploadError(error) {
      console.error('上传错误详情:', error)
      ElMessage.error('上传失败: ' + (error.message || '未知错误'))
    },
    
    // 摄像头相关
    async startCamera() {
      try {
        this.cameraStream = await navigator.mediaDevices.getUserMedia({ 
          video: { width: { ideal: 640 }, height: { ideal: 480 } } 
        })
        
        if (this.$refs.cameraVideo) {
          this.$refs.cameraVideo.srcObject = this.cameraStream
          this.isCameraActive = true
          ElMessage.success('摄像头已启动')
        }
      } catch (error) {
        ElMessage.error('无法访问摄像头: ' + error.message)
      }
    },
    
    stopCamera() {
      this.silentStopCamera()
      ElMessage.success('摄像头已关闭')
    },
    
    silentStopCamera() {
      if (this.cameraStream) {
        this.cameraStream.getTracks().forEach(track => track.stop())
        this.cameraStream = null
      }
      this.isCameraActive = false
    },
    
    // 检测相关
    async startDetection() {
      if ((this.detectionMode === 'image' || this.detectionMode === 'image_seg') && this.imageUrl) {
        ElMessage.info('请重新上传图片以触发检测')
      } else if ((this.detectionMode === 'video' || this.detectionMode === 'video_seg') && this.videoFile) {
        await this.detectVideo()
      }
    },
    
    async detectVideo() {
      if (!this.videoFile) {
        ElMessage.error('请先上传视频文件')
        return
      }
      
      try {
        this.$store.commit('SET_LOADING', true)
        
        const formData = new FormData()
        formData.append('file', this.videoFile)
        formData.append('user_id', this.$store.getters.currentUser?.id || 1)
        
        const response = await fetch(this.getUploadAction(), {
          method: 'POST',
          body: formData
        })
        
        const data = await response.json()
        
        if (data.success) {
          this.detectionResult = { ...data }
          ElMessage.success('视频检测完成')
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
      if (this.imageUrl && this.imageUrl.startsWith('blob:')) {
        URL.revokeObjectURL(this.imageUrl)
      }
      if (this.videoUrl && this.videoUrl.startsWith('blob:')) {
        URL.revokeObjectURL(this.videoUrl)
      }
      
      this.imageUrl = ''
      this.videoUrl = ''
      this.videoFile = null
      this.detectionResult = {}
    },
    
    // 结果显示相关
    getResultImageUrl() {
      return `http://localhost:5000${this.detectionResult.result_image}`
    },
    
    getResultVideoUrl() {
      return `http://localhost:5000${this.detectionResult.result_video}`
    },
    
    formatBbox(bbox) {
      if (!bbox || bbox.length !== 4) return ''
      return `(${Math.round(bbox[0])}, ${Math.round(bbox[1])}) - (${Math.round(bbox[2])}, ${Math.round(bbox[3])})`
    },
    
    handleImageError(event) {
      console.error('图片加载错误:', event)
      ElMessage.error('图片加载失败，请检查网络连接')
    },
    
    handleVideoError(event) {
      console.error('视频加载错误:', event)
      ElMessage.error('视频加载失败，请检查网络连接')
    },
    
    // ==================== RTSP流相关方法 ====================
    
    // 初始化RTSP流
    async initRTSPStreams() {
      if (this.detectionMode === 'rtsp') {
        await this.loadRTSPStreams()
        this.startRTSPUpdate()
      }
    },
    
    // 加载RTSP流列表
    async loadRTSPStreams() {
      try {
        const response = await fetch(`http://localhost:5000/api/rtsp/streams?user_id=${this.$store.getters.currentUser?.id || 1}`)
        const data = await response.json()
        
        if (data.success) {
          this.rtspStreams = data.streams
          console.log('✅ 加载RTSP流列表成功:', this.rtspStreams.length, '个流')
        } else {
          console.error('❌ 加载RTSP流列表失败:', data.message)
        }
      } catch (error) {
        console.error('❌ 加载RTSP流列表异常:', error)
      }
    },
    
    // 根据位置获取流
    getStreamByPosition(x, y) {
      return this.rtspStreams.find(stream => stream.position_x === x && stream.position_y === y)
    },
    
    // 获取流状态
    getStreamStatus(streamId) {
      if (!streamId || !this.streamStatus[streamId]) {
        console.log(`⚠️ 流 ${streamId} 状态信息不存在`)
        return 'stopped'
      }
      const status = this.streamStatus[streamId]
      console.log(`🔍 流 ${streamId} 详细状态:`, status)
      
      // 检查不同的状态字段可能性
      let isRunning = false
      if (status.status && typeof status.status === 'object' && status.status.is_running !== undefined) {
        isRunning = status.status.is_running
      } else if (status.is_running !== undefined) {
        isRunning = status.is_running
      } else if (status.status === 'running') {
        isRunning = true
      }
      
      console.log(`🎯 流 ${streamId} 运行状态: ${isRunning}`)
      return isRunning ? 'running' : 'stopped'
    },
    
    // 获取流状态文本
    getStreamStatusText(streamId) {
      const status = this.getStreamStatus(streamId)
      return status === 'running' ? '运行中' : '已停止'
    },
    
    // 获取流统计信息
    getStreamStats(streamId) {
      if (!streamId || !this.streamStatus[streamId]) return ''
      const status = this.streamStatus[streamId]
      return `FPS: ${status.fps || 0} | 检测: ${status.detection_count || 0}`
    },
    
    // 开始RTSP更新循环
    startRTSPUpdate() {
      if (this.rtspUpdateInterval) {
        clearInterval(this.rtspUpdateInterval)
      }
      
      this.rtspUpdateInterval = setInterval(async () => {
        if (this.detectionMode === 'rtsp' && this.rtspStreams.length > 0) {
          await this.updateRTSPData()
        }
      }, 500) // 减少到500ms，提高实时性
    },
    
    // 停止RTSP更新循环
    stopRTSPUpdate() {
      if (this.rtspUpdateInterval) {
        clearInterval(this.rtspUpdateInterval)
        this.rtspUpdateInterval = null
      }
    },
    
    // 更新RTSP数据
    async updateRTSPData() {
      try {
        await this.updateStreamsStatus()
        
        for (const stream of this.rtspStreams) {
          const status = this.getStreamStatus(stream.id)
          console.log(`📊 流 ${stream.id} (${stream.name}) 状态: ${status}`)
          
          if (status === 'running') {
            await this.updateStreamFrame(stream.id)
          } else {
            console.log(`⚠️ 流 ${stream.id} 未运行，状态: ${status}`)
          }
        }
      } catch (error) {
        console.error('❌ 更新RTSP数据失败:', error)
      }
    },
    
    // 更新所有流状态
    async updateStreamsStatus() {
      try {
        const response = await fetch(`http://localhost:5000/api/rtsp/status?user_id=${this.$store.getters.currentUser?.id || 1}`)
        const data = await response.json()
        
        if (data.success) {
          // 清空并重新赋值以确保响应式更新
          Object.keys(this.streamStatus).forEach(key => {
            delete this.streamStatus[key]
          })
          Object.assign(this.streamStatus, data.streams_status)
          console.log('📊 流状态已更新:', Object.keys(this.streamStatus).length, '个流')
        }
      } catch (error) {
        console.error('❌ 更新流状态失败:', error)
      }
    },
    
    // 更新单个流的帧
    async updateStreamFrame(streamId) {
      try {
        const response = await fetch(`http://localhost:5000/api/rtsp/streams/${streamId}/frame`)
        const data = await response.json()
        
        if (data.success && data.frame) {
          // Vue 3 响应式更新
          this.streamFrames[streamId] = data.frame
          // 强制触发视图更新
          this.$nextTick(() => {
            this.$forceUpdate()
          })
          console.log(`🖼️ 更新流 ${streamId} 的帧`)
        } else {
          console.warn(`⚠️ 流 ${streamId} 帧获取失败:`, data.message)
        }
      } catch (error) {
        console.error(`❌ 流 ${streamId} 帧更新异常:`, error)
      }
    },
    
    // 启动单个流
    async startSingleStream(streamId) {
      try {
        console.log(`🚀 启动流 ${streamId}`)
        const response = await fetch(`http://localhost:5000/api/rtsp/streams/${streamId}/start`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: this.$store.getters.currentUser?.id || 1
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          console.log(`✅ 流 ${streamId} 启动成功`)
          ElMessage.success(data.message)
          await this.updateStreamsStatus()
        } else {
          console.error(`❌ 流 ${streamId} 启动失败:`, data.message)
          ElMessage.error(data.message)
        }
      } catch (error) {
        console.error(`❌ 启动流 ${streamId} 异常:`, error)
        ElMessage.error(`启动流失败: ${error.message}`)
      }
    },

    // 切换流状态
    async toggleStream(stream) {
      try {
        const isRunning = this.getStreamStatus(stream.id) === 'running'
        const action = isRunning ? 'stop' : 'start'
        
        console.log(`🔄 ${action === 'start' ? '启动' : '停止'}流 ${stream.id} (${stream.name})`)
        
        const response = await fetch(`http://localhost:5000/api/rtsp/streams/${stream.id}/${action}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: this.$store.getters.currentUser?.id || 1
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          console.log(`✅ 流 ${stream.id} ${action === 'start' ? '启动' : '停止'}成功`)
          ElMessage.success(data.message)
          await this.updateStreamsStatus()
        } else {
          console.error(`❌ 流 ${stream.id} ${action === 'start' ? '启动' : '停止'}失败:`, data.message)
          ElMessage.error(data.message)
        }
      } catch (error) {
        console.error(`❌ 操作流 ${stream.id} 异常:`, error)
        ElMessage.error(`操作流失败: ${error.message}`)
      }
    },
    
    // 启动所有流
    async startAllStreams() {
      try {
        const response = await fetch('http://localhost:5000/api/rtsp/streams/start-all', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            user_id: this.$store.getters.currentUser?.id || 1
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          await this.updateStreamsStatus()
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error(`启动所有流失败: ${error.message}`)
      }
    },
    
    // 停止所有流
    async stopAllStreams() {
      try {
        const response = await fetch('http://localhost:5000/api/rtsp/streams/stop-all', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          await this.updateStreamsStatus()
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error(`停止所有流失败: ${error.message}`)
      }
    },
    
    // 编辑流
    editStream(stream) {
      this.editingStream = stream
      this.streamForm = {
        name: stream.name,
        url: stream.url,
        username: stream.username || '',
        password: stream.password || '',
        model_path: stream.model_path,
        detection_enabled: stream.detection_enabled,
        tracking_enabled: stream.tracking_enabled,
        counting_enabled: stream.counting_enabled,
        alert_enabled: stream.alert_enabled,
        is_active: stream.is_active
      }
      this.showAddStreamDialog = true
    },
    
    // 删除流
    async deleteStream(streamOrId) {
      // 在函数开始就声明变量，确保在整个函数作用域内可用
      let stream;
      let streamId;
      
      try {
        // 兼容处理：可能传入的是stream对象或者id
        if (typeof streamOrId === 'object' && streamOrId !== null) {
          // 传入的是stream对象
          stream = streamOrId;
          streamId = stream.id;
        } else {
          // 传入的是id，需要查找对应的stream对象
          streamId = streamOrId;
          stream = this.rtspStreams.find(s => s.id === streamId);
          if (!stream) {
            ElMessage.error('找不到要删除的流');
            return;
          }
        }
        
        console.log('🗑️ 准备删除流:', stream.name, '(ID:', streamId, ')');
        
        const result = await this.$confirm(
          `确定要删除流 "${stream.name}" 吗？\n\n删除后将无法恢复，请谨慎操作。`, 
          '确认删除', 
          {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
            dangerouslyUseHTMLString: false,
            distinguishCancelAndClose: true
          }
        )
        
        console.log('🚀 用户确认删除，发送请求...');
        
        // 添加到删除中状态
        this.deletingStreamIds.add(streamId);
        
        const response = await fetch(`http://localhost:5000/api/rtsp/streams/${streamId}?user_id=${this.$store.getters.currentUser?.id || 1}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json'
          }
        })
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json()
        
        if (data.success) {
          console.log('✅ 流删除成功');
          ElMessage.success(data.message || '流删除成功');
          
          // 清理本地状态
          delete this.streamFrames[streamId];
          delete this.streamStatus[streamId];
          
          // 重新加载流列表
          await this.loadRTSPStreams();
          
          // 如果删除的是当前预览的流，关闭预览
          if (this.currentPreviewStream && this.currentPreviewStream.id === streamId) {
            this.closeStreamPreview();
          }
        } else {
          console.error('❌ 删除失败:', data.message);
          ElMessage.error(data.message || '删除流失败');
        }
      } catch (error) {
        if (error === 'cancel') {
          console.log('⚠️ 用户取消删除操作');
        } else {
          console.error('❌ 删除流异常:', error);
          ElMessage.error(`删除流失败: ${error.message || '未知错误'}`);
        }
      } finally {
        // 清理删除状态 - streamId现在在函数作用域内，一定是可用的
        if (streamId !== undefined) {
          this.deletingStreamIds.delete(streamId);
        }
      }
    },
    
    // 保存流配置
    async saveStream() {
      try {
        await this.$refs.streamFormRef.validate()
        
        this.streamSaving = true
        
        const streamData = {
          ...this.streamForm,
          user_id: this.$store.getters.currentUser?.id || 1
        }
        
        let response
        if (this.editingStream) {
          response = await fetch(`http://localhost:5000/api/rtsp/streams/${this.editingStream.id}`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(streamData)
          })
        } else {
          response = await fetch('http://localhost:5000/api/rtsp/streams', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(streamData)
          })
        }
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          this.showAddStreamDialog = false
          await this.loadRTSPStreams()
          
          // 自动启动新创建的流
          if (data.stream && data.stream.id) {
            console.log('🚀 自动启动新创建的流:', data.stream.id)
            setTimeout(async () => {
              await this.startSingleStream(data.stream.id)
            }, 1000) // 等待1秒后启动
          }
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        if (error.message) {
          ElMessage.error(`保存流失败: ${error.message}`)
        }
      } finally {
        this.streamSaving = false
      }
    },
    
    // 重置流表单
    resetStreamForm() {
      this.editingStream = null
      this.streamForm = {
        name: '',
        url: '',
        username: '',
        password: '',
        model_path: 'yolov8n.pt',
        detection_enabled: true,
        tracking_enabled: false,
        counting_enabled: false,
        alert_enabled: false,
        is_active: true
      }
      
      if (this.$refs.streamFormRef) {
        this.$refs.streamFormRef.clearValidate()
      }
    },
    
    // 测试RTSP连接
    async testRTSPConnection() {
      if (!this.streamForm.url) {
        ElMessage.error('请先输入RTSP地址')
        return
      }
      
      this.testingConnection = true
      
      try {
        const response = await fetch('http://localhost:5000/api/rtsp/test-connection', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            url: this.streamForm.url,
            username: this.streamForm.username,
            password: this.streamForm.password
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
        } else {
          ElMessage.error(data.message)
        }
      } catch (error) {
        ElMessage.error(`连接测试失败: ${error.message}`)
      } finally {
        this.testingConnection = false
      }
    },
    
    // 打开流预览
    openStreamPreview(stream) {
      if (!stream) return
      
      console.log('🔍 打开流预览:', stream.name)
      this.currentPreviewStream = stream
      this.showPreviewDialog = true
    },
    
    // 关闭流预览
    closeStreamPreview() {
      console.log('❌ 关闭流预览')
      this.showPreviewDialog = false
      this.currentPreviewStream = null
    },
    
    // 刷新预览
    async refreshPreview() {
      if (!this.currentPreviewStream) return
      
      console.log('🔄 刷新预览:', this.currentPreviewStream.name)
      try {
        await this.updateStreamFrame(this.currentPreviewStream.id)
        ElMessage.success('预览已刷新')
      } catch (error) {
        console.error('刷新预览失败:', error)
        ElMessage.error('刷新预览失败')
      }
    },
    
    // 创建测试流
    async createTestStream() {
      try {
        const testStream = {
          name: `测试流-${Date.now()}`,
          url: 'test_image.jpg', // 使用项目中的测试图片
          user_id: this.$store.getters.currentUser?.id || 1,
          detection_enabled: true,
          tracking_enabled: false,
          counting_enabled: false,
          alert_enabled: false,
          is_active: true,
          model_path: 'yolov8n.pt'
        }
        
        console.log('🧪 创建测试流:', testStream)
        
        const response = await fetch('http://localhost:5000/api/rtsp/streams', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(testStream)
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success('测试流创建成功！')
          await this.loadRTSPStreams()
          
          // 自动启动测试流
          if (data.stream && data.stream.id) {
            setTimeout(async () => {
              await this.startSingleStream(data.stream.id)
            }, 1000)
          }
        } else {
          ElMessage.error(`创建测试流失败: ${data.message}`)
        }
      } catch (error) {
        ElMessage.error(`创建测试流异常: ${error.message}`)
      }
    }
  },
  
  beforeUnmount() {
    this.silentStopCamera()
    this.resetUpload()
    this.stopRTSPUpdate()
    
    // 清理resize事件监听器
    if (this.debouncedHandleResize) {
      window.removeEventListener('resize', this.debouncedHandleResize)
    }
  }
}
</script>

<style scoped>
.detection-container {
  max-width: 1400px;
  margin: 0 auto;
}

.mode-selector {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
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
  height: 300px;
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
  max-height: 300px;
  border-radius: 8px;
  /* 优化resize性能 */
  contain: layout;
  transform: translateZ(0);
}

.camera-section {
  margin-bottom: 20px;
}

.camera-container {
  position: relative;
  width: 100%;
  height: 300px;
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.camera-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
  /* 优化resize性能 */
  contain: layout;
  transform: translateZ(0);
}

.camera-placeholder {
  text-align: center;
  color: #999;
}

.camera-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.camera-controls {
  margin-top: 15px;
  text-align: center;
}

.detection-controls {
  margin-top: 20px;
  text-align: center;
}

.detection-controls .el-button {
  margin: 0 10px;
}

.result-content {
  min-height: 400px;
}

.result-media {
  margin-bottom: 20px;
  text-align: center;
}

.result-image, .result-video {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  /* 优化resize性能 */
  contain: layout;
  transform: translateZ(0);
}

.detection-list {
  margin-top: 20px;
}

.bbox-info {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

.empty-result {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 400px;
}

/* RTSP相关样式 */
.rtsp-manager-card {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
}

/* RTSP全宽模式优化 */
.upload-card .rtsp-manager-card {
  margin: -20px;
  border-radius: 8px;
  border: none;
  box-shadow: none;
  background: transparent;
}

.upload-card .rtsp-manager-card .el-card__header {
  padding: 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.upload-card .rtsp-manager-card .el-card__body {
  padding: 20px;
}

/* 响应式设计 - 大屏幕优化 */
@media (min-width: 1400px) {
  .rtsp-grid {
    height: 750px;
    gap: 30px;
  }
}

@media (min-width: 1600px) {
  .rtsp-grid {
    height: 800px;
    gap: 35px;
  }
}

.rtsp-controls {
  display: flex;
  gap: 10px;
}

.rtsp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 25px;
  height: 700px;
  max-width: 100%;
  /* 防止ResizeObserver问题 */
  contain: layout style;
  will-change: auto;
}

.rtsp-grid-item {
  border: 2px dashed #d9d9d9;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
  min-height: 320px;
  background: #fafafa;
  transition: all 0.3s ease;
}

.rtsp-grid-item.has-stream {
  border-color: #409eff;
  border-style: solid;
}

.stream-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.stream-video-container {
  flex: 1;
  position: relative;
  background: #000;
}

.stream-frame {
  width: 100%;
  height: 100%;
  object-fit: cover;
  /* 优化resize性能 */
  contain: layout;
  transform: translateZ(0);
}

.stream-placeholder {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.stream-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.stream-info {
  padding: 10px;
  background: #f5f5f5;
  border-top: 1px solid #ddd;
}

.stream-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.stream-name {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.stream-controls {
  text-align: center;
}

.stream-stats {
  margin-top: 5px;
  color: #666;
  font-size: 11px;
}

.empty-grid-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
  cursor: pointer;
  transition: all 0.3s;
  padding: 30px;
  height: 100%;
}

.empty-grid-item:hover {
  border-color: #409eff;
  color: #409eff;
}

.add-stream-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.quick-actions {
  margin-top: 15px;
  display: flex;
  gap: 10px;
  flex-direction: column;
}

/* 新的流布局样式 */
.stream-header-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.4) 70%, transparent 100%);
  color: white;
  padding: 8px 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 10;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.stream-title-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stream-title-info h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
}

.stream-control-buttons {
  display: flex;
  opacity: 0.9;
}

.stream-control-buttons:hover {
  opacity: 1;
}

.stream-video-container {
  position: relative;
  cursor: pointer;
  border-radius: 8px;
  overflow: hidden;
}

.stream-video-container:hover .preview-overlay {
  opacity: 1;
}

.preview-overlay {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: linear-gradient(0deg, rgba(0,0,0,0.8) 0%, rgba(0,0,0,0.4) 70%, transparent 100%);
  color: white;
  text-align: center;
  padding: 10px;
  opacity: 0;
  transition: opacity 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 12px;
}

.stream-stats-bar {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  z-index: 5;
}

.stream-container {
  position: relative;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
}

/* 预览对话框样式 */
.preview-container {
  display: flex;
  flex-direction: column;
  height: 70vh;
}

.preview-video {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 15px;
}

.preview-frame {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.preview-placeholder {
  color: #666;
  text-align: center;
}

.preview-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.preview-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 0;
  border-top: 1px solid #eee;
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.preview-stats {
  color: #666;
  font-size: 14px;
}

/* 对话框样式 */
.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 5px;
}

.feature-settings {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>