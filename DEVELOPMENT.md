# SHABO（傻波儿）开发交接文档

CABO（傻波儿）原型衍生的**横版手机网页卡牌对战游戏**，2–5 人实时联机。每人 4 张手牌，目标是手牌总分尽量低（0 最好、13 最差），通过摸牌、取弃牌堆、技能牌、呼叫 SHABO 等机制博弈。

## 一、环境信息

| 项 | 值 |
| --- | --- |
| 本地代码 | `E:\SHABO2` |
| 线上地址 | http://124.223.164.216:8082 |
| 服务器 | 腾讯云 `124.223.164.216`，部署目录 `/opt/shabo2` |
| 端口 | 前端 nginx `8082:80`；后端 uvicorn `8000`（仅内网） |
| 设计基准 | 960×540 横版舞台，CSS transform 等比缩放（竖屏自动旋转 90°） |

## 二、技术栈

**后端**：FastAPI 0.111 + Uvicorn 0.30 + SQLAlchemy 2.0 + SQLite + python-jose / passlib（JWT + bcrypt）。

**前端**：Vue 3 `<script setup>` + Vite 5 + Pinia + vue-router 4，原生 WebSocket，无 UI 框架。

## 三、目录结构

```
SHABO2/
├─ docker-compose.yml          后端 + 前端 nginx，卷 shabo_data:/data
├─ .env                        SECRET_KEY / 超时 / TARGET_SCORE
├─ backend/
│  ├─ Dockerfile  requirements.txt
│  └─ app/
│     ├─ main.py               FastAPI 入口、create_all + ensure_schema、/api/health
│     ├─ config.py             Settings（环境变量）
│     ├─ database.py           engine / SessionLocal / Base / ensure_schema()
│     ├─ models.py             User / SeasonRecord / AppState
│     ├─ schemas.py            Pydantic 入参出参
│     ├─ security.py           JWT 签发校验、密码哈希
│     ├─ deps.py               get_current_user
│     ├─ hub.py                连接注册表（每个玩家一条 socket）
│     ├─ season.py             赛季滚动与归档
│     ├─ ws.py                 全部实时协议 + 计时器 ticker + 战绩写入
│     ├─ game/
│     │  ├─ cards.py           54 张牌构建、技能映射
│     │  ├─ engine.py          权威游戏引擎
│     │  ├─ room.py            房间生命周期、RoomManager、机器人
│     │  └─ bots.py            机器人自动决策
│     └─ routers/
│        ├─ auth.py            注册 / 登录 / me
│        └─ profile.py         资料更新、排行榜、个人战绩
├─ frontend/
│  └─ src/
│     ├─ views/  Login / Hall / Game / Rules
│     ├─ components/  Stage（缩放）/ Avatar / PlayingCard
│     ├─ store/  auth.js（HTTP）/ game.js（WS 状态 + 动画事件队列）
│     ├─ ws/client.js          断线重连、心跳、单点登录
│     ├─ api/http.js|server.js 请求封装、服务器地址可配置
│     ├─ data/  rules.js 规则文案 / emotes.js / assets.js
│     └─ router/index.js
└─ tools/   prepare_assets.py / shrink_emoji.py / smoke_ws.py / reset_stats.py
```

## 四、本地开发与部署

### 4.1 本地启动

```bat
rem 后端（首次需建 venv 并 pip install -r requirements.txt）
cd /d E:\SHABO2\backend
set DATABASE_URL=sqlite:///E:/SHABO2/backend/shabo.db
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

rem 前端
cd /d E:\SHABO2\frontend
npm run dev        rem http://localhost:5173，已代理 /api 与 /ws
```

> 本地后端**不带 `--reload`**，改后端代码必须手动重启。Windows 下先 `netstat -ano | findstr :8000` 找 PID，再 `taskkill /PID x /F`。

### 4.2 部署

仅在确认后执行：

```bat
tar -czf "%TEMP%\shabo2.tar.gz" --exclude=node_modules --exclude=dist --exclude=__pycache__ --exclude=.venv --exclude=.git -C E:\SHABO2 .
scp -i "E:\codemaker\Exercise_check_in.pem" -o StrictHostKeyChecking=no "%TEMP%\shabo2.tar.gz" root@124.223.164.216:/opt/shabo2/shabo2.tar.gz
ssh -i "E:\codemaker\Exercise_check_in.pem" -o StrictHostKeyChecking=no root@124.223.164.216 "cd /opt/shabo2 && tar -xzf shabo2.tar.gz && rm -f shabo2.tar.gz && docker compose up -d --build"
```

## 五、核心机制实现要点

### 5.1 游戏引擎 `app/game/engine.py`

- **状态机**：`Phase`（INITIALIZING / PEEK_PHASE / PLAYING_PHASE / CABO_COUNTDOWN / SETTLING）× `Sub`（IDLE / PEEK_SELECT / REVEAL / WAITING_ACTION / CARD_DRAWN / SPECIAL）。
- **手牌槽位**：`HandSlot(card, revealed_to)`，`revealed_to` 记录"谁知道这张牌"，是信息隔离的唯一依据。
- **开局看牌**：按 `peek_order()` 轮流选 2 张看；超时/离线由 `_auto_peek` 随机代选。看牌时给本人发 `reveal`（带点数），同时给全场发 `peek`（只带位置、无点数），其他玩家看到「👁 被查看」标记但看不到牌面。
- **单张查看**：`_reveal_to(viewer, owner, slot)` 技能共用，非本人时同样广播 `peek`。
- **神风**：手牌恰为 12/12/13/13 时本人 0 分，其余各 +50，覆盖 SHABO 惩罚。
- **SHABO 呼叫**：`CABO_PENALTY = 10`，其余玩家各行动 1 回合后结算。
- **两种赛制**：`SINGLE`（单局）/ `MULTI`（累计到 `target_score=100` 结束，总分最低者胜）。

### 5.2 事件与信息过滤（关键设计）

引擎通过 `_emit(kind, ..., visible_to=...)` 产生事件队列，`ws.filter_events()` 按 `visible_to` 裁剪：

- `visible_to="all"`：所有人可见；
- `visible_to=[id]`：仅该玩家可见；
- 不允许者若事件带 `card` 则置空，`reveal` 事件直接丢弃。

`push_room()` 对每个成员分别调用 `snapshot_for(viewer_id)` + `filter_events()`，**每个玩家收到定制化状态**，不依赖前端隐藏。

### 5.3 房间 `app/game/room.py`

内存态（`room_manager`），重启即清空。房间号 6 位数字，`ROOM_MIN/MAX_PLAYERS = 2/5`。房主离开自动转移给下一位真人。机器人 `bot_xxxx` 仅管理员 + 房主可增删。

### 5.4 计时与战绩 `app/ws.py`

- 全局 `ticker_loop()`（0.4s）推进所有房间 `engine.tick()` + `bots.maybe_act()`，有变更才广播。
- `keepalive_loop()` 每 20s 服务端下行 ping，防止浏览器后台节流导致断连。
- `record_match_stats()` 在 `round_result is not None and match_over` 时写入生涯 + 赛季数据；异常必须吞掉（战绩不能影响对局）。

### 5.5 赛季 `app/season.py`

按东八区自然月划分，`ensure_season(db)` 惰性滚动：`AppState["current_season"]` 与当前月份不一致时，归档三榜排名到 `SeasonRecord`（标准竞赛排名），然后清零 `season_wins / season_shabo / season_low`。所有涉及赛季的接口都会先调用它。

### 5.6 数据库迁移

`Base.metadata.create_all` **不会 ALTER 已存在的表**。新增列必须手动追加到 `database.py:ensure_schema()` 的 `ALTER TABLE` 列表，否则线上 SQLite 会因缺列报错。

## 六、WebSocket 协议

