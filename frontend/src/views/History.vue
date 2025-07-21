<template>
  <div class="history-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>检测历史记录</span>
          <div class="header-actions">
            <el-button 
              type="danger" 
              @click="clearAllHistory" 
              :disabled="history.length === 0"
              v-if="history.length > 0"
            >
              <el-icon><Delete /></el-icon>
              清空所有
            </el-button>
            <el-button 
              type="warning" 
              @click="batchDelete" 
              :disabled="selectedRows.length === 0"
              v-if="selectedRows.length > 0"
            >
              <el-icon><Delete /></el-icon>
              批量删除 ({{ selectedRows.length }})
            </el-button>
            <el-button type="primary" @click="refreshHistory" :loading="$store.state.isLoading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>
      
      <div class="history-content">
        <!-- 统计信息 -->
        <div class="stats-row" v-if="history.length > 0">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-statistic title="总检测次数" :value="history.length" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="图片检测" :value="getCountByType('image')" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="视频检测" :value="getCountByType('video')" />
            </el-col>
            <el-col :span="6">
              <el-statistic title="摄像头检测" :value="getCountByType('camera')" />
            </el-col>
          </el-row>
        </div>
        
        <!-- 历史记录表格 -->
        <el-table 
          :data="paginatedHistory" 
          style="width: 100%" 
          v-loading="$store.state.isLoading"
          empty-text="暂无检测历史"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="55" />
          
          <el-table-column label="检测时间" width="180">
            <template #default="scope">
              <div class="time-info">
                <el-icon><Clock /></el-icon>
                {{ formatTime(scope.row.created_at) }}
              </div>
            </template>
          </el-table-column>
          
          <el-table-column label="检测类型" width="120">
            <template #default="scope">
              <el-tag :type="getTypeTagType(scope.row.detection_type)">
                {{ getTypeLabel(scope.row.detection_type) }}
              </el-tag>
            </template>
          </el-table-column>
          
          <el-table-column label="原始文件" width="200">
            <template #default="scope">
              <div class="file-info" v-if="scope.row.original_file">
                <el-icon><Document /></el-icon>
                <span class="file-name">{{ scope.row.original_file }}</span>
              </div>
              <span v-else class="no-file">实时检测</span>
            </template>
          </el-table-column>
          
          <el-table-column label="检测结果" width="150">
            <template #default="scope">
              <div class="result-info">
                <el-tag type="success" v-if="scope.row.detections && scope.row.detections.length > 0">
                  检测到 {{ scope.row.detections.length }} 个目标
                </el-tag>
                <el-tag type="info" v-else>
                  未检测到目标
                </el-tag>
              </div>
            </template>
          </el-table-column>
          
          <el-table-column label="最高置信度" width="150">
            <template #default="scope">
              <el-progress 
                v-if="scope.row.confidence"
                :percentage="Math.round(scope.row.confidence * 100)"
                :stroke-width="8"
                :color="getConfidenceColor(scope.row.confidence)"
              />
              <span v-else>--</span>
            </template>
          </el-table-column>
          
          <el-table-column label="操作" width="250">
            <template #default="scope">
              <el-button-group>
                <el-button 
                  size="small" 
                  @click="viewDetails(scope.row)"
                  :disabled="!scope.row.detections || scope.row.detections.length === 0"
                >
                  <el-icon><View /></el-icon>
                  查看详情
                </el-button>
                <el-button 
                  size="small" 
                  type="primary"
                  @click="downloadResult(scope.row)"
                  :disabled="!scope.row.result_file"
                >
                  <el-icon><Download /></el-icon>
                  下载结果
                </el-button>
                <el-button 
                  size="small" 
                  type="danger"
                  @click="deleteRecord(scope.row)"
                >
                  <el-icon><Delete /></el-icon>
                  删除
                </el-button>
              </el-button-group>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 分页 -->
        <div class="pagination-container" v-if="history.length > pageSize">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="history.length"
            layout="total, prev, pager, next, jumper"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </el-card>
    
    <!-- 详情对话框 -->
    <el-dialog 
      v-model="showDetails" 
      title="检测详情" 
      width="80%"
      destroy-on-close
    >
      <div v-if="selectedRecord" class="detail-content">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="detail-info">
              <h4>基本信息</h4>
              <el-descriptions :column="1" border>
                <el-descriptions-item label="检测时间">
                  {{ formatTime(selectedRecord.created_at) }}
                </el-descriptions-item>
                <el-descriptions-item label="检测类型">
                  <el-tag :type="getTypeTagType(selectedRecord.detection_type)">
                    {{ getTypeLabel(selectedRecord.detection_type) }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="原始文件" v-if="selectedRecord.original_file">
                  {{ selectedRecord.original_file }}
                </el-descriptions-item>
                <el-descriptions-item label="检测目标数量">
                  {{ selectedRecord.detections ? selectedRecord.detections.length : 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="最高置信度" v-if="selectedRecord.confidence">
                  {{ (selectedRecord.confidence * 100).toFixed(2) }}%
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </el-col>
          
          <el-col :span="12">
            <div class="result-preview" v-if="selectedRecord.result_file">
              <h4>结果预览</h4>
              <div class="preview-container">
                <img 
                  v-if="isImageFile(selectedRecord.result_file)"
                  :src="getResultFileUrl(selectedRecord.result_file)" 
                  class="preview-image"
                  alt="检测结果"
                />
                <video 
                  v-else-if="isVideoFile(selectedRecord.result_file)"
                  :src="getResultFileUrl(selectedRecord.result_file)"
                  class="preview-video"
                  controls
                >
                  您的浏览器不支持视频播放
                </video>
              </div>
            </div>
          </el-col>
        </el-row>
        
        <!-- 检测详情列表 -->
        <div class="detection-details" v-if="selectedRecord.detections && selectedRecord.detections.length > 0">
          <h4>检测详情</h4>
          <el-table :data="selectedRecord.detections" style="width: 100%" size="small">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="class" label="类别" width="150" />
            <el-table-column label="置信度" width="150">
              <template #default="scope">
                <el-progress 
                  :percentage="Math.round(scope.row.confidence * 100)" 
                  :stroke-width="8"
                  :color="getConfidenceColor(scope.row.confidence)"
                />
              </template>
            </el-table-column>
            <el-table-column label="边界框坐标">
              <template #default="scope">
                <span class="bbox-info">
                  {{ formatBbox(scope.row.bbox) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="帧数" v-if="selectedRecord.detection_type === 'video'">
              <template #default="scope">
                {{ scope.row.frame || '--' }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Refresh, 
  Clock, 
  Document, 
  View, 
  Download,
  Delete
} from '@element-plus/icons-vue'

export default {
  name: 'History',
  components: {
    Refresh,
    Clock,
    Document,
    View,
    Download,
    Delete
  },
  data() {
    return {
      currentPage: 1,
      pageSize: 10,
      showDetails: false,
      selectedRecord: null,
      selectedRows: []
    }
  },
  computed: {
    history() {
      return this.$store.state.history || []
    },
    paginatedHistory() {
      const start = (this.currentPage - 1) * this.pageSize
      const end = start + this.pageSize
      return this.history.slice(start, end)
    }
  },
  async mounted() {
    await this.refreshHistory()
  },
  methods: {
    async refreshHistory() {
      try {
        const result = await this.$store.dispatch('fetchHistory')
        if (!result.success) {
          ElMessage.error(result.message)
        }
      } catch (error) {
        ElMessage.error('获取历史记录失败')
      }
    },
    
    getCountByType(type) {
      return this.history.filter(item => item.detection_type === type).length
    },
    
    getTypeLabel(type) {
      const labels = {
        image: '图片检测',
        video: '视频检测', 
        camera: '摄像头检测'
      }
      return labels[type] || type
    },
    
    getTypeTagType(type) {
      const types = {
        image: 'primary',
        video: 'success',
        camera: 'warning'
      }
      return types[type] || 'info'
    },
    
    formatTime(timeString) {
      const date = new Date(timeString)
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    },
    
    getConfidenceColor(confidence) {
      if (confidence >= 0.8) return '#67c23a'
      if (confidence >= 0.6) return '#e6a23c'
      return '#f56c6c'
    },
    
    formatBbox(bbox) {
      if (!bbox || bbox.length !== 4) return '--'
      return `(${Math.round(bbox[0])}, ${Math.round(bbox[1])}) - (${Math.round(bbox[2])}, ${Math.round(bbox[3])})`
    },
    
    viewDetails(record) {
      this.selectedRecord = record
      this.showDetails = true
    },
    
    downloadResult(record) {
      if (record.result_file) {
        const url = this.getResultFileUrl(record.result_file)
        const link = document.createElement('a')
        link.href = url
        link.download = record.result_file
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        ElMessage.success('开始下载结果文件')
      } else {
        ElMessage.warning('没有可下载的结果文件')
      }
    },
    
    getResultFileUrl(filename) {
      return `http://localhost:5000/static/${filename}`
    },
    
    isImageFile(filename) {
      const imageExts = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
      return imageExts.some(ext => filename.toLowerCase().endsWith(ext))
    },
    
    isVideoFile(filename) {
      const videoExts = ['.mp4', '.avi', '.mov', '.mkv']
      return videoExts.some(ext => filename.toLowerCase().endsWith(ext))
    },
    
    handlePageChange(page) {
      this.currentPage = page
    },
    
    handleSelectionChange(selection) {
      this.selectedRows = selection.map(item => item.id)
    },
    
    async deleteRecord(record) {
      try {
        await ElMessageBox.confirm(
          `确定要删除这条检测记录吗？\n检测时间: ${this.formatTime(record.created_at)}\n此操作不可恢复`,
          '删除确认',
          {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning',
            dangerouslyUseHTMLString: true
          }
        )
        
        const response = await fetch(`http://localhost:5000/api/history/delete/${record.id}`, {
          method: 'DELETE'
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          await this.refreshHistory()
        } else {
          ElMessage.error(data.message)
        }
        
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除记录失败: ' + error.message)
        }
      }
    },
    
    async batchDelete() {
      if (this.selectedRows.length === 0) {
        ElMessage.warning('请先选择要删除的记录')
        return
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要删除选中的 ${this.selectedRows.length} 条检测记录吗？\n此操作不可恢复`,
          '批量删除确认',
          {
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        const currentUser = this.$store.getters.currentUser
        const response = await fetch('http://localhost:5000/api/history/batch-delete', {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            record_ids: this.selectedRows,
            user_id: currentUser?.id || 1
          })
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          this.selectedRows = []
          await this.refreshHistory()
        } else {
          ElMessage.error(data.message)
        }
        
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('批量删除失败: ' + error.message)
        }
      }
    },
    
    async clearAllHistory() {
      if (this.history.length === 0) {
        ElMessage.info('没有需要清空的记录')
        return
      }
      
      try {
        await ElMessageBox.confirm(
          `确定要清空所有检测历史记录吗？\n这将删除 ${this.history.length} 条记录和相关文件\n此操作不可恢复`,
          '清空历史确认',
          {
            confirmButtonText: '确定清空',
            cancelButtonText: '取消',
            type: 'error'
          }
        )
        
        const currentUser = this.$store.getters.currentUser
        const response = await fetch(`http://localhost:5000/api/history/clear/${currentUser?.id || 1}`, {
          method: 'DELETE'
        })
        
        const data = await response.json()
        
        if (data.success) {
          ElMessage.success(data.message)
          this.selectedRows = []
          await this.refreshHistory()
        } else {
          ElMessage.error(data.message)
        }
        
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('清空历史记录失败: ' + error.message)
        }
      }
    }
  }
}
</script>

<style scoped>
.history-container {
  max-width: 1400px;
  margin: 0 auto;
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
  align-items: center;
}

.stats-row {
  margin-bottom: 30px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
}

.time-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.no-file {
  color: #999;
  font-style: italic;
}

.result-info {
  display: flex;
  align-items: center;
}

.pagination-container {
  margin-top: 20px;
  text-align: center;
}

.detail-content {
  max-height: 70vh;
  overflow-y: auto;
}

.detail-info {
  margin-bottom: 20px;
}

.detail-info h4 {
  margin-bottom: 15px;
  color: #333;
  font-weight: 600;
}

.result-preview h4 {
  margin-bottom: 15px;
  color: #333;
  font-weight: 600;
}

.preview-container {
  text-align: center;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #f9f9f9;
}

.preview-image, .preview-video {
  max-width: 100%;
  max-height: 300px;
  border-radius: 8px;
}

.detection-details {
  margin-top: 30px;
}

.detection-details h4 {
  margin-bottom: 15px;
  color: #333;
  font-weight: 600;
}

.bbox-info {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

:deep(.el-statistic__number) {
  color: #409eff;
  font-weight: 600;
}

:deep(.el-statistic__title) {
  color: #666;
  font-size: 14px;
}

:deep(.el-descriptions-item__label) {
  font-weight: 600;
  background: #fafafa;
}

:deep(.el-table .cell) {
  padding: 0 8px;
}

.header-actions .el-button {
  transition: all 0.3s ease;
}

.header-actions .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.header-actions .el-button--danger {
  background: linear-gradient(45deg, #ff6b6b, #ee5a52);
}

.header-actions .el-button--warning {
  background: linear-gradient(45deg, #feca57, #ff9ff3);
}
</style> 