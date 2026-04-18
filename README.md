# NAS Traffic Monitor

NAS 流量监控与告警系统，部署在飞牛 NAS 上，自动监控所有服务的网络流量和连接状态。

## 功能

- **服务自动发现**：自动识别 Docker 容器、飞牛商店应用（Docker + 原生 systemd 服务）
- **按服务流量统计**：上下行流量，区分局域网/互联网，5 分钟采集粒度
- **每日流量汇总**：按天聚合报表，7/30 天趋势图
- **异常告警**：流量或连接数超阈值时通过飞书 Webhook 推送通知，30 分钟去重
- **连接数监控**：每个服务的 TCP/UDP 连接数，区分局域网/互联网
- **Web 管理界面**：仪表盘、服务详情、趋势图表、告警配置，JWT 认证保护

## 部署

### 方式一：Python 虚拟环境（推荐）

```bash
cd /vol1/docker/nas-traffic-monitor

python3 -m venv venv
source venv/bin/activate
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi uvicorn apscheduler docker python-jose bcrypt aiosqlite httpx

cp .env.example .env
# 编辑 .env 修改 ADMIN_PASSWORD 和 JWT_SECRET
vi .env
```

启动服务：

```bash
sudo DB_PATH=./data/monitor.db JWT_SECRET=your-secret ADMIN_PASSWORD=your-password ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8888
```

后台运行：

```bash
nohup sudo DB_PATH=./data/monitor.db JWT_SECRET=your-secret ADMIN_PASSWORD=your-password ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8888 > monitor.log 2>&1 &
```

### 方式二：Docker Compose

```bash
# 配置 Docker Hub 镜像加速（如需要）
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'EOF'
{
  "registry-mirrors": ["https://docker.1ms.run"]
}
EOF
sudo systemctl restart docker

# 启动
sudo docker compose up -d --build
```

## 配置

编辑 `.env` 文件：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| ADMIN_USERNAME | 管理员用户名 | admin |
| ADMIN_PASSWORD | 管理员密码 | changeme |
| JWT_SECRET | JWT 签名密钥 | 请务必修改 |
| FEISHU_WEBHOOK_URL | 飞书机器人 Webhook | 空 |
| DB_PATH | SQLite 数据库路径 | /app/data/monitor.db |

生成随机密钥：`openssl rand -hex 32`

## 访问

浏览器打开 `http://NAS_IP:8888`，用 `.env` 中配置的账号密码登录。

## 服务来源识别

| 来源 | 识别方式 |
|------|----------|
| Docker 容器 | 通过 Docker API 发现 |
| 飞牛商店应用（Docker） | 镜像来自 `registry.cn-guangzhou.aliyuncs.com/fnapp/` 或 `registry.fnnas.com/fnapp/` |
| 飞牛商店应用（原生） | systemd 服务名以 `trim-`/`fnos_` 开头或以 `_service` 结尾 |
| 系统服务 | 其他 systemd 服务 |

## 默认告警阈值

| 规则 | 指标 | 默认阈值 |
|------|------|----------|
| 互联网上行流量过高 | 1 小时累计上传 | 5 GB |
| 互联网下行流量过高 | 1 小时累计下载 | 10 GB |
| 互联网连接数过高 | 单次采集连接数 | 200 |

可在 Web 界面「系统设置」中自定义。

## 项目结构

```
app/
├── main.py              # FastAPI 入口
├── config.py             # 环境变量配置
├── database.py           # SQLite 管理
├── models.py             # 数据模型
├── auth.py               # JWT 认证
├── scheduler.py          # 定时任务调度
├── notifier.py           # 飞书 Webhook 通知
├── collector/
│   ├── discovery.py      # 服务发现
│   ├── traffic.py        # 流量采集（iptables）
│   └── connections.py    # 连接数采集（ss）
├── processor/
│   ├── aggregator.py     # 每日汇总
│   └── alert_engine.py   # 异常检测与告警
├── api/
│   ├── auth.py           # 登录/改密 API
│   ├── services.py       # 服务 API
│   ├── summary.py        # 汇总 API
│   ├── alerts.py         # 告警 API
│   ├── settings.py       # 设置 API
│   └── dashboard.py      # 仪表盘 API
└── static/               # Web 前端页面
```

## 数据保留

- 原始数据（流量/连接数）：90 天
- 每日汇总：永久
- 告警记录：180 天

## 常用命令

```bash
# 查看日志
tail -f monitor.log

# 查看进程
ps aux | grep uvicorn

# 停止服务
sudo pkill -f "uvicorn app.main:app"

# 重启服务
sudo pkill -f "uvicorn app.main:app"
nohup sudo DB_PATH=./data/monitor.db JWT_SECRET=xxx ADMIN_PASSWORD=xxx ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8888 > monitor.log 2>&1 &
```

## License

MIT
