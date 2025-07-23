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
      </el-radio-group>
    </el-card>
    
    <el-row :gutter="20">
      <!-- 左侧：上传和控制区域 -->
      <el-col :span="12">
        <el-card class="upload-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>{{ getModeTitle() }}</span>
              <el-button 
                v-if="detectionMode === 'camera' && !isCameraActive"
                type="primary" 
                @click="startCamera" 
                :loading="$store.state.isLoading"
              >
                启动摄像头
              </el-button>
              <el-button 
                v-if="detectionMode === 'camera' && isCameraActive"
                type="danger" 
                @click="stopCamera"
              >
                停止摄像头
              </el-button>
              <el-button 
                v-if="detectionMode === 'camera' && isCameraActive && trackingSettings.enableTracking"
                type="warning" 
                @click="resetTracking"
              >
                <el-icon><RefreshRight /></el-icon>
                重置跟踪
              </el-button>
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
                  <p v-if="detectionMode === 'image_seg'" class="upload-tip seg-tip">
                    🎭 分割模式：将显示详细的目标轮廓和彩色掩码
                  </p>
                </div>
              </div>
              <img v-else :src="imageUrl" class="uploaded-image" alt="上传的图片">
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
                  <p v-if="detectionMode === 'video_seg'" class="upload-tip seg-tip">
                    🎭 分割模式：将在视频中显示彩色分割掩码
                  </p>
                </div>
              </div>
              <video v-else :src="videoUrl" class="uploaded-video" controls>
                您的浏览器不支持视频播放
              </video>
            </el-upload>
          </div>
          
          <!-- 摄像头 -->
          <div v-if="detectionMode === 'camera'" class="camera-section">
            <div class="camera-container" :class="{ 'camera-overlay-container': isCameraActive }">
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
              
              <!-- 实时检测框叠加层 -->
              <div v-if="isCameraActive" class="camera-detection-overlay">
                <!-- 如果启用跟踪，只显示跟踪框 -->
                <template v-if="trackingSettings.enableTracking">
                  <div 
                    v-for="(track, index) in realtimeTrackingResults" 
                    :key="`track-${track.id}-${index}`"
                    class="tracking-box"
                    :style="getTrackingBoxStyle(track)"
                  >
                    <span class="tracking-label">
                      ID:{{ track.id }} {{ track.class }}: {{ (track.confidence * 100).toFixed(1) }}%
                    </span>
                  </div>
                </template>
                
                <!-- 如果没有启用跟踪，只显示检测框 -->
                <template v-else>
                  <div 
                    v-for="(detection, index) in realtimeDetections" 
                    :key="`detection-${detection.confidence}-${index}`"
                    class="detection-box"
                    :style="getDetectionBoxStyle(detection)"
                  >
                    <span class="detection-label">
                      {{ detection.class }}: {{ (detection.confidence * 100).toFixed(1) }}%
                    </span>
                  </div>
                </template>
              </div>
              
              <div v-if="!isCameraActive" class="camera-placeholder">
                <el-icon class="camera-icon"><Camera /></el-icon>
                <p>点击上方"启动摄像头"开始实时检测</p>
              </div>
            </div>
          </div>
          
          <!-- 分割设置 -->
          <div class="segmentation-controls" v-if="isSegmentationMode">
            <el-card class="seg-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>分割可视化设置</span>
                </div>
              </template>
              
              <el-form label-width="100px" size="small">
                <el-form-item label="显示掩码">
                  <el-switch v-model="segmentationSettings.showMasks" />
                  <div class="setting-desc">
                    显示彩色分割掩码，突出显示目标的精确轮廓
                  </div>
                </el-form-item>
                
                <el-form-item label="显示边界框">
                  <el-switch v-model="segmentationSettings.showBoxes" />
                  <div class="setting-desc">
                    显示目标检测边界框
                  </div>
                </el-form-item>
                
                <el-form-item label="显示标签">
                  <el-switch v-model="segmentationSettings.showLabels" />
                  <div class="setting-desc">
                    显示类别名称和置信度
                  </div>
                </el-form-item>
                
                <el-form-item label="掩码透明度">
                  <el-slider 
                    v-model="segmentationSettings.maskAlpha" 
                    :min="0.1" 
                    :max="0.9" 
                    :step="0.1"
                    show-input
                    style="width: 200px;"
                  />
                  <div class="setting-desc">
                    调整分割掩码的透明度，值越小掩码越透明
                  </div>
                </el-form-item>
                
                <el-form-item label="置信度阈值">
                  <el-slider 
                    v-model="segmentationSettings.confThreshold" 
                    :min="0.1" 
                    :max="0.9" 
                    :step="0.05"
                    show-input
                    style="width: 200px;"
                  />
                  <div class="setting-desc">
                    只显示置信度大于此阈值的检测结果
                  </div>
                </el-form-item>
              </el-form>
            </el-card>
          </div>
          
          <!-- 跟踪和计数设置 -->
          <div class="tracking-controls" v-if="detectionMode !== 'image' && detectionMode !== 'image_seg'">
            <el-card class="tracking-card" shadow="never">
              <template #header>
                <div class="card-header">
                  <span>跟踪和计数设置</span>
                </div>
              </template>
              
              <el-form label-width="100px" size="small">
                <el-form-item label="启用跟踪">
                  <el-switch 
                    v-model="trackingSettings.enableTracking" 
                    @change="onTrackingSettingsChange"
                  />
                </el-form-item>
                
                <el-form-item label="启用计数">
                  <el-switch 
                    v-model="trackingSettings.enableCounting" 
                    @change="onTrackingSettingsChange"
                  />
                </el-form-item>
                
                <el-form-item label="启用预警" v-if="trackingSettings.enableTracking">
                  <el-switch 
                    v-model="trackingSettings.enableAlert" 
                    @change="onTrackingSettingsChange"
                  />
                  <div v-if="trackingSettings.enableAlert" class="alert-info">
                    <el-text type="warning" size="small">
                      <el-icon><Warning /></el-icon>
                      新目标出现时将自动保存预警帧并记录
                    </el-text>
                  </div>
                </el-form-item>
                
                <el-form-item v-if="trackingSettings.enableCounting" label="说明">
                  <div class="counting-info">
                    <p><strong>累积计数:</strong> 从视频开始到结束，总共出现过的不同ID数量</p>
                    <p><strong>当前屏幕:</strong> 当前时刻屏幕内可见的目标数量</p>
                    <p><strong>自动统计:</strong> 系统将自动统计所有检测到的类别，并在检测结果中显示详细统计信息</p>
                  </div>
                </el-form-item>
              </el-form>
            </el-card>
          </div>
          
          <!-- 检测控制 -->
          <div class="detection-controls" v-if="detectionMode !== 'camera'">
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
      <el-col :span="12">
        <el-card class="result-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>检测结果</span>
              <div class="result-stats">
                <el-tag v-if="detectionResult.detections" type="success">
                  检测到 {{ detectionResult.detections.length }} 个目标
                </el-tag>
                <el-tag v-if="detectionResult.segmentation_results" type="warning">
                  分割掩码: {{ detectionResult.segmentation_results.masks_count || 0 }}
                </el-tag>
                <el-tag v-if="detectionResult.model_type === 'segmentation'" type="info">
                  {{ detectionResult.model_type === 'segmentation' ? '分割模式' : '检测模式' }}
                </el-tag>
                <el-tag v-if="detectionResult.tracking_results" type="primary">
                  跟踪到 {{ detectionResult.tracking_results.length }} 个轨迹
                </el-tag>
                <el-tag v-if="detectionResult.counting_results || currentCounts" type="warning">
                  累积计数: {{ getTotalCount() }}
                </el-tag>
                <el-tag v-if="detectionResult.counting_results || currentCounts" type="info">
                  当前屏幕: {{ getCurrentScreenCount() }}
                </el-tag>
              </div>
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
                @click="openImagePreview(getResultImageUrl())"
              >
              <div class="image-overlay">
                <el-button type="primary" @click="openImagePreview(getResultImageUrl())">
                  <el-icon><ZoomIn /></el-icon>
                  点击放大查看{{ detectionMode === 'image_seg' ? '分割结果' : '' }}
                </el-button>
              </div>
            </div>
            
            <!-- 检测结果视频 -->
            <div v-if="detectionResult.result_video && (detectionMode === 'video' || detectionMode === 'video_seg')" class="result-media">
              <video 
                :src="getResultVideoUrl()" 
                class="result-video" 
                controls 
                preload="metadata"
                @error="handleVideoError"
                @loadstart="onVideoLoadStart"
                @loadeddata="onVideoLoaded"
              >
                您的浏览器不支持视频播放
              </video>
              <div class="video-overlay">
                <el-button type="primary" @click="openVideoPreview(getResultVideoUrl())">
                  <el-icon><ZoomIn /></el-icon>
                  全屏查看{{ detectionMode === 'video_seg' ? '分割结果' : '' }}
                </el-button>
              </div>
            </div>
            
            <!-- 检测结果列表 -->
            <div v-if="detectionResult.detections && detectionResult.detections.length > 0" class="detection-list">
              <h4>检测详情</h4>
              <el-table :data="detectionResult.detections" style="width: 100%" size="small" max-height="300">
                <el-table-column prop="class" label="类别" width="120">
                  <template #default="scope">
                    <el-tag 
                      :type="isWatermarkClass(scope.row.class) ? 'warning' : 'primary'"
                      effect="light"
                    >
                      {{ scope.row.class }}
                      <el-icon v-if="isWatermarkClass(scope.row.class)" style="margin-left: 4px;">
                        <Warning />
                      </el-icon>
                    </el-tag>
                  </template>
                </el-table-column>
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
                <el-table-column label="帧数" v-if="detectionMode === 'video'" width="80">
                  <template #default="scope">
                    {{ scope.row.frame || '--' }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120">
                  <template #default="scope">
                    <el-button 
                      v-if="isWatermarkClass(scope.row.class)"
                      type="warning"
                      size="mini"
                      @click="handleWatermarkRemoval(scope.row)"
                    >
                      <el-icon><MagicStick /></el-icon>
                      去除
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            
            <!-- 类别计数统计 -->
            <div v-if="trackingSettings.enableCounting && (classCountsData.length > 0 || (detectionMode === 'camera' && isCameraActive))" class="class-counts">
              <h4>类别计数统计</h4>
              <div v-if="classCountsData.length > 0">
                <el-table 
                  :data="paginatedClassCounts" 
                  style="width: 100%" 
                  size="small"
                  :show-header="true"
                >
                  <el-table-column prop="class" label="类别" width="120">
                    <template #default="scope">
                      <el-tag :type="getClassTagType(scope.row.class)">
                        {{ scope.row.class }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="currentScreen" label="当前屏幕" width="100" align="center">
                    <template #default="scope">
                      <span class="count-number">{{ scope.row.currentScreen }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column prop="cumulativeTotal" label="累积计数" width="100" align="center">
                    <template #default="scope">
                      <span class="count-number cumulative">{{ scope.row.cumulativeTotal }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="计数比例" align="center">
                    <template #default="scope">
                      <el-progress 
                        :percentage="getCountPercentage(scope.row.cumulativeTotal)" 
                        :stroke-width="6"
                        :show-text="false"
                        :color="getProgressColor(scope.row.cumulativeTotal)"
                      />
                      <span class="percentage-text">{{ getCountPercentage(scope.row.cumulativeTotal) }}%</span>
                    </template>
                  </el-table-column>
                </el-table>
                
                <!-- 分页 -->
                <div v-if="classCountsTotal > countsPagination.pageSize" class="counts-pagination">
                  <el-pagination
                    v-model:current-page="countsPagination.currentPage"
                    :page-size="countsPagination.pageSize"
                    :total="classCountsTotal"
                    layout="prev, pager, next, jumper"
                    @current-change="handleCountsPageChange"
                    small
                  />
                </div>
              </div>
              <div v-else class="empty-counts">
                <el-empty description="暂无计数数据" :image-size="60" />
              </div>
            </div>
            
            <!-- 空状态 -->
            <div v-if="!detectionResult.detections && !$store.state.isLoading && detectionMode !== 'camera'" class="empty-result">
              <el-empty description="暂无检测结果">
                <el-button type="primary" @click="startDetection" v-if="canDetect">
                  开始检测
                </el-button>
              </el-empty>
            </div>
            
            <!-- 摄像头模式的空状态 -->
            <div v-if="detectionMode === 'camera' && !isCameraActive && !$store.state.isLoading" class="empty-result">
              <el-empty description="请启动摄像头开始实时检测" />
            </div>
            
            <!-- 实时检测统计 -->
            <div v-if="detectionMode === 'camera' && isCameraActive" class="realtime-stats">
              <el-row :gutter="20">
                <el-col :span="6">
                  <el-statistic title="实时检测目标" :value="realtimeDetections.length" />
                </el-col>
                <el-col :span="6" v-if="trackingSettings.enableTracking">
                  <el-statistic title="跟踪轨迹" :value="realtimeTrackingResults.length" />
                </el-col>
                <el-col :span="6" v-if="trackingSettings.enableCounting">
                  <el-statistic title="累积计数" :value="getTotalCount()" />
                </el-col>
                <el-col :span="6" v-if="trackingSettings.enableCounting">
                  <el-statistic title="当前屏幕" :value="getCurrentScreenCount()" />
                </el-col>
              </el-row>
            </div>
            
            <!-- 加载状态 -->
            <div v-if="$store.state.isLoading" class="loading-result">
              <el-loading 
                element-loading-text="正在进行AI检测分析..."
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
      v-model="showImagePreview"
      title="检测结果 - 放大查看"
      width="90%"
      top="5vh"
      destroy-on-close
      @close="closeImagePreview"
    >
      <div class="preview-container">
        <img 
          v-if="previewImageUrl" 
          :src="previewImageUrl" 
          class="preview-image" 
          alt="检测结果放大图"
          :style="{ 
            transform: `scale(${zoomLevel})`,
            cursor: 'grab'
          }"
          @load="onPreviewImageLoad"
          @error="onPreviewImageError"
          @mousedown="startDrag"
          @mousemove="drag"
          @mouseup="endDrag"
          @wheel="handleWheel"
        >
        <div class="preview-controls">
          <el-button-group>
            <el-button @click="zoomIn">
              <el-icon><ZoomIn /></el-icon>
              放大
            </el-button>
            <el-button @click="zoomOut">
              <el-icon><ZoomOut /></el-icon>
              缩小
            </el-button>
            <el-button @click="resetZoom">
              <el-icon><RefreshRight /></el-icon>
              重置
            </el-button>
            <el-button @click="downloadImage">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
          </el-button-group>
          <div class="zoom-info">
            缩放: {{ Math.round(zoomLevel * 100) }}%
          </div>
        </div>
      </div>
    </el-dialog>
    
    <!-- 视频预览对话框 -->
    <el-dialog
      v-model="showVideoPreview"
      title="检测结果 - 全屏查看"
      width="90%"
      top="5vh"
      destroy-on-close
      @close="closeVideoPreview"
    >
      <div class="preview-container">
        <video 
          v-if="previewVideoUrl" 
          :src="previewVideoUrl" 
          class="preview-video" 
          controls 
          autoplay
        >
          您的浏览器不支持视频播放
        </video>
        <div class="preview-controls">
          <el-button @click="downloadVideo">
            <el-icon><Download /></el-icon>
            下载视频
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { 
  Picture, 
  VideoPlay, 
  Camera, 
  Plus, 
  Search, 
  RefreshRight,
  ZoomIn,
  ZoomOut,
  Download,
  Warning,
  MagicStick
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
    ZoomIn,
    ZoomOut,
    Download,
    Warning,
    MagicStick
  },
  data() {
    return {
      detectionMode: 'image',
      imageUrl: '',
      videoUrl: '',
      videoFile: null,
      isCameraActive: false,
      detectionResult: {},
      realtimeDetections: [],
      realtimeTrackingResults: [],
      currentCounts: {},
      cameraStream: null,
      detectionInterval: null,
      // 添加停止标志，确保异步操作不会在停止后继续
      detectionStopped: false,
      // 添加正在进行的请求数量计数
      activeRequests: 0,
      uploadAction: 'http://localhost:5000/api/detect_image',
      videoUploadAction: 'http://localhost:5000/api/detect_video',
      videoLoading: false,
      showImagePreview: false,
      showVideoPreview: false,
      previewImageUrl: '',
      previewVideoUrl: '',
      zoomLevel: 1,
      imageWidth: 0,
      imageHeight: 0,
      isDragging: false,
      dragStartX: 0,
      dragStartY: 0,
      // 新增跟踪和计数相关数据
      trackingSettings: {
        enableTracking: false,
        enableCounting: false,
        enableAlert: false,
        countingClass: ''
      },
      // 新增分割设置
      segmentationSettings: {
        showMasks: true,
        showBoxes: true,
        showLabels: true,
        maskAlpha: 0.4,
        confThreshold: 0.25,
        iouThreshold: 0.45
      },
      availableClasses: [],
      // 新增类别计数显示相关数据
      classCounts: {
        currentScreen: {},
        cumulativeTotal: {},
        totalScreenCount: 0,
        totalCumulativeCount: 0
      },
      // 类别计数分页数据
      countsPagination: {
        currentPage: 1,
        pageSize: 10,
        total: 0
      }
    }
  },
  computed: {
    canDetect() {
      return (this.detectionMode === 'image' && this.imageUrl) || 
             (this.detectionMode === 'image_seg' && this.imageUrl) ||
             (this.detectionMode === 'video' && this.videoFile) ||
             (this.detectionMode === 'video_seg' && this.videoFile)
    },
    
    isSegmentationMode() {
      return this.detectionMode === 'image_seg' || this.detectionMode === 'video_seg'
    },
    
    // 获取类别计数数据
    classCountsData() {
      let currentScreen = {}
      let cumulativeTotal = {}
      
      if (this.detectionMode === 'camera' && this.currentCounts) {
        // 摄像头模式：从currentCounts获取数据
        currentScreen = this.currentCounts
        cumulativeTotal = this.currentCounts // 实时模式下累积计数等于当前计数
      } else if (this.detectionResult.count_summary) {
        // 视频模式：从count_summary获取数据
        currentScreen = this.detectionResult.count_summary.current_screen || {}
        cumulativeTotal = this.detectionResult.count_summary.cumulative_total || {}
      }
      
      // 合并所有类别，创建完整的计数数据
      const allClasses = new Set([...Object.keys(currentScreen), ...Object.keys(cumulativeTotal)])
      const classCountsArray = Array.from(allClasses).map(className => ({
        class: className,
        currentScreen: currentScreen[className] || 0,
        cumulativeTotal: cumulativeTotal[className] || 0
      }))
      
      // 按累积计数排序
      classCountsArray.sort((a, b) => b.cumulativeTotal - a.cumulativeTotal)
      
      return classCountsArray
    },
    
    // 获取分页后的类别计数数据
    paginatedClassCounts() {
      const start = (this.countsPagination.currentPage - 1) * this.countsPagination.pageSize
      const end = start + this.countsPagination.pageSize
      return this.classCountsData.slice(start, end)
    },
    
    // 获取类别计数总数
    classCountsTotal() {
      return this.classCountsData.length
    }
  },
  
  watch: {
    // 监听类别计数数据变化
    classCountsData() {
      this.updateClassCounts()
    },
    
    // 监听实时计数数据变化
    currentCounts() {
      this.updateClassCounts()
    },
    
    // 监听检测结果变化
    detectionResult() {
      this.updateClassCounts()
    }
  },
  
  async mounted() {
    // 加载可用类别
    await this.loadAvailableClasses()
  },
  methods: {
    getModeTitle() {
      const titles = {
        image: '图片上传检测',
        image_seg: '图片分割检测',
        video: '视频上传检测',
        video_seg: '视频分割检测',
        camera: '摄像头实时检测'
      }
      return titles[this.detectionMode]
    },
    
    getUploadAction() {
      if (this.detectionMode === 'image_seg') {
        return 'http://localhost:5000/api/segment_image'
      } else if (this.detectionMode === 'video_seg') {
        return 'http://localhost:5000/api/segment_video'
      } else if (this.detectionMode === 'image') {
        return 'http://localhost:5000/api/detect_image'
      } else {
        return this.videoUploadAction
      }
    },
    
    getUploadData() {
      const baseData = {
        user_id: this.$store.getters.currentUser?.id || 1
      }
      
      if (this.isSegmentationMode) {
        return {
          ...baseData,
          show_masks: this.segmentationSettings.showMasks,
          show_boxes: this.segmentationSettings.showBoxes,
          show_labels: this.segmentationSettings.showLabels,
          mask_alpha: this.segmentationSettings.maskAlpha,
          conf_threshold: this.segmentationSettings.confThreshold,
          iou_threshold: this.segmentationSettings.iouThreshold
        }
      } else {
        return {
          ...baseData,
          enable_tracking: this.trackingSettings.enableTracking,
          enable_counting: this.trackingSettings.enableCounting,
          enable_alert: this.trackingSettings.enableAlert,
          counting_class: this.trackingSettings.countingClass
        }
      }
    },
    
    // 获取总计数
    getTotalCount() {
      // 对于实时摄像头模式，优先显示累积计数
      if (this.detectionMode === 'camera' && this.currentCounts && Object.keys(this.currentCounts).length > 0) {
        return Object.values(this.currentCounts).reduce((sum, count) => sum + count, 0)
      }
      
      // 对于视频模式，优先显示累积计数
      if (this.detectionResult.count_summary) {
        const cumulativeTotal = this.detectionResult.count_summary.cumulative_total || {}
        return Object.values(cumulativeTotal).reduce((sum, count) => sum + count, 0)
      }
      
      // 备用：使用API返回的total_count
      if (this.detectionResult.total_count !== undefined) {
        return this.detectionResult.total_count
      }
      
      // 最后备用逻辑
      if (this.currentCounts && Object.keys(this.currentCounts).length > 0) {
        return Object.values(this.currentCounts).reduce((sum, count) => sum + count, 0)
      }
      
      return 0
    },
    
    // 获取当前屏幕内计数
    getCurrentScreenCount() {
      // 对于实时摄像头模式
      if (this.detectionMode === 'camera' && this.currentCounts && Object.keys(this.currentCounts).length > 0) {
        return Object.values(this.currentCounts).reduce((sum, count) => sum + count, 0)
      }
      
      // 对于视频模式，使用current_screen_count
      if (this.detectionResult.current_screen_count !== undefined) {
        return this.detectionResult.current_screen_count
      }
      
      // 备用：使用count_summary中的current_screen
      if (this.detectionResult.count_summary && this.detectionResult.count_summary.current_screen) {
        const currentScreen = this.detectionResult.count_summary.current_screen
        return Object.values(currentScreen).reduce((sum, count) => sum + count, 0)
      }
      
      return 0
    },
    
    // 加载可用类别
    async loadAvailableClasses() {
      try {
        const response = await fetch('http://localhost:5000/api/model/classes')
        const data = await response.json()
        if (data.success) {
          this.availableClasses = data.classes
        }
      } catch (error) {
        console.error('加载类别失败:', error)
      }
    },
    
    // 跟踪设置变化处理
    async onTrackingSettingsChange() {
      // 如果启用了跟踪，重置跟踪器确保ID从1开始
      if (this.trackingSettings.enableTracking) {
        try {
          const resetResult = await this.$store.dispatch('resetTracker')
          if (resetResult.success) {
            console.log('跟踪器已重置')
          } else {
            console.error('重置跟踪器失败:', resetResult.message)
          }
        } catch (error) {
          console.error('重置跟踪器异常:', error)
        }
      }
      
      // 如果是摄像头模式，需要重新启动检测
      if (this.detectionMode === 'camera' && this.isCameraActive) {
        this.startRealtimeDetection()
      }
    },
    
    // 重置跟踪器
    async resetTracking() {
      try {
        const resetResult = await this.$store.dispatch('resetTracker')
        if (resetResult.success) {
          ElMessage.success('跟踪器已重置')
          this.realtimeTrackingResults = [] // 清空当前显示的跟踪框
          this.currentCounts = {} // 清空计数
        } else {
          ElMessage.error(resetResult.message || '重置跟踪器失败')
        }
      } catch (error) {
        console.error('重置跟踪器异常:', error)
        ElMessage.error('重置跟踪器失败: ' + error.message)
      }
    },

    
    // 获取上传数据
    getUploadData() {
      return {
        user_id: this.$store.getters.currentUser?.id || 1,
        enable_tracking: this.trackingSettings.enableTracking,
        enable_counting: this.trackingSettings.enableCounting,
        enable_alert: this.trackingSettings.enableAlert,
        counting_class: this.trackingSettings.countingClass,
        counting_line: this.trackingSettings.countingLine
      }
    },
    
    handleModeChange() {
      // 静默关闭摄像头，不显示提示
      this.silentStopCamera()
      this.resetUpload()
      this.detectionResult = {}
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
      
      // 保存图片URL用于预览
      this.imageUrl = URL.createObjectURL(file)
      return true
    },
    
    handleImageSuccess(response) {
      if (response.success) {
        // 确保结果稳定显示
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
      // 只保存视频文件用于预览，不立即检测
      this.videoUrl = URL.createObjectURL(uploadFile.raw)
      this.videoFile = uploadFile.raw
      ElMessage.success('视频上传成功，请点击"开始检测"进行分析')
    },
    
    handleVideoSuccess(response) {
      if (response.success) {
        // 确保结果稳定显示
        this.detectionResult = { ...response }
        
        let message = ''
        if (response.model_type === 'segmentation') {
          // 分割模式的消息
          const stats = response.segmentation_stats || {}
          message = `视频分割完成！处理了 ${stats.total_frames || 0} 帧，`
          message += `检测到 ${stats.total_detections || 0} 个目标，`
          message += `生成了 ${stats.total_masks || 0} 个分割掩码`
        } else {
          // 普通检测模式的消息
          message = `视频检测完成！处理了 ${response.processed_frames || 0} 帧，检测到 ${response.total_detections || 0} 个目标`
          
          if (response.tracking_results) {
            message += `，跟踪到 ${response.tracking_count || 0} 个轨迹`
          }
          
          if (response.counting_results) {
            message += `，计数结果: ${response.total_count || 0}`
          }
        }
        
        ElMessage.success(message)
      } else {
        ElMessage.error(response.message)
      }
    },
    
    handleUploadError(error, file, fileList) {
      console.error('上传错误详情:', error)
      if (error.response) {
        const errorData = error.response.data
        if (errorData && errorData.message) {
          ElMessage.error(`上传失败: ${errorData.message}`)
        } else {
          ElMessage.error(`上传失败: HTTP ${error.response.status}`)
        }
      } else {
        ElMessage.error('上传失败: ' + error.message)
      }
    },
    
    // 视频加载事件
    onVideoLoadStart() {
      this.videoLoading = true
      console.log('视频开始加载...')
    },
    
    onVideoLoaded() {
      this.videoLoading = false
      console.log('视频加载完成')
    },
    
    handleImageError(event) {
      console.error('图片加载错误:', event)
      ElMessage.error('图片加载失败，请检查网络连接')
    },
    
    handleVideoError(event) {
      console.error('视频加载错误:', event)
      const video = event.target
      let errorMessage = '视频加载失败'
      
      if (video.error) {
        switch (video.error.code) {
          case 1: // MEDIA_ERR_ABORTED
            errorMessage = '视频加载被中止'
            break
          case 2: // MEDIA_ERR_NETWORK
            errorMessage = '视频网络加载错误'
            break
          case 3: // MEDIA_ERR_DECODE
            errorMessage = '视频解码错误，格式可能不支持'
            break
          case 4: // MEDIA_ERR_SRC_NOT_SUPPORTED
            errorMessage = '视频格式不支持或文件损坏'
            break
          default:
            errorMessage = '视频播放出现未知错误'
        }
      }
      
      ElMessage.error(errorMessage)
      
      // 提供解决建议
      this.$notify({
        title: '视频加载失败',
        message: '建议：1. 检查网络连接 2. 尝试其他视频格式 3. 重新上传视频',
        type: 'warning',
        duration: 8000
      })
    },
    
    // 摄像头相关
    async startCamera() {
      try {
        // 重置停止标志
        this.detectionStopped = false
        this.activeRequests = 0
        
        // 在启动摄像头前先重置跟踪器，确保ID从1开始
        if (this.trackingSettings.enableTracking) {
          const resetResult = await this.$store.dispatch('resetTracker')
          if (resetResult.success) {
            console.log('跟踪器已重置')
          } else {
            console.error('重置跟踪器失败:', resetResult.message)
          }
        }
        
        this.cameraStream = await navigator.mediaDevices.getUserMedia({ 
          video: { 
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'user'
          } 
        })
        
        if (this.$refs.cameraVideo) {
          this.$refs.cameraVideo.srcObject = this.cameraStream
          this.isCameraActive = true
          
          // 等待视频加载后开始检测
          this.$refs.cameraVideo.onloadedmetadata = () => {
            this.startRealtimeDetection()
          }
          
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
      // 设置停止标志，防止异步操作继续
      this.detectionStopped = true
      
      if (this.cameraStream) {
        this.cameraStream.getTracks().forEach(track => track.stop())
        this.cameraStream = null
      }
      if (this.detectionInterval) {
        clearInterval(this.detectionInterval)
        this.detectionInterval = null
      }
      
      // 等待所有异步请求完成后再清理UI
      const cleanup = () => {
      this.isCameraActive = false
      this.realtimeDetections = []
      this.realtimeTrackingResults = []
      this.currentCounts = {}
        this.activeRequests = 0
      }
      
      // 如果有正在进行的请求，等待完成
      if (this.activeRequests > 0) {
        setTimeout(() => {
          cleanup()
        }, 200) // 等待200ms让异步请求完成
      } else {
        cleanup()
      }
    },
    
    startRealtimeDetection() {
      if (this.detectionInterval) {
        clearInterval(this.detectionInterval)
      }
      
      // 重置停止标志
      this.detectionStopped = false
      
      // 在开始检测时清空计数和跟踪结果
      this.currentCounts = {}
      this.realtimeTrackingResults = []
      this.realtimeDetections = []
      
      this.detectionInterval = setInterval(async () => {
        // 双重检查：检查摄像头状态和停止标志
        if (!this.isCameraActive || this.detectionStopped) {
          return
        }
        
        if (this.$refs.cameraVideo && this.$refs.cameraVideo.readyState === 4) {
          const canvas = this.$refs.cameraCanvas
          const video = this.$refs.cameraVideo
          const ctx = canvas.getContext('2d')
          
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
          
          if (canvas.width > 0 && canvas.height > 0) {
            ctx.drawImage(video, 0, 0)
            const imageData = canvas.toDataURL('image/jpeg', 0.8)
            
            try {
              // 再次检查停止标志，防止在停止后发起新请求
              if (this.detectionStopped) {
                return
              }
              
              // 增加活跃请求计数
              this.activeRequests++
              
              const frameData = {
                image: imageData,
                user_id: this.$store.getters.currentUser?.id || 1,
                enable_tracking: this.trackingSettings.enableTracking,
                enable_counting: this.trackingSettings.enableCounting,
                enable_alert: this.trackingSettings.enableAlert,
                counting_class: '' // 统计所有类别
              }
              
              const result = await this.$store.dispatch('processFrame', frameData)
              
              // 减少活跃请求计数
              this.activeRequests = Math.max(0, this.activeRequests - 1)
              
              // 请求完成后再次检查停止标志，防止在停止后更新UI
              if (this.detectionStopped || !this.isCameraActive) {
                return
              }
              
              if (result.success) {
                // 使用Vue的响应式更新，避免闪烁
                this.$nextTick(() => {
                  // 最后一次检查，确保不在停止状态下更新UI
                  if (!this.detectionStopped && this.isCameraActive) {
                  this.realtimeDetections = result.detections && result.detections.length > 0 ? [...result.detections] : []
                  this.realtimeTrackingResults = result.tracking_results && result.tracking_results.length > 0 ? [...result.tracking_results] : []
                  this.currentCounts = result.counting_results ? { ...result.counting_results } : {}
                  }
                })
              } else {
                // 如果检测失败，也要检查停止标志
                this.$nextTick(() => {
                  if (!this.detectionStopped && this.isCameraActive) {
                  this.realtimeDetections = []
                  this.realtimeTrackingResults = []
                  this.currentCounts = {}
                  }
                })
              }
            } catch (error) {
              // 减少活跃请求计数
              this.activeRequests = Math.max(0, this.activeRequests - 1)
              console.error('实时检测失败:', error)
            }
          }
        }
      }, 100) // 全帧检测模式，提高前端调用频率到100ms
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
        
        // 根据模式添加不同的参数
        if (this.detectionMode === 'video_seg') {
          formData.append('user_id', this.$store.getters.currentUser?.id || 1)
          formData.append('show_masks', this.segmentationSettings.showMasks)
          formData.append('show_boxes', this.segmentationSettings.showBoxes)
          formData.append('show_labels', this.segmentationSettings.showLabels)
          formData.append('mask_alpha', this.segmentationSettings.maskAlpha)
          formData.append('conf_threshold', this.segmentationSettings.confThreshold)
          formData.append('iou_threshold', this.segmentationSettings.iouThreshold)
        } else {
          formData.append('user_id', this.$store.getters.currentUser?.id || 1)
          formData.append('enable_tracking', this.trackingSettings.enableTracking)
          formData.append('enable_counting', this.trackingSettings.enableCounting)
          formData.append('enable_alert', this.trackingSettings.enableAlert)
          formData.append('counting_class', '') // 统计所有类别
        }
        
        const uploadUrl = this.detectionMode === 'video_seg' ? 
                         'http://localhost:5000/api/segment_video' : 
                         this.videoUploadAction
        
        const response = await fetch(uploadUrl, {
          method: 'POST',
          body: formData
        })
        
        const data = await response.json()
        
        if (data.success) {
          this.handleVideoSuccess(data)
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
      this.detectionResult = {}
      this.currentCounts = {}
    },
    
    resetAll() {
      this.resetUpload()
      this.silentStopCamera()
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
    
    getDetectionBoxStyle(detection) {
      if (!detection.bbox || !this.$refs.cameraVideo) return { display: 'none' }
      
      const video = this.$refs.cameraVideo
      const container = video.parentElement
      
      // 确保视频已经加载
      if (!video.videoWidth || !video.videoHeight) return { display: 'none' }
      
      const videoRect = video.getBoundingClientRect()
      const containerRect = container.getBoundingClientRect()
      
      const [x1, y1, x2, y2] = detection.bbox
      
      // 计算缩放比例
      const scaleX = videoRect.width / video.videoWidth
      const scaleY = videoRect.height / video.videoHeight
      
      // 计算相对于容器的位置
      const left = (videoRect.left - containerRect.left) + (x1 * scaleX)
      const top = (videoRect.top - containerRect.top) + (y1 * scaleY)
      const width = (x2 - x1) * scaleX
      const height = (y2 - y1) * scaleY
      
      // 确保框在有效范围内
      if (left < 0 || top < 0 || width <= 0 || height <= 0) {
        return { display: 'none' }
      }
      
      return {
        position: 'absolute',
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
        border: '2px solid #00ff00',
        backgroundColor: 'rgba(0, 255, 0, 0.1)',
        pointerEvents: 'none',
        zIndex: 10,
        transition: 'all 0.1s ease-out'
      }
    },
    
    getTrackingBoxStyle(track) {
      if (!track.bbox || !this.$refs.cameraVideo) return { display: 'none' }
      
      const video = this.$refs.cameraVideo
      const container = video.parentElement
      
      // 确保视频已经加载
      if (!video.videoWidth || !video.videoHeight) return { display: 'none' }
      
      const videoRect = video.getBoundingClientRect()
      const containerRect = container.getBoundingClientRect()
      
      const [x1, y1, x2, y2] = track.bbox
      
      // 计算缩放比例
      const scaleX = videoRect.width / video.videoWidth
      const scaleY = videoRect.height / video.videoHeight
      
      // 计算相对于容器的位置
      const left = (videoRect.left - containerRect.left) + (x1 * scaleX)
      const top = (videoRect.top - containerRect.top) + (y1 * scaleY)
      const width = (x2 - x1) * scaleX
      const height = (y2 - y1) * scaleY
      
      // 确保框在有效范围内
      if (left < 0 || top < 0 || width <= 0 || height <= 0) {
        return { display: 'none' }
      }
      
      return {
        position: 'absolute',
        left: `${left}px`,
        top: `${top}px`,
        width: `${width}px`,
        height: `${height}px`,
        border: '2px solid #0066ff',
        backgroundColor: 'rgba(0, 102, 255, 0.1)',
        pointerEvents: 'none',
        zIndex: 11,
        transition: 'all 0.1s ease-out'
      }
    },
    
    openImagePreview(imageUrl) {
      this.previewImageUrl = imageUrl
      this.showImagePreview = true
    },
    
    openVideoPreview(videoUrl) {
      this.previewVideoUrl = videoUrl
      this.showVideoPreview = true
    },
    
    closeImagePreview() {
      this.showImagePreview = false
      this.previewImageUrl = ''
    },
    
    closeVideoPreview() {
      this.showVideoPreview = false
      this.previewVideoUrl = ''
    },
    
    onPreviewImageLoad() {
      const image = new Image()
      image.src = this.previewImageUrl
      image.onload = () => {
        this.imageWidth = image.width
        this.imageHeight = image.height
      }
    },
    
    onPreviewImageError(event) {
      console.error('图片加载错误:', event)
      ElMessage.error('图片加载失败，请检查网络连接')
    },
    
    zoomIn() {
      this.zoomLevel += 0.1
      if (this.zoomLevel > 3) this.zoomLevel = 3
    },
    
    zoomOut() {
      this.zoomLevel -= 0.1
      if (this.zoomLevel < 0.1) this.zoomLevel = 0.1
    },
    
    resetZoom() {
      this.zoomLevel = 1
    },
    
    handleWheel(event) {
      event.preventDefault()
      const delta = event.deltaY > 0 ? -0.05 : 0.05
      this.zoomLevel += delta
      if (this.zoomLevel > 3) this.zoomLevel = 3
      if (this.zoomLevel < 0.1) this.zoomLevel = 0.1
    },
    
    startDrag(event) {
      this.isDragging = true
      this.dragStartX = event.clientX
      this.dragStartY = event.clientY
    },
    
    drag(event) {
      if (!this.isDragging) return
      // 这里可以实现图片拖拽移动功能
    },
    
    endDrag() {
      this.isDragging = false
    },
    
    downloadImage() {
      if (!this.previewImageUrl) return
      
      const link = document.createElement('a')
      link.href = this.previewImageUrl
      link.download = `检测结果_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.jpg`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      ElMessage.success('图片下载已开始')
    },
    
    downloadVideo() {
      if (!this.previewVideoUrl) return
      
      const link = document.createElement('a')
      link.href = this.previewVideoUrl
      link.download = `检测结果_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.mp4`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      ElMessage.success('视频下载已开始')
    },
    
    // 分页处理
    handleCountsPageChange(page) {
      this.countsPagination.currentPage = page
    },
    
    // 更新类别计数
    updateClassCounts() {
      // 更新分页总数
      this.countsPagination.total = this.classCountsTotal
      
      // 如果当前页超出范围，重置为第一页
      if (this.countsPagination.currentPage > Math.ceil(this.classCountsTotal / this.countsPagination.pageSize)) {
        this.countsPagination.currentPage = 1
      }
    },
    
    // 获取类别标签类型
    getClassTagType(className) {
      const tagTypes = {
        'person': 'primary',
        'car': 'success',
        'truck': 'warning',
        'bus': 'info',
        'bicycle': 'danger',
        'motorcycle': 'warning'
      }
      return tagTypes[className] || 'info'
    },
    
    // 获取计数比例
    getCountPercentage(count) {
      if (!this.classCountsData.length) return 0
      const maxCount = Math.max(...this.classCountsData.map(item => item.cumulativeTotal))
      return maxCount === 0 ? 0 : Math.round((count / maxCount) * 100)
    },
    
    // 获取进度条颜色
    getProgressColor(count) {
      const percentage = this.getCountPercentage(count)
      if (percentage >= 80) return '#67c23a'
      if (percentage >= 60) return '#409eff'
      if (percentage >= 40) return '#e6a23c'
      return '#f56c6c'
    },
    
    // 水印相关方法
    isWatermarkClass(className) {
      // 定义水印相关的类别关键词
      const watermarkKeywords = [
        'watermark', 'logo', 'text', 'brand', 'copyright', 
        '水印', '商标', '版权', '标识', 'signature'
      ]
      
      const lowerClassName = className.toLowerCase()
      return watermarkKeywords.some(keyword => lowerClassName.includes(keyword))
    },
    
    async handleWatermarkRemoval(detection) {
      try {
        // 确认用户是否要去除水印
        await this.$confirm(
          `检测到水印类别："${detection.class}"，是否要跳转到去除水印页面进行处理？`,
          '水印检测',
          {
            confirmButtonText: '去除水印',
            cancelButtonText: '取消',
            type: 'warning',
            customClass: 'watermark-confirm-dialog'
          }
        )
        
        // 跳转到去除水印页面
        this.$router.push('/dashboard/watermark-removal')
        
        // 显示提示信息
        this.$message({
          message: '已跳转到去除水印页面，请上传包含水印的文件进行处理',
          type: 'success',
          duration: 3000
        })
        
      } catch {
        // 用户取消操作
      }
    }
  },
  
  beforeUnmount() {
    // 设置停止标志，防止异步操作继续
    this.detectionStopped = true
    this.silentStopCamera()
    this.resetUpload()
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

.result-stats {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.tracking-controls, .segmentation-controls {
  margin-bottom: 20px;
}

.tracking-card, .seg-card {
  background: #f8f9fa;
  border: 1px solid #e9ecef;
}

.tracking-card :deep(.el-card__header), .seg-card :deep(.el-card__header) {
  background: #ffffff;
  border-bottom: 1px solid #e9ecef;
}

.seg-card {
  background: #f0f9ff;
  border: 1px solid #e0f2fe;
}

.seg-card :deep(.el-card__header) {
  background: #f8fafc;
  border-bottom: 1px solid #e0f2fe;
}

.setting-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  line-height: 1.4;
}

.seg-tip {
  color: #059669 !important;
  font-weight: 500;
}

.counting-info {
  padding: 10px;
  background: #f0f9ff;
  border: 1px solid #e0f2fe;
  border-radius: 4px;
  font-size: 13px;
  color: #0369a1;
}

.counting-info p {
  margin: 2px 0;
}

.realtime-stats {
  margin-top: 20px;
  padding: 15px;
  background: #f0f2f5;
  border-radius: 6px;
}

.realtime-stats :deep(.el-statistic__content) {
  font-size: 18px;
  color: #409eff;
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

.camera-overlay-container {
  border-color: #409eff;
}

.camera-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
}

.camera-canvas {
  position: absolute;
  top: 0;
  left: 0;
  visibility: hidden;
}

.camera-placeholder {
  text-align: center;
  color: #999;
}

.camera-icon {
  font-size: 48px;
  margin-bottom: 10px;
}

.camera-detection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 10;
}

.detection-box {
  position: absolute;
  border: 2px solid #00ff00;
  background: rgba(0, 255, 0, 0.1);
  pointer-events: none;
  transition: all 0.3s ease-in-out;
  animation: fadeIn 0.2s ease-out;
}

.tracking-box {
  position: absolute;
  border: 2px solid #0066ff;
  background: rgba(0, 102, 255, 0.1);
  pointer-events: none;
  transition: all 0.3s ease-in-out;
  animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.detection-label {
  position: absolute;
  top: -25px;
  left: 0;
  background: #00ff00;
  color: black;
  padding: 2px 6px;
  font-size: 12px;
  border-radius: 3px;
  white-space: nowrap;
  pointer-events: none;
}

.tracking-label {
  position: absolute;
  top: -25px;
  left: 0;
  background: #0066ff;
  color: white;
  padding: 2px 6px;
  font-size: 12px;
  border-radius: 3px;
  white-space: nowrap;
  pointer-events: none;
}

.detection-controls {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 20px;
}

.result-content {
  position: relative;
  min-height: 400px;
}

.result-media {
  margin-bottom: 20px;
  text-align: center;
  position: relative;
}

.result-image, .result-video {
  max-width: 100%;
  max-height: 350px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  transition: transform 0.3s ease;
}

.result-image:hover, .result-video:hover {
  transform: scale(1.02);
}

.image-overlay, .video-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s ease;
  border-radius: 8px;
}

.result-media:hover .image-overlay,
.result-media:hover .video-overlay {
  opacity: 1;
}

.detection-list {
  margin-top: 20px;
}

.detection-list h4 {
  margin-bottom: 15px;
  color: #333;
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
  height: 300px;
}

.realtime-stats {
  text-align: center;
  margin-top: 20px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 8px;
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
  position: relative;
  width: 100%;
  height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  border-radius: 8px;
  overflow: hidden;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  transition: transform 0.1s ease;
  user-select: none;
}

.preview-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 8px;
}

.preview-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.7);
  padding: 10px;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  backdrop-filter: blur(10px);
}

.preview-controls .el-button {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
}

.preview-controls .el-button:hover {
  background: rgba(255, 255, 255, 0.3);
}

.zoom-info {
  color: white;
  font-size: 12px;
  text-align: center;
  margin-top: 5px;
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

:deep(.el-radio-button__inner) {
  padding: 12px 20px;
}

/* 类别计数样式 */
.class-counts {
  margin-top: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.class-counts h4 {
  margin-bottom: 15px;
  color: #495057;
  font-weight: 600;
}

.count-number {
  font-weight: 600;
  font-size: 16px;
  color: #409eff;
}

.count-number.cumulative {
  color: #67c23a;
}

.percentage-text {
  font-size: 12px;
  color: #666;
  margin-left: 8px;
}

.counts-pagination {
  margin-top: 15px;
  display: flex;
  justify-content: center;
}

.empty-counts {
  text-align: center;
  padding: 20px;
  color: #999;
}

.class-counts .el-table {
  border-radius: 6px;
  overflow: hidden;
}

.class-counts :deep(.el-table__header-wrapper) {
  background: #f5f7fa;
}

.alert-info {
  margin-top: 8px;
  padding: 8px 12px;
  background: #fef0f0;
  border: 1px solid #fcdcdc;
  border-radius: 4px;
  font-size: 12px;
}

.alert-info .el-icon {
  margin-right: 4px;
}

.class-counts :deep(.el-table__row:hover) {
  background: #f0f9ff;
}

.class-counts :deep(.el-tag) {
  font-weight: 500;
}

.class-counts :deep(.el-progress__text) {
  display: none;
}

.class-counts :deep(.el-progress-bar) {
  margin-bottom: 2px;
}

/* 水印相关样式 */
:deep(.watermark-confirm-dialog) {
  border-radius: 12px;
}

:deep(.watermark-confirm-dialog .el-message-box__title) {
  color: #e6a23c;
  font-weight: 600;
}

:deep(.watermark-confirm-dialog .el-message-box__content) {
  padding: 20px 24px;
}

:deep(.watermark-confirm-dialog .el-button--primary) {
  background: linear-gradient(45deg, #e6a23c, #f39c12);
  border: none;
  border-radius: 6px;
  transition: all 0.3s ease;
}

:deep(.watermark-confirm-dialog .el-button--primary:hover) {
  background: linear-gradient(45deg, #d68910, #e67e22);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(230, 162, 60, 0.4);
}

/* 水印检测结果的特殊样式 */
.detection-list :deep(.el-table__row) {
  transition: all 0.3s ease;
}

.detection-list :deep(.el-table__row:hover) {
  background-color: #fef9e7;
}

.detection-list .el-tag.el-tag--warning {
  background: linear-gradient(45deg, #fff7e6, #fef2d0);
  border: 1px solid #f0c14b;
  color: #d68910;
  animation: watermarkPulse 2s infinite;
}

@keyframes watermarkPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(240, 193, 75, 0.4);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(240, 193, 75, 0.1);
  }
}

.detection-list .el-button--warning {
  background: linear-gradient(45deg, #e6a23c, #f39c12);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  padding: 4px 8px;
  transition: all 0.3s ease;
}

.detection-list .el-button--warning:hover {
  background: linear-gradient(45deg, #d68910, #e67e22);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(230, 162, 60, 0.4);
}
</style> 