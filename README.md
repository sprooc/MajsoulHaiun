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
bash -n scripts/dev.sh scripts/start.sh
shellcheck scripts/dev.sh scripts/start.sh
```
