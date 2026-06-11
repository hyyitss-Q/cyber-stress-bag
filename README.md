# 🐱 赛博出气包 · 桌面像素猫

一只常驻你桌面的像素风小猫，也是永远站在你这边的 AI 损友。上班压力大、被甲方折磨、被老板 PUA？单击它，倒给它听。

它会半透明悬浮在桌面最上层、会眨眼、会随机冒泡吐槽，能拖到任何角落，还会记住你把它放哪了。基于 Claude（Opus 4.8）+ PySide6，纯本地运行。

## 它能干啥

- 🖱️ **单击猫** 弹出聊天面板，跟它吐槽，回复逐字流式蹦出来。
- 😺 **会动**：眨眼、说话张嘴、闲着时偶尔冒泡来一句打工人嘴替金句。
- 🎚️ **毒舌强度可调**：滑块从「温柔顺毛」拉到「殇血开炮」，实时改变它的火力。
- 💾 **记得住**：对话自动保存，下次启动接着聊；可一键清空或导出成文本。
- ⌨️ **全局热键 + 托盘**：`Ctrl+Alt+C` 随时呼出/隐藏，托盘菜单管模式、自启等。
- 🚀 **开机自启**（可选）：开机就有猫陪你。

## 四种模式

| 模式 | 干啥用 |
|------|--------|
| 😤 **吐槽出气** | 纯陪骂、纯顺毛。把今天的破事倒出来，它帮你骂回去，绝不当和事佬。 |
| 💬 **嘴替回怼** | 给你 3 版能直接发出去的回怼（刚正面 / 阴阳怪气 / 幽默化解）。 |
| 🛋️ **一起摆烂** | 不激励你，陪你一起摆，帮你找「今天不想上班」的离谱理由。 |
| 🔮 **赛博算命** | 不正经神棍，算算「这破班还要上多久」「今天宜不宜摸鱼」。 |

## 怎么跑起来

### 1. 装依赖

```bash
pip install -r requirements.txt
```

> PySide6 体积稍大（约 100MB+），第一次装会慢点，耐心等。

### 2. 配 API key

去 [platform.claude.com](https://platform.claude.com) 申请一个 key，然后任选一种：

**方式 A（推荐）**：把 `.env.example` 复制成 `.env`，填进你的 key：

```
ANTHROPIC_API_KEY=sk-ant-你的key
```

**方式 B**：直接设环境变量：

```bash
export ANTHROPIC_API_KEY="sk-ant-你的key"
```

> 没设 key 也能启动，猫会先待在桌面上，设好 key 重启就能聊。

### 3. 启动

```bash
python main.py
```

桌面右下角会蹦出一只猫。单击它开聊，拖动它换位置，`Ctrl+Alt+C` 呼出/隐藏。

## 可选配置（环境变量）

都不是必填，不填走默认值。可写进 `.env` 或设为系统环境变量：

| 变量 | 默认 | 作用 |
|------|------|------|
| `CYBERCAT_MODEL` | `claude-opus-4-8` | 用哪个模型 |
| `CYBERCAT_MAX_TOKENS` | `2048` | 单次回复最大 token |
| `CYBERCAT_MAX_RETRIES` | `3` | 限流/过载时自动重试次数 |
| `CYBERCAT_HOTKEY` | `Ctrl+Alt+C` | 呼出/隐藏猫的全局热键 |

## 想自己调教它

整个猫的「性格」全在 `prompts.py` 里。想让它更损、更温柔、加新模式，改那个文件就行。

- `_BASE`：所有模式共享的底层人设（永远向着你、不说教那套）。
- `VENT` / `ROAST_BACK` / `LIE_FLAT` / `FORTUNE`：四个模式各自的指令。
- `_SAVAGERY_LEVELS`：毒舌强度三档的语气指令。
- `build_system_prompt(mode, savagery)`：把三层拼成最终 prompt。
- 加新模式：在 `_MODE_SECTIONS` 和 `MODE_HINTS` 里各加一项即可。

想换猫的长相？`cat_sprite.py` 里每帧就是一组等宽字符，配一张调色板，改字符就能重画。

## 项目结构

```
cyber-stress-bag/
├── main.py          # 入口：托盘 + 装配各窗口 + 启动检查
├── pet_window.py    # 悬浮像素猫（动画 / 拖动 / 冒泡）
├── chat_window.py   # 聊天面板（模式 / 毒舌滑块 / 清空导出）
├── ai_worker.py     # 后台线程跑 Claude 流式（重试 / 取消）
├── cat_sprite.py    # 代码绘制的像素猫（无外部素材）
├── prompts.py       # 人设 prompt（灵魂所在）
├── config.py        # 配置与持久化（位置 / 历史 / 环境变量）
├── hotkey.py        # Windows 全局热键
├── autostart.py     # Windows 开机自启
├── requirements.txt
├── .env.example     # API key + 可选配置模板
└── README.md
```

> 注：全局热键和开机自启是 Windows 专属功能，其它系统上会自动跳过（猫和聊天照常用）。
