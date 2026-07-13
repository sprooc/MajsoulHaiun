# 牌运 Haiun

牌运（Haiun，取自日文“牌運”的读音）是一款中英双语、自托管的立直麻将牌谱与运气分析应用。它支持标准四人麻将与三人麻将，把原始牌谱、规范对局事实和分析结果分层保存在本机，并解释随机机会如何影响每位玩家。

## 功能

- 通过 Amae-Koromo 的匿名公开索引搜索四人/三人玩家和近期对局。
- 导入雀魂分享链接、牌谱 ID、解码 JSON 或牌运规范 JSON。
- 在匿名原始牌谱不可用时返回 `REPLAY_FETCH_UNAVAILABLE`，继续保留公开元数据与本地文件导入能力。
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

## 网络与安全

默认监听 `0.0.0.0:8765`，便于同一局域网中的设备访问。设定 `HAIUN_HOST=127.0.0.1` 可恢复仅本机访问；`HAIUN_PORT` 修改端口。应用没有身份验证，不能直接暴露到公网。公网使用必须在前方部署带 TLS、身份验证和防火墙策略的反向代理。

CORS 默认不允许无关来源。仅在前后端分离部署时设置逗号分隔的 `HAIUN_ALLOWED_ORIGINS`。应用不会请求、保存或传输雀魂密码、OAuth token、邮件验证码或浏览器会话。

## 数据目录与删除

默认状态目录是仓库下的 `data/`，包含 SQLite 数据库、原始牌谱、规范对局和缓存分析；该目录已被 Git 忽略。`HAIUN_DATA_DIR` 可覆盖路径。复制目录即可备份，停止服务后删除整个目录即可清空全部本地状态。

## 导入格式与限制

单个文件最大 32 MiB。当前稳定离线路径支持解码 JSON 与牌运规范 JSON；二进制 protobuf 解码依赖仓库内的麻将魂协议描述，可用 `scripts/update_majsoul_protocol.py` 从官方静态资源更新。可执行文件与归档文件会被拒绝。

Amae-Koromo 是非官方公开索引，其搜索和列表接口可能延迟或暂时不可用。匿名获取完整雀魂事件字节不作保证；应用不会以登录或隐藏凭证绕过此限制。

## 牌运分数含义

`baseline-v1` 比较实际随机结果与当时合法候选结果的加权期望，先累加原始偏差与方差，再把 z-score 映射到 0–100：`50 + 15 × z`，并限制在 0–100。50 表示接近期望，较高表示随机机会更有利，较低表示更不利。它不是实力评分，也不是最终排名预测。

起手分布使用固定种子 `20260713`，分别为四麻庄家、四麻闲家、三麻庄家、三麻闲家实际生成 50,000 个样本；庄家 14 张状态按最优合法弃牌后的形状评估。相同依赖版本、牌谱、算法版本和选项会得到相同结果。

赤五、普通宝牌、杠宝牌、里宝牌、岭上牌和拔北按各自增量路径计算，避免在多个分量中重复。实战点数始终单独显示。

## 语言

初始语言为中文。页面右上角可切换中文与 English；测试会递归比较两套翻译资源的键树。

## 测试

```bash
nix develop -c .venv/bin/python -m pytest backend/tests -v
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix frontend run e2e
bash -n scripts/dev.sh scripts/start.sh
shellcheck scripts/dev.sh scripts/start.sh
```
