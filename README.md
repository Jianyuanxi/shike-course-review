# 拾课：课程资料复习助手

把散落在文件夹中的 Markdown、TXT、PDF 课程资料切块存入 seekdb，用关键词与向量混合检索回到原文；再用 PowerContext 记录查询和反复出现的薄弱知识点，自动生成复习清单。

## 核心功能

- **资料导入**：选择一个文件夹，导入其中的 `.md`、`.txt`、`.pdf`；支持相对目录、SHA-256 去重和变化文件重新导入。
- **原文检索**：seekdb 全文检索与 512 维本地向量检索经 RRF 融合，返回最相关的 5 段原文。
- **准确定位**：Markdown/TXT 保留段落范围，PDF 保留页码；可展开命中块前后各 2 块上下文。
- **学习记忆**：每个用户对应独立 PowerContext Scope，每次查询写入 Source，每个知识点写入 Atomic Memory。
- **薄弱点与复习清单**：同一知识点查询第 2 次后成为薄弱点；首页显示查询次数、记忆 Revision 和关联原文。
- **可核对日志**：页面展示 seekdb 检索候选、RRF/最终排名、薄弱点加权，以及 PowerContext HTTP 状态、Artifact、Revision 和 Request ID。

## 技术分工

| 组件 | 实际用途 |
| --- | --- |
| seekdb | `course_chunks` Collection 保存原文、向量和出处元数据；执行全文 + 向量混合检索；保存文档、检索和记忆审计表。 |
| PowerContext 1.4.1 | Scope 隔离用户；Source 保存查询证据；Atomic Memory 保存知识点查询次数、最近问题和原文引用。 |
| FastAPI | 文件上传、切块、检索、记忆、复习清单和审计 API，同时托管前端。 |
| BGE 本地模型 | `BAAI/bge-small-zh-v1.5`，CPU 上生成归一化向量，不需要 API Key。 |
| 原生 HTML/CSS/JavaScript | 导入、检索、上下文、薄弱点、复习清单和技术记录页面。 |

检索先取最多 20 个 RRF 候选，再计算 `final_score = 1 / (60 + rrf_rank) + weak_boost`。命中既有薄弱点关联原文时 `weak_boost = 0.0005`，只在相近候选间提供优先权，避免记忆信号压过最相关的新资料。

## 目录结构

```text
qoder/
├── backend/
│   ├── app/
│   │   ├── db/              # seekdb 连接与审计表
│   │   ├── services/        # 切块、导入、向量、检索、PowerContext
│   │   └── main.py          # FastAPI 入口
│   ├── tests/               # 不依赖外部服务的单元测试
│   ├── pyproject.toml
│   └── uv.lock
├── frontend/                # 单页应用
├── samples/course/          # 4 个示例文件，共 9 个原文块
├── docs/verification/       # 真实 API 响应与审计证据
├── 开发记录/                # 实际浏览器验收截图
├── docker-compose.yml
├── .env.example
└── 验证样例.md
```

## 环境与已验证版本

- Windows 11（其他可运行 Docker 与 Python 的平台也可按相同命令部署）
- Docker 29.9.1、Docker Compose v5.6.0
- uv 0.10.8
- Python `>=3.11,<3.13`，由 uv 按项目配置安装
- seekdb 镜像 `oceanbase/seekdb:1.4.0-100000172026082615`
- PowerContext 官方 Git tag `powercontext-v1.4.1`
- Python 依赖的精确版本见 `backend/pyproject.toml` 和 `backend/uv.lock`

首次构建 PowerContext 需要访问 GitHub，首次生成向量需要下载 BGE 模型；模型随后使用本地缓存。运行过程不需要 LLM 或 embedding API Key。

## 从安装到启动

在本目录（`qoder/`）执行以下命令。

### 1. 准备配置

```bash
cp .env.example .env
```

Windows CMD 也可使用 `copy .env.example .env`。默认值即可在本机运行；不要提交真实密码或 Key。

### 2. 启动 seekdb 与 PowerContext

先启动 Docker Desktop，再执行：

```bash
docker compose up -d --build
docker compose ps
```

预期容器：

- `course-review-seekdb`：MySQL 协议 `127.0.0.1:2881`
- `course-review-powercontext`：HTTP `127.0.0.1:8000`，健康状态为 `healthy`

数据分别保存在 Docker named volumes `seekdb-data` 和 `powercontext-data` 中，普通停止或重启不会清空。

### 3. 安装后端依赖

安装 [uv](https://docs.astral.sh/uv/) 后执行：

```bash
uv sync --directory backend
```

### 4. 启动应用

```bash
uv run --env-file ../.env --directory backend uvicorn app.main:app --host 127.0.0.1 --port 8080
```

打开 <http://127.0.0.1:8080>。PowerContext Dashboard 位于 <http://127.0.0.1:8000/dashboard>。

健康检查：

```bash
curl http://127.0.0.1:8080/api/health
```

预期包含 `"status":"ready"`、`"powercontext":"ready"` 和本地模型名。

### 5. 运行测试

```bash
uv run --directory backend pytest -q
```

本次最终回归结果为 `10 passed in 2.50s`。

## 使用流程

1. 输入学习空间标识，默认 `demo`。标识只支持字母、数字、下划线和短横线。
2. 点击“导入示例资料”，或选择自己的资料文件夹。单个文件上限 15 MiB。
3. 输入问题并点击“检索原文”。首次导入和检索会因模型加载稍慢。
4. 点击任意结果的“查看上下文”核对原文。
5. 对同一知识点查询两次，查看“最近常查”和“薄弱点复习清单”。
6. 在“技术运行记录”中核对检索与记忆读写。完整预期结果见 [验证样例.md](验证样例.md)。

示例资料来源和改动说明见 [samples/SOURCES.md](samples/SOURCES.md)。

## 配置项

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `SEEKDB_HOST` / `SEEKDB_PORT` | `127.0.0.1` / `2881` | seekdb 连接 |
| `SEEKDB_DATABASE` | `course_review` | 应用数据库 |
| `SEEKDB_USER` / `SEEKDB_PASSWORD` | `root` / 空 | 本地 seekdb 账号 |
| `POWERCONTEXT_URL` | `http://127.0.0.1:8000` | PowerContext HTTP API |
| `POWERCONTEXT_TOKEN` | 空 | 仅在外部服务启用认证时填写 |
| `EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 本地向量模型 |
| `EMBEDDING_DEVICE` | `cpu` | 向量计算设备 |

更换向量模型或维度后需要重建 Collection 和原文向量，不能混用不同向量空间。

## 停止与边界

```bash
docker compose stop
```

前端和后端默认只绑定 `127.0.0.1`。学习空间标识用于演示数据隔离，PowerContext Scope 也是数据分区而不是身份认证；不要在未增加认证和访问控制的情况下直接暴露到公网。

真实运行证据位于 [docs/verification/](docs/verification/)，浏览器截图位于 [开发记录/](开发记录/)。

## 项目介绍网站

公开代码仓库：<https://github.com/Jianyuanxi/shike-course-review>

Qoder Sites 公开地址：<https://shike-course-review-hbvu92d2jdk.qoder.zone>

介绍站包含项目简介、痛点、核心功能、seekdb/PowerContext 分工、真实运行截图、验证证据、仓库链接和本地运行方法。静态源文件位于 `site/dist/`，公开访问与发布版验收记录见 [验证样例.md](验证样例.md)。
