# 更新日志

## 2026-01-14 - 新目录结构和配置分离

### 重要变更 ⚠️

#### 目录结构调整
- **新的基础目录**: `/home/firefly/sparkrobot/`（取代原来的`~/robot-chat/`）
- **代码目录**: `/home/firefly/sparkrobot/robot-chat/`
- **配置目录**: `/home/firefly/sparkrobot/config/`

#### 配置文件分离
- **全局配置** (`config/config.toml`): 存储UUID等所有应用共享的配置
- **专用配置** (`config/robot-chat.toml`): 存储机器人对话相关的专属配置

### 优势
1. **模块化设计**: 配置与代码分离，便于管理
2. **可扩展性**: 为未来更多Spark Robot应用预留空间
3. **配置共享**: UUID等全局配置在所有应用间共享
4. **清晰的目录结构**: 更符合专业软件的组织方式

### 迁移指南

如果你已有旧版本安装在`~/robot-chat`：

```bash
# 1. 创建新目录
mkdir -p ~/sparkrobot/robot-chat
mkdir -p ~/sparkrobot/config

# 2. 迁移配置
# 如果存在旧配置
if [ -f ~/robot-chat/config.toml ]; then
    # 提取UUID
    UUID=$(grep "uuid" ~/robot-chat/config.toml | cut -d'"' -f2)
    echo "uuid = \"$UUID\"" > ~/sparkrobot/config/config.toml
    
    # 复制其他配置到新位置
    cp ~/robot-chat/config.toml ~/sparkrobot/config/robot-chat.toml
fi

# 3. 迁移代码（或重新部署）
cp -r ~/robot-chat/* ~/sparkrobot/robot-chat/

# 4. 可选：清理旧目录
# rm -rf ~/robot-chat
```

---

## 2026-01-14 - 客户端自动部署和固件更新功能

### 新功能

#### 1. 改进的SSH助手脚本 (`backend/src/utils/ssh_helper.py`)
- ✅ 添加详细的日志输出，方便调试
- ✅ 改进错误处理，显示更明确的错误信息  
- ✅ 添加路径验证，避免无效路径导致的问题
- ✅ 跳过docs目录，减少不必要的文件传输
- ✅ 使用绝对路径避免路径解析问题

#### 2. 创建机器人时自动部署客户端
- ✅ 在添加机器人时自动测试SSH连接
- ✅ 自动创建远程目录结构
- ✅ 自动检测或生成UUID
- ✅ 自动复制客户端代码到机器人
- ✅ 更详细的错误提示和日志

#### 3. 固件更新功能
- ✅ 新增API端点: `POST /api/robots/:uuid/update-firmware`
- ✅ 前端管理页面新增"更新固件"按钮
- ✅ 支持一键更新机器人的客户端代码
- ✅ 带确认对话框，防止误操作
- ✅ 实时显示更新状态

### 技术细节

#### API路由改进 (`backend/src/routes/api.ts`)
- 使用新的目录结构
- 所有远程路径统一使用绝对路径
- 添加详细的控制台日志输出
- 改进错误信息传递
- 配置文件采用TOML格式

#### 客户端改进 (`client/src/robot_client.py`)
- 支持新的目录结构
- 配置分离：全局配置与专用配置
- 自动创建多级目录
- 兼容旧版本配置（可手动迁移）

#### 前端界面 (`frontend/src/views/RobotManage.vue`)
- 卡片视图和列表视图都添加了"更新固件"按钮
- 添加`updating`状态管理，防止重复点击
- 导入Upload图标
- 按钮带加载动态和提示文本

### 使用说明

#### 方式1: 创建机器人时自动部署
1. 在前端界面点击"添加机器人"
2. 填写机器人名称和IP地址
3. 点击"添加"
4. 系统会自动完成所有部署

#### 方式2: 手动更新固件
1. 在机器人管理页面找到目标机器人
2. 点击"更新固件"按钮
3. 确认更新
4. 等待完成

### 注意事项

1. **SSH配置**: 默认使用firefly/firefly作为用户名密码
2. **网络要求**: 确保开发机器可以SSH连接到机器狗
3. **目录结构**: 所有文件安装在`/home/firefly/sparkrobot/`
4. **配置分离**: UUID存储在`config/config.toml`，其他配置在`config/robot-chat.toml`

### 故障排查

如果更新失败，请检查：
1. 机器狗IP是否正确且可访问
2. SSH端口22是否开放
3. firefly用户权限是否正常
4. 网络连接是否稳定
5. 查看后端控制台日志获取详细错误信息
