<template>
  <div class="alert-record-container">
    <!-- 统计信息卡片 -->
    <div class="stats-grid">
      <el-card class="stat-card">
        <div class="stat-content">
          <div class="stat-number">{{ stats.total_alerts }}</div>
          <div class="stat-label">总预警数</div>
        </div>
        <el-icon class="stat-icon total"><Warning /></el-icon>
      </el-card>
      
      <el-card class="stat-card unhandled">
        <div class="stat-content">
          <div class="stat-number">{{ stats.unhandled_alerts }}</div>
          <div class="stat-label">未处理</div>
        </div>
        <el-icon class="stat-icon unhandled"><Bell /></el-icon>
      </el-card>
      
      <el-card class="stat-card today">
        <div class="stat-content">
          <div class="stat-number">{{ stats.today_alerts }}</div>
          <div class="stat-label">今日预警</div>
        </div>
        <el-icon class="stat-icon today"><Calendar /></el-icon>
      </el-card>
    </div>

    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button-group>
          <el-button 
            :type="filterStatus === 'all' ? 'primary' : ''"
            @click="setFilter('all')"
          >
            全部
          </el-button>
          <el-button 
            :type="filterStatus === 'unhandled' ? 'primary' : ''"
            @click="setFilter('unhandled')"
          >
            未处理
          </el-button>
          <el-button 
            :type="filterStatus === 'handled' ? 'primary' : ''"
            @click="setFilter('handled')"
          >
            已处理
          </el-button>
        </el-button-group>
      </div>
      
      <div class="toolbar-right">
        <el-button 
          type="success" 
          :disabled="selectedIds.length === 0"
          @click="markAsHandled"
        >
          <el-icon><Check /></el-icon>
          标记已处理
        </el-button>
        <el-button 
          type="danger" 
          :disabled="selectedIds.length === 0"
          @click="deleteSelected"
        >
          <el-icon><Delete /></el-icon>
          删除选中
        </el-button>
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 预警列表 -->
    <el-card class="table-card">
      <el-table 
        :data="alertList" 
        v-loading="loading"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column label="预警图像" width="120">
          <template #default="scope">
            <div class="image-preview" @click="showImagePreview(scope.row)">
              <img :src="scope.row.frame_image" alt="预警图像" />
              <div class="image-overlay">
                <el-icon><ZoomIn /></el-icon>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="目标信息" width="180">
          <template #default="scope">
            <div class="target-info">
              <div class="target-class">
                <el-tag :type="getClassTagType(scope.row.target_class)">
                  {{ scope.row.target_class }}
                </el-tag>
              </div>
              <div class="target-id">ID: {{ scope.row.target_id }}</div>
              <div class="confidence">置信度: {{ (scope.row.confidence * 100).toFixed(1) }}%</div>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column label="预警描述" prop="description" min-width="200" />
        
        <el-table-column label="帧号" width="80">
          <template #default="scope">
            <span v-if="scope.row.frame_number">{{ scope.row.frame_number }}</span>
            <span v-else class="text-muted">实时</span>
          </template>
        </el-table-column>
        
        <el-table-column label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.is_handled ? 'success' : 'warning'">
              {{ scope.row.is_handled ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="预警时间" width="180">
          <template #default="scope">
            {{ formatTime(scope.row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="scope">
            <el-button-group size="small">
              <el-button 
                v-if="!scope.row.is_handled"
                type="success" 
                size="small"
                @click="markSingleAsHandled(scope.row.id)"
              >
                处理
              </el-button>
              <el-button 
                type="danger" 
                size="small"
                @click="deleteSingle(scope.row.id)"
              >
                删除
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 图像预览对话框 -->
    <el-dialog 
      v-model="imagePreviewVisible" 
      title="预警图像详情"
      width="60%"
      center
    >
      <div v-if="selectedAlert" class="image-detail">
        <div class="image-container">
          <img :src="selectedAlert.frame_image" alt="预警图像" class="detail-image" />
        </div>
        <div class="alert-details">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="目标类别">
              <el-tag :type="getClassTagType(selectedAlert.target_class)">
                {{ selectedAlert.target_class }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="目标ID">{{ selectedAlert.target_id }}</el-descriptions-item>
            <el-descriptions-item label="置信度">{{ (selectedAlert.confidence * 100).toFixed(1) }}%</el-descriptions-item>
            <el-descriptions-item label="帧号">
              <span v-if="selectedAlert.frame_number">{{ selectedAlert.frame_number }}</span>
              <span v-else>实时检测</span>
            </el-descriptions-item>
            <el-descriptions-item label="预警时间">{{ formatTime(selectedAlert.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="处理状态">
              <el-tag :type="selectedAlert.is_handled ? 'success' : 'warning'">
                {{ selectedAlert.is_handled ? '已处理' : '未处理' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="预警描述" :span="2">{{ selectedAlert.description }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  Warning, 
  Bell, 
  Calendar, 
  Check, 
  Delete, 
  Refresh, 
  ZoomIn 
} from '@element-plus/icons-vue'
import axios from 'axios'

export default {
  name: 'AlertRecord',
  components: {
    Warning,
    Bell,
    Calendar,
    Check,
    Delete,
    Refresh,
    ZoomIn
  },
  setup() {
    const loading = ref(false)
    const alertList = ref([])
    const selectedIds = ref([])
    const currentPage = ref(1)
    const pageSize = ref(20)
    const total = ref(0)
    const filterStatus = ref('all')
    
    const stats = reactive({
      total_alerts: 0,
      unhandled_alerts: 0,
      today_alerts: 0,
      class_counts: {}
    })
    
    const imagePreviewVisible = ref(false)
    const selectedAlert = ref(null)

    const userId = computed(() => {
      const user = JSON.parse(localStorage.getItem('user') || '{}')
      return user.id || 1
    })

    // 获取预警统计信息
    const fetchStats = async () => {
      try {
        const response = await axios.get(`/api/alerts/stats/${userId.value}`)
        if (response.data.success) {
          Object.assign(stats, response.data.stats)
        }
      } catch (error) {
        console.error('获取统计信息失败:', error)
      }
    }

    // 获取预警列表
    const fetchAlerts = async () => {
      loading.value = true
      try {
        const params = {
          page: currentPage.value,
          per_page: pageSize.value
        }
        
        if (filterStatus.value !== 'all') {
          params.is_handled = filterStatus.value === 'handled'
        }
        
        const response = await axios.get(`/api/alerts/${userId.value}`, { params })
        
        if (response.data.success) {
          alertList.value = response.data.alerts
          total.value = response.data.pagination.total
        }
      } catch (error) {
        ElMessage.error('获取预警记录失败')
        console.error('获取预警记录失败:', error)
      } finally {
        loading.value = false
      }
    }

    // 设置过滤器
    const setFilter = (status) => {
      filterStatus.value = status
      currentPage.value = 1
      fetchAlerts()
    }

    // 处理选择变化
    const handleSelectionChange = (selection) => {
      selectedIds.value = selection.map(item => item.id)
    }

    // 标记已处理
    const markAsHandled = async () => {
      if (selectedIds.value.length === 0) return
      
      try {
        const response = await axios.post('/api/alerts/mark_handled', {
          alert_ids: selectedIds.value,
          user_id: userId.value
        })
        
        if (response.data.success) {
          ElMessage.success(response.data.message)
          fetchAlerts()
          fetchStats()
          selectedIds.value = []
        }
      } catch (error) {
        ElMessage.error('标记失败')
        console.error('标记失败:', error)
      }
    }

    // 删除选中
    const deleteSelected = async () => {
      if (selectedIds.value.length === 0) return
      
      try {
        await ElMessageBox.confirm(
          `确定要删除选中的 ${selectedIds.value.length} 条预警记录吗？`,
          '删除确认',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
        
        const response = await axios.delete('/api/alerts/delete', {
          data: {
            alert_ids: selectedIds.value,
            user_id: userId.value
          }
        })
        
        if (response.data.success) {
          ElMessage.success(response.data.message)
          fetchAlerts()
          fetchStats()
          selectedIds.value = []
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
          console.error('删除失败:', error)
        }
      }
    }

    // 标记单个已处理
    const markSingleAsHandled = async (alertId) => {
      try {
        const response = await axios.post('/api/alerts/mark_handled', {
          alert_ids: [alertId],
          user_id: userId.value
        })
        
        if (response.data.success) {
          ElMessage.success('已标记为已处理')
          fetchAlerts()
          fetchStats()
        }
      } catch (error) {
        ElMessage.error('标记失败')
        console.error('标记失败:', error)
      }
    }

    // 删除单个
    const deleteSingle = async (alertId) => {
      try {
        await ElMessageBox.confirm('确定要删除这条预警记录吗？', '删除确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        
        const response = await axios.delete('/api/alerts/delete', {
          data: {
            alert_ids: [alertId],
            user_id: userId.value
          }
        })
        
        if (response.data.success) {
          ElMessage.success('删除成功')
          fetchAlerts()
          fetchStats()
        }
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
          console.error('删除失败:', error)
        }
      }
    }

    // 显示图像预览
    const showImagePreview = (alert) => {
      selectedAlert.value = alert
      imagePreviewVisible.value = true
    }

    // 刷新数据
    const refreshData = () => {
      fetchAlerts()
      fetchStats()
    }

    // 分页处理
    const handleSizeChange = (newSize) => {
      pageSize.value = newSize
      currentPage.value = 1
      fetchAlerts()
    }

    const handleCurrentChange = (newPage) => {
      currentPage.value = newPage
      fetchAlerts()
    }

    // 格式化时间
    const formatTime = (timeStr) => {
      const date = new Date(timeStr)
      return date.toLocaleString('zh-CN')
    }

    // 获取类别标签类型
    const getClassTagType = (className) => {
      const types = {
        'person': 'primary',
        'car': 'success',
        'truck': 'warning',
        'bus': 'danger',
        'bicycle': 'info'
      }
      return types[className] || ''
    }

    onMounted(() => {
      fetchAlerts()
      fetchStats()
    })

    return {
      loading,
      alertList,
      selectedIds,
      currentPage,
      pageSize,
      total,
      filterStatus,
      stats,
      imagePreviewVisible,
      selectedAlert,
      setFilter,
      handleSelectionChange,
      markAsHandled,
      deleteSelected,
      markSingleAsHandled,
      deleteSingle,
      showImagePreview,
      refreshData,
      handleSizeChange,
      handleCurrentChange,
      formatTime,
      getClassTagType
    }
  }
}
</script>

<style scoped>
.alert-record-container {
  padding: 20px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  overflow: hidden;
}

.stat-card.unhandled {
  border-left: 4px solid #f56c6c;
}

.stat-card.today {
  border-left: 4px solid #67c23a;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.stat-icon {
  position: absolute;
  right: 20px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 32px;
  opacity: 0.3;
}

.stat-icon.total {
  color: #409eff;
}

.stat-icon.unhandled {
  color: #f56c6c;
}

.stat-icon.today {
  color: #67c23a;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.table-card {
  margin-bottom: 20px;
}

.image-preview {
  position: relative;
  cursor: pointer;
  width: 80px;
  height: 60px;
  border-radius: 4px;
  overflow: hidden;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.3s;
  color: white;
}

.image-preview:hover .image-overlay {
  opacity: 1;
}

.target-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.target-class {
  margin-bottom: 4px;
}

.target-id, .confidence {
  font-size: 12px;
  color: #666;
}

.text-muted {
  color: #909399;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.image-detail {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.image-container {
  text-align: center;
}

.detail-image {
  max-width: 100%;
  max-height: 400px;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.alert-details {
  padding: 0 20px;
}
</style> 