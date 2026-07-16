# 牌运 Haiun

牌运（Haiun，取自日文“牌運”的读音）是立直麻将牌谱与运气分析应用。它支持标准四人麻将与三人麻将，把原始牌谱、规范对局事实和分析结果分层保存在本机，并解释随机机会如何影响每位玩家。

## 功能

- 通过 Amae-Koromo 的匿名公开索引搜索四人/三人玩家和近期对局。
- 通过后端本地账号配置导入雀魂分享链接或牌谱 ID，也支持解码 JSON 和牌运规范 JSON。
- 按雀魂牌谱 ID 缓存原始牌谱与规范牌谱，重复导入不会再次登录或下载。
- 使用 `baseline-v1` 分析配牌、自摸进张和随机事件；对手主动弃牌作为 `opponent_gift` 信息展示，不计入主牌运分数。
- 分别显示 0–100 牌运分数、z-score、置信度和实战点数。
- 支持三麻缺少二至八万、拔北、三人计分与自摸损规则事实。

## NixOS / Nix

进入开发环境：

```bash
nix develop
uv venv .venv
uv pip install -e '.[test]'
npm --prefix frontend install
```

开发模式：

```bash
nix run .#dev
```

生产模式：

```bash
nix run .#start
```

## 常规 Linux

需要 Python 3.11+、Node.js 22+、npm、SQLite 和 Bash。脚本检测到 `uv` 时会优先使用，否则回退到标准库 `venv` 与 `pip`。首次安装：

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'
npm --prefix frontend install
```

随后运行 `scripts/dev.sh` 或 `scripts/start.sh`。脚本从自身路径解析仓库根目录，因此可从任意工作目录启动。

## Docker

### 前置条件

安装 Docker Engine 28 或更高版本，以及 Docker Compose 2.40 或更高版本。仅在需要覆盖卷名、路径或 Python 包索引等非敏感值时复制环境变量示例：

```bash
cp .env.docker.example .env
```

两个 Compose 模式的 `HAIUN_PYPI_INDEX_URL` 默认都是官方的 `https://pypi.org/simple`；仅在受限网络中确有需要时覆盖它。

先按下文“后端配置”填写真实配置，并将 `config/config.toml` 保留在本机、设置为 `0600`。Docker 只读挂载整个 `config/` 目录，不会把真实配置文件复制进镜像。容器启动时会以 root 仅将这个私有文件安全复制到容器专用的 tmpfs，副本设为 UID/GID `10001:10001`、模式 `0400`，随后清空附加组并永久降权到 UID/GID `10001:10001` 运行 Haiun。宿主机文件的所有者和权限不会被修改：

```bash
chmod 600 config/config.toml
```

### 简单模式

简单模式直接发布 Haiun，默认监听宿主机端口 `8765`：

```bash
docker compose -f compose.simple.yml up -d --build
docker compose -f compose.simple.yml ps
curl http://127.0.0.1:8765/api/health
```

停止服务但保留数据：

```bash
docker compose -f compose.simple.yml down
```

### 生产模式

生产模式的 Nginx 绑定宿主机端口 80，并要求现有 TLS 代理或负载均衡器把 HTTP 转发给它。用防火墙将服务器端口 80 严格限制为只有该 TLS 代理或负载均衡器的实际来源地址可以连接。该栈本身不签发证书，也不终止公网 TLS。

创建 Grafana 密码文件且不把密码打印到终端；文件位于已被 Git 忽略的本地 `secrets/` 目录中，并由 `umask 077` 以 `0600` 模式创建：

```bash
install -d -m 0700 secrets
umask 077
openssl rand -base64 32 > secrets/grafana_admin_password.txt
```

如果 TLS 代理不是从回环地址或 RFC 1918 地址连接，请复制默认 Nginx include，并把其中的网络替换为该代理文档给出的实际来源网络：

```bash
cp deploy/nginx/trusted-proxies.default.conf config/trusted-proxies.conf
```

在 `.env` 中设置这个非敏感路径：

```dotenv
HAIUN_TRUSTED_PROXIES_FILE=./config/trusted-proxies.conf
```

可信代理文件虽然不含凭据，仍是安全敏感配置。绝不能信任 `0.0.0.0/0`：那会允许直接客户端伪造源 IP。只列出实际 TLS 代理或负载均衡器的来源网络。

启动生产栈：

