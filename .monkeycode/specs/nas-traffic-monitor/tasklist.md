# 需求实施计划

- [ ] 1. 项目初始化与基础结构
  - [ ] 1.1 创建项目目录结构（app/、app/collector/、app/processor/、app/api/、app/static/、tests/）
  - [ ] 1.2 创建 pyproject.toml，声明依赖（fastapi、uvicorn、apscheduler、docker、python-jose、bcrypt、aiosqlite）
  - [ ] 1.3 创建 Dockerfile 和 docker-compose.yml，配置 host 网络模式和 Docker Socket 挂载
  - [ ] 1.4 创建 .env.example，列出所有环境变量（ADMIN_USERNAME、ADMIN_PASSWORD、JWT_SECRET、FEISHU_WEBHOOK_URL 等）
  - [ ] 1.5 创建 app/config.py，从环境变量读取配置项

- [ ] 2. 数据模型与数据库层
  - [ ] 2.1 创建 app/database.py，实现 SQLite 连接管理、表初始化（users、services、traffic_records、connection_records、daily_summaries、alert_records、alert_config、settings）
  - [ ] 2.2 创建 app/models.py，定义所有数据模型（ServiceInfo、TrafficRecord、ConnectionRecord、DailySummary、AlertRecord、AlertConfig、User）
  - [ ] 2.3 实现首次启动时的默认数据初始化：默认管理员账号、默认告警规则（high_upload/high_download/high_connections）

- [ ] 3. 认证模块（REQ-7）
  - [ ] 3.1 创建 app/auth.py，实现 JWT Token 生成与验证、密码 bcrypt 哈希与校验
  - [ ] 3.2 实现 FastAPI 认证中间件（Depends 机制），所有 /api/* 接口（除 /api/auth/login 外）需验证 Token
  - [ ] 3.3 实现登录接口 POST /api/auth/login
  - [ ] 3.4 实现修改密码接口 PUT /api/auth/password
  - [ ] 3.5 实现获取用户信息接口 GET /api/auth/info

- [ ] 4. 数据采集层 - 服务发现（REQ-1）
  - [ ] 4.1 创建 app/collector/discovery.py，实现 Docker 容器服务发现（通过 Docker SDK 获取容器列表、名称、镜像、端口、状态、PID）
  - [ ] 4.2 实现飞牛商店服务发现预留接口（抽象基类，当前返回空列表）
  - [ ] 4.3 实现服务信息持久化：新服务插入、已有服务状态更新、离线服务标记

- [ ] 5. 数据采集层 - 流量采集（REQ-2）
  - [ ] 5.1 创建 app/collector/traffic.py，实现 iptables 规则管理：为每个 Docker 容器创建流量计数规则（区分局域网/互联网、上行/下行）
  - [ ] 5.2 实现流量计数器读取：解析 iptables -L -v -n 输出，提取字节数
  - [ ] 5.3 实现流量差值计算：与上次采集值做差值，负值丢弃并记录日志（对应 Correctness Properties #1）
  - [ ] 5.4 实现流量记录写入 traffic_records 表

- [ ] 6. 数据采集层 - 连接数采集（REQ-5）
  - [ ] 6.1 创建 app/collector/connections.py，实现 ss -tunap 命令输出解析
  - [ ] 6.2 实现连接按进程 PID 关联到服务
  - [ ] 6.3 实现按 remote IP 区分局域网/互联网连接
  - [ ] 6.4 实现连接数记录写入 connection_records 表

- [ ] 7. 数据处理层 - 聚合与告警（REQ-3、REQ-4）
  - [ ] 7.1 创建 app/processor/aggregator.py，实现每日流量汇总：按天聚合各服务的流量和连接数峰值/均值，写入 daily_summaries
  - [ ] 7.2 创建 app/processor/alert_engine.py，实现告警规则评估：检查 1 小时内累计流量和当前连接数是否超阈值
  - [ ] 7.3 实现告警去重逻辑：同一服务同一规则 30 分钟内只触发一次（对应 Correctness Properties #3）
  - [ ] 7.4 创建 app/notifier.py，实现飞书 Webhook 告警消息发送（消息卡片格式）

- [ ] 8. 定时调度器（Scheduler）
  - [ ] 8.1 创建 app/scheduler.py，使用 APScheduler BackgroundScheduler 配置所有定时任务（服务发现5分钟、流量采集5分钟、连接采集5分钟、每日汇总00:05、告警检查5分钟、数据清理01:00）
  - [ ] 8.2 实现数据清理任务：删除 90 天前的 traffic_records 和 connection_records，删除 180 天前的 alert_records

- [ ] 9. 检查点 - 确保后端核心逻辑可运行
  - 启动应用验证调度器正常运行、数据库初始化成功、采集流程无报错

- [ ] 10. Web API 层（REQ-6、REQ-7）
  - [ ] 10.1 创建 app/api/services.py，实现服务列表 GET /api/services、服务流量 GET /api/services/{id}/traffic、服务连接数 GET /api/services/{id}/connections
  - [ ] 10.2 创建 app/api/summary.py，实现每日汇总列表 GET /api/daily-summary、指定日期详情 GET /api/daily-summary/{date}
  - [ ] 10.3 创建 app/api/alerts.py，实现告警记录 GET /api/alerts、告警配置 GET/PUT /api/alerts/config
  - [ ] 10.4 创建 app/api/settings.py，实现 Webhook 配置 GET/PUT /api/settings/webhook、测试 POST /api/settings/webhook/test
  - [ ] 10.5 创建 app/api/dashboard.py，实现仪表盘聚合数据 GET /api/dashboard

- [ ] 11. Web 前端界面（REQ-6、REQ-7）
  - [ ] 11.1 创建登录页面（/login），实现用户名密码登录、Token 存储到 localStorage
  - [ ] 11.2 创建前端公共模块：API 请求封装（自动附加 Bearer Token、401 跳转登录）、路由守卫
  - [ ] 11.3 创建仪表盘页面（/），展示全局流量概览、活跃服务数、最近告警
  - [ ] 11.4 创建服务列表页面（/services），展示所有服务及运行状态
  - [ ] 11.5 创建服务详情页面（/services/{id}），展示单个服务流量和连接数趋势图表（Chart.js）
  - [ ] 11.6 创建每日汇总页面（/summary），展示每日流量报表和趋势图
  - [ ] 11.7 创建告警记录页面（/alerts），展示历史告警列表
  - [ ] 11.8 创建系统设置页面（/settings），包含告警阈值配置、飞书 Webhook 配置和测试、修改密码

- [ ] 12. 应用入口与静态资源服务
  - [ ] 12.1 创建 app/main.py，初始化 FastAPI 应用、挂载 API 路由、注册调度器、serve 静态前端文件
  - [ ] 12.2 确保静态资源（/login、/css、/js）不需要 Token 认证

- [ ] 13. 检查点 - 完整功能验证
  - 构建并运行容器，验证登录、数据采集、仪表盘展示、告警触发全流程
