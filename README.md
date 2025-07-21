# YOLO检测识别系统

基于YOLOv8深度学习模型的目标检测系统，支持图片、视频和摄像头实时检测三种方式。

## 技术栈

### 后端
- **Flask**: Python Web框架
- **YOLOv8**: 目标检测模型
- **SQLite**: 轻量级数据库
- **OpenCV**: 图像处理
- **SQLAlchemy**: ORM框架

### 前端
- **Vue 3**: 前端框架
- **Element Plus**: UI组件库
- **Vuex**: 状态管理
- **Vue Router**: 路由管理
- **Axios**: HTTP客户端

## 功能特性

- ✅ **用户认证**: 登录/注册系统
- ✅ **三种检测方式**:
  - 图片上传检测
  - 视频上传检测
  - 摄像头实时检测
- ✅ **检测结果可视化**: 显示检测框和置信度
- ✅ **历史记录管理**: 查看和管理检测历史
- ✅ **结果下载**: 支持检测结果文件下载
- ✅ **现代化UI**: 美观的用户界面
- ✅ **简化配置**: 使用SQLite，无需复杂的数据库配置

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 14+



#### 2. 后端设置
```bash
# 安装Python依赖
pip install -r requirements.txt

# 启动后端服务（首次运行会自动创建数据库）
python app.py
```

#### 3. 前端设置
```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run serve
```

#### 4. 访问系统
- 前端地址: http://localhost:8080
- 默认账号: admin / admin123

## 使用说明

### 图片检测
1. 选择"图片检测"模式
2. 拖拽或点击上传图片文件
3. 系统自动进行检测并显示结果

### 视频检测
1. 选择"视频检测"模式
2. 上传视频文件（支持MP4、AVI、MOV格式）
3. 等待处理完成，查看检测结果

### 摄像头检测
1. 选择"摄像头检测"模式
2. 点击"启动摄像头"按钮
3. 系统实时显示检测结果

### 历史记录
- 查看所有检测历史
- 下载检测结果文件
- 查看详细检测信息

## 模型配置

系统默认使用YOLOv8n模型，首次运行会自动下载。您可以：

1. **使用自定义模型**: 将训练好的.pt模型文件放在项目根目录，修改`config.py`中的`YOLO_MODEL_PATH`
2. **调整检测阈值**: 修改`config.py`中的`DETECTION_CONFIDENCE`参数
3. **支持的模型格式**: .pt, .onnx, .torchscript

## 数据库

系统使用SQLite数据库，数据存储在项目根目录的`yolo_detection.db`文件中。

### 数据库结构

#### users 表
- id: 用户ID
- username: 用户名
- password: 密码
- created_at: 创建时间

#### detection_result 表
- id: 记录ID
- user_id: 用户ID
- detection_type: 检测类型（image/video/camera）
- original_file: 原始文件名
- result_file: 结果文件名
- detections: 检测结果（JSON）
- confidence: 最高置信度
- created_at: 检测时间

## 项目结构

```
├── app.py                 # Flask主应用
├── config.py             # 配置文件
├── requirements.txt      # Python依赖
├── run.py               # 启动脚本（Linux/Mac）
├── start.bat            # 启动脚本（Windows）
├── init_db.py           # 数据库初始化脚本
├── yolo_detection.db    # SQLite数据库文件（自动创建）
├── uploads/             # 上传文件目录
├── static/              # 静态文件目录
└── frontend/            # Vue前端
    ├── src/
    │   ├── components/  # 组件
    │   ├── views/       # 页面
    │   ├── router/      # 路由
    │   ├── store/       # 状态管理
    │   └── main.js      # 入口文件
    ├── public/          # 公共文件
    └── package.json     # 前端依赖
```

## 开发说明

### 配置说明
所有配置都在`config.py`文件中，包括：
- 数据库路径
- 上传文件大小限制
- YOLO模型路径
- 检测置信度阈值

### 添加新的检测类型
1. 在后端`app.py`中添加新的API路由
2. 在前端添加对应的界面和逻辑
3. 更新数据库模型（如需要）

### 自定义模型
- 将训练好的YOLO模型文件放置在项目目录
- 修改`config.py`中的模型路径
- 确保模型与YOLOv8兼容

### 部署到生产环境
1. 修改`config.py`中的配置为生产环境设置
2. 使用`npm run build`构建前端
3. 配置Web服务器（如Nginx）
4. 使用进程管理工具（如PM2）管理Python应用