```bash
docker compose -f compose.production.yml up -d --build
docker compose -f compose.production.yml ps
curl http://127.0.0.1/api/health
```

生产模式以 2 vCPU、2 GiB RAM 的宿主机为基线。Compose 对 Haiun、Nginx、Alloy、Loki、Prometheus 和 Grafana 分别设置 `768 MiB`、`64 MiB`、`96 MiB`、`192 MiB`、`192 MiB` 和 `192 MiB` 的内存上限。

生产 Compose 只发布 Nginx 的 `80:80` 和 Grafana 的 `127.0.0.1:3000:3000`；只有 Nginx 对外。Grafana 通过 SSH 隧道访问：

```bash
ssh -L 3000:127.0.0.1:3000 user@server
```

然后在本机打开 `http://127.0.0.1:3000`，以 `admin` 登录，并使用 `secrets/grafana_admin_password.txt` 中保存的密码。

停止生产栈但保留所有命名卷：

```bash
docker compose -f compose.production.yml down
```

### 仪表盘、健康状态与资源

Grafana 自动预置三个仪表盘：

- **Haiun API Overview**：请求速率、状态与错误概况（当前显示 5xx 错误率）、p50/p95/p99 延迟、处理中请求数，以及最繁忙的规范化路由。
- **Haiun Access Sources**：客户端 IP、来源站点主机名、用户代理、最近请求、慢请求和失败请求。
- **Haiun Backend Runtime**：Python CPU、常驻内存、垃圾回收、运行时间、Haiun 抓取健康状态，以及监控服务抓取健康状态。

排障时检查容器、日志、资源与服务就绪状态：

```bash
docker compose -f compose.production.yml ps
docker compose -f compose.production.yml logs --tail=200 nginx haiun alloy loki prometheus grafana
docker stats --no-stream
docker compose -f compose.production.yml exec prometheus \
  wget -qO- http://127.0.0.1:9090/-/ready
docker compose -f compose.production.yml exec grafana \
  wget -qO- http://127.0.0.1:3000/api/health
```

日志和指标均保留 30 天，Prometheus 另有 `512 MB` 大小上限。Grafana 仅能从宿主机回环地址访问。默认不执行 IP 地理定位，不部署宿主机范围的 exporter，也不收集宿主机全局指标。

### 备份与恢复

下面的命令先停止生产服务，再备份默认的应用数据卷；`down` 不会删除命名卷：

```bash
docker compose -f compose.production.yml down
docker run --rm \
  -v haiun-data:/data:ro \
  -v "$PWD":/backup \
  alpine:3.22 \
  sh -c 'umask 077; tar -czf /backup/haiun-data.tar.gz -C /data .'
```

如果通过 `HAIUN_DATA_VOLUME` 覆盖了卷名，请在备份和恢复命令中把 `haiun-data` 替换为该实际卷名。恢复时目标命名卷必须为空：

```bash
docker volume create haiun-data
docker run --rm \
  -v haiun-data:/data \
  -v "$PWD":/backup:ro \
  alpine:3.22 \
  tar -xzf /backup/haiun-data.tar.gz -C /data
```

### 升级

拉取代码、刷新基础镜像并重新创建有变化的服务：

```bash
git pull --ff-only
docker compose -f compose.production.yml build --pull
docker compose -f compose.production.yml up -d
```

### 2 GiB 主机的交换空间

在 2 GiB RAM 主机上，可按发行版要求创建 2 GiB 交换文件作为内存突增时的应急保护：

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
swapon --show
```

交换空间不能替代 CPU 或 RAM。如果分析并发、访问流量、仪表盘使用量或保留数据显著增长，建议至少使用 4 GiB RAM。持久启用交换文件时，请按发行版的正式文档把它加入 `/etc/fstab`，不要自动添加未经审核的配置行。

## 后端配置

管理员访问与完整雀魂牌谱账号使用同一个后端本地 TOML。复制示例文件：

```bash
cp config/config.example.toml config/config.toml
chmod 600 config/config.toml
```

在 `config/config.toml` 中按优先顺序配置一个或多个国服账号，并设置管理员密码：

```toml
timeout_seconds = 15

[[accounts]]
username = "你的雀魂账号"
password = "你的雀魂密码"
host = "https://game.maj-soul.com"

[[accounts]]
username = "备用账号"
password = "备用账号密码"