**客户端 → 服务端**：`auth`（首帧，带 token）、`ping`、`sync`、`create_room`、`join_room`、`leave_room`、`invite`、`invite_response`、`ready`、`chat`、`start_game`、`next_round`、`back_to_room`、`add_bot`、`remove_bot`、`kick`、`peek_select`、`draw`、`discard`、`replace`、`take_discard`、`use_special`、`special_select`、`cancel_special`、`call_cabo`。

**服务端 → 客户端**：`authed`、`room_state`（含 `room` / `game` / `events`）、`invite`、`notice`、`error`、`ping`。

同一账号重复登录时，新 socket 顶替旧 socket，旧连接以 **4001** 关闭并提示"该账号已在其他设备登录"。

## 七、已实现功能

**基础**：注册登录、头像预设（13 种）与昵称修改、房间创建/加入/邀请 ID、准备/开局、聊天与快捷语、表情包、机器人对战、断线重连、单点登录。

**对局**：开局看牌（含位置广播）、摸牌/取弃牌、多张凑对换牌、明牌角标、技能（7/8 自窥、9/10 窥敌、11/12 盲换）、SHABO 呼叫、神风、弃牌堆重洗、结算揭示动画、记忆辅助。

**社交与成长**：

- 房间内点击任意头像查看战绩卡（生涯胜场 / 傻波次数 / 生涯最低分 + 本赛季 + 历史赛季排名）；点击自己头像显示战绩卡，卡内「修改资料」为二级弹窗。
- 房主踢人（仅等待中、非机器人、非自己）。
- 排行榜三榜：胜场榜 / 极限榜（最低分）/ 傻波榜，每榜前 20 名 + 自己的名次。
- 赛季奖励：左侧展示当前榜的专属徽章（`public/art/shabo_champion_badge_s1.png`、`shabo_geek_badge_s1.png`、`shabo_king_badge_s1.png`），可点击看大图。
- 创建房间采用默认值：5 人 + 100 分赛制（`MULTI`），无需选择。
- 规则页含完整规则、胜场规则、赛季规则。

## 八、注意事项

1. 后端改代码必须重启本地 uvicorn（无 `--reload`），否则接口 404。
2. 新增数据库列要同步修改 `ensure_schema()`。
3. 房间数据全在内存，服务重启对局全丢，这是有意设计。
4. 前端缩进使用 Tab；`Game.vue` / `Hall.vue` 体量大（Scoped CSS 很长），改动时注意定位对应块。
5. 弹窗层叠靠 DOM 顺序（后面的 `.mask` 覆盖前面的），二级弹窗必须放在一级之后。
6. `filter_events` 是信息隔离的关键，新增事件都要考虑 `visible_to`，否则会泄露手牌。
7. 线上数据库在 Docker 卷 `shabo_data`，容器内路径 `/data/shabo.db`。
8. 运维脚本 `tools/reset_stats.py`：清空全部战绩与排行榜但**不删账号**。用法：

```bat
scp -i "E:\codemaker\Exercise_check_in.pem" -o StrictHostKeyChecking=no "E:\SHABO2\tools\reset_stats.py" root@124.223.164.216:/opt/shabo2/reset_stats.py
ssh -i "E:\codemaker\Exercise_check_in.pem" -o StrictHostKeyChecking=no root@124.223.164.216 "docker cp /opt/shabo2/reset_stats.py shabo2-backend-1:/tmp/reset_stats.py && docker exec shabo2-backend-1 python /tmp/reset_stats.py && rm -f /opt/shabo2/reset_stats.py"
```

## 九、后续可考虑方向

观战与回放、目标分可配置的更多赛制、徽章在个人资料页展示、排行榜分页、对局中途离场惩罚、移动端体验优化（当前仅横屏）、单元测试补齐（现有 `tests/rules_test.py` 与 `tools/smoke_ws.py`）。

## 十、编码规范

后端 Python 遵循：Tab 缩进、Google 风格 Docstring、单行不超过 120 字符、导入按标准库/第三方/本地分组、文件末尾单个换行、函数与变量 `snake_case`、类名 `PascalCase`、禁止裸 `except`。