[admin]
password = "请替换为足够长且唯一的管理员密码"
session_hours = 12
```

后端会按 `[[accounts]]` 的书写顺序尝试；某个账号登录失败或无权访问牌谱时继续下一个账号。`HAIUN_CONFIG` 可覆盖配置文件路径。真实配置文件已被 Git 忽略，不要把账号密码或管理员密码写入示例文件、README、日志或提交记录。当前账号密码登录方式面向雀魂国服；OAuth、邮件验证码和浏览器会话不在支持范围内。

## 访客与管理员访问

网站默认以访客模式打开。访客可以搜索、导入和开始分析，但导航中不显示全局“分析”列表。每次开始分析都会创建独立的 `/results/<随机 UUID>` 地址；相同牌谱可以复用后台计算缓存，但不会覆盖之前的结果地址。

结果地址是可分享的能力链接：没有公开列表或搜索接口可以枚举其他人的结果，但任何收到完整地址的人都可以打开它。请只把结果链接分享给希望查看结果的人。

管理员入口是不会出现在页面导航中的 `/admin`。输入 `config/config.toml` 中至少 12 个字符的管理员密码后，可查看全部分析任务并执行受保护的管理操作；管理员会话默认持续 12 小时，也可通过 `session_hours` 调整。连续失败的登录会被临时限流。

## 网络与安全

默认监听 `0.0.0.0:8765`，便于同一局域网中的设备访问。设定 `HAIUN_HOST=127.0.0.1` 可恢复仅本机访问；`HAIUN_PORT` 修改端口。公网部署必须在前方使用 TLS 反向代理，并配置适当的防火墙与请求限流；管理员密码只保护管理功能，不会把访客搜索、导入、分析或已分享的结果链接变成私有接口。

CORS 默认不允许无关来源。仅在确有需要时设置逗号分隔的 `HAIUN_ALLOWED_ORIGINS`。雀魂账号密码与管理员密码仅由后端从本地 TOML 读取；它们不进入数据库、日志或错误响应。管理员会话 cookie 为 HTTP-only；数据库只保存随机会话令牌的哈希。OAuth token、邮件验证码和浏览器会话不会被请求或处理。

## 数据目录与删除

默认状态目录是仓库下的 `data/`，包含 SQLite 数据库、原始牌谱、规范对局和缓存分析；该目录已被 Git 忽略。`HAIUN_DATA_DIR` 可覆盖路径。复制目录即可备份，停止服务后删除整个目录即可清空全部本地状态。

## 导入格式与限制

单个文件最大 32 MiB。离线路径支持解码 JSON 与牌运规范 JSON；雀魂链接下载保存原始 `ResGameRecord` protobuf，并通过仓库内的麻将魂协议描述解码。可用 `scripts/update_majsoul_protocol.py` 从官方静态资源更新描述文件。可执行文件与归档文件会被拒绝。

Amae-Koromo 是非官方公开索引，其搜索和列表接口可能延迟或暂时不可用。完整牌谱获取依赖本地配置账号能否登录并访问目标牌谱；所有账号均失败时返回 `REPLAY_FETCH_UNAVAILABLE`，配置或网络问题会返回对应的类型化错误。

## 牌运分数含义

`baseline-v1` 比较实际随机结果与当时合法候选结果的加权期望，先累加原始偏差与方差，再把 z-score 映射到 0–100：`50 + 15 × z`，并限制在 0–100。50 表示接近期望，较高表示随机机会更有利，较低表示更不利。它不是实力评分，也不是最终排名预测。

起手分布使用固定种子 `20260713`，分别为四麻庄家、四麻闲家、三麻庄家、三麻闲家实际生成 50,000 个样本；庄家 14 张状态按最优合法弃牌后的形状评估。相同依赖版本、牌谱、算法版本和选项会得到相同结果。

赤五、普通宝牌、杠宝牌、里宝牌、岭上牌和拔北按各自增量路径计算，避免在多个分量中重复。实战点数始终单独显示。

## 测试

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
bash -n scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
nix develop -c shellcheck scripts/dev.sh scripts/start.sh scripts/check_docker_deploy.sh
docker compose -f compose.simple.yml config
GRAFANA_ADMIN_PASSWORD_FILE=/dev/null docker compose -f compose.production.yml config
scripts/check_docker_deploy.sh all
```

生产烟雾测试要求宿主机端口 80 和回环端口 3000 空闲。脚本使用隔离的临时配置、密码文件、网络和卷名，结束时会清理这些资源。
