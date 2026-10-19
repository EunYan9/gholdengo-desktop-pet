# 赛富豪桌宠

Windows 透明桌面宠物：用赛富豪与索财灵陪伴 Codex 工作，显示剩余额度、每日使用建议和运行任务的 token 统计。

![点击金币效果](docs/coin-burst-preview.webp)

## 启动

1. 安装 Python 3.10 或更新版本，并安装、登录官方 Codex 桌面应用。
2. 下载或克隆此仓库，双击 `run.bat`。首次运行自动创建 `.venv` 并安装依赖，需要网络。
3. 双击 `run-review.bat`，可以预览赛富豪金币特效和其他形态，模拟开工与收工。

也可先运行 `setup.bat` 安装依赖。日常播放使用仓库中的本地动画；额度同步需要网络。运行时使用当前电脑已登录的 Codex，仓库不包含个人登录凭证或使用记录。

拖动头顶额度条移动桌宠；右键宠物、额度条或托盘图标，可直接进入 ChatGPT / Codex 桌面端页面、同步额度、隐藏每日建议、开关完成音效和退出。

## 当前版本

- **桌面端对话入口**：右键直接选择“与 ChatGPT 对话”或“与 Codex 对话”，通过原生链接打开客户端对应模式的新对话页，已移除中间气泡与预览入口，不再模拟按键。
- **可选完成音效**：默认关闭，避免与 Codex 自带声音重复；支持右键开启，按观测到的任务本轮成功完成去重提醒。

- **赛富豪**：512×512、80 帧朱紫原生冲浪循环，完整保留头发与金币质感。单击从点击处弹出翻转金币，带细齿压边、金属高光和少量微光，沿弧线散开后淡出。连点有数量上限，工作时同样生效，交互不重置身体动画。
- **索财灵**：宝箱和徒步形态保留原生动作，包括随机待机、点击回应、严格滚动 1 秒内三连点嫌弃、小憩和独立收工动作；宝箱工作与点击通过匹配的原始姿态自然衔接。
- **额度条**：同时显示五小时与一周剩余百分比，每 180 秒同步；悬停可看重置时间。按较低剩余值切换形态：≥80% 赛富豪、20%～80% 宝箱、3%～20% 徒步、低于 3% 休眠。
- **每日建议**：按北京时间 02:00 至次日 02:00 统计，依次按周剩余 / 7、/ 6……/ 1 分配当天建议；周期自动跟随服务端周重置时间，提前重置后重新分配，重置时间漂移不会重复增加建议。启动时恢复历史额度元数据；缺少基准时明确显示缺口，不把未知当作 0。达到建议的 80%、100% 时提醒。
- **工作陪伴**：每秒读取本机 Codex 任务状态；悬停“专注”气泡可看运行任务、本轮和累计 token、输入与输出计数。浮层保留不透明深色底板与透明圆角外侧。成功结束、中断和失败分别处理；ChatGPT 模式下的普通对话任务状态尚未接入。

赛富豪目前只使用这一段可靠的原生循环；未提供额外的身体挥手、嫌弃、庆祝或睡眠动画。相应回应使用气泡和金币特效，索财灵仍保留完整动作。

额度百分比不能直接换算为固定 token 个数；没有虚构月余额。任务 token 统计通常在调用结算后更新，未完成的流式生成可能尚未计入，历史记录不完整时会明确标注。工作状态覆盖整轮任务执行，包含推理、工具调用和等待交互。状态与计数读取依赖当前 Windows Codex 本地存储结构；结构不兼容时回退，不监测其他电脑或纯云端任务。只解析相关计数和状态元数据，不展示对话正文、不修改 Codex 配置。

公开版仅包含当前 Codex 桌宠。旧版 Kimi / 零的源码、素材和原始历史保留于私有备份，不随公开版分发。

## 验证与素材工具

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s codex-pet -p test_usage.py
.\.venv\Scripts\python.exe -m unittest discover -s codex-pet -p test_activity.py
.\.venv\Scripts\python.exe -m unittest discover -s codex-pet -p test_daily_budget.py
.\.venv\Scripts\python.exe -m unittest discover -s codex-pet -p test_quota_history.py
.\.venv\Scripts\python.exe -m unittest discover -s codex-pet -p test_task_usage.py
.\.venv\Scripts\python.exe codex-pet\test_gholdengo.py
.\.venv\Scripts\python.exe codex-pet\test_animation.py
.\.venv\Scripts\python.exe codex-pet\test_panels.py
```

运行 `test_pose_joins.py` 或素材打包工具额外需要 Pillow。详细实现、动画再生成方法和署名见 [技术说明](codex-pet/README.md)。运行程序无需 Blender、在线模型或重新渲染。

## 素材来源

- 赛富豪：[PokeStats 朱紫原生动画](https://pokestats.gg/sprites/gholdengo)。512×512 原文件按字节保留，来源与哈希记录见 [gholdengo-sources.json](codex-pet/gholdengo-sources.json)。金币特效由本项目本地矢量绘制。
- 宝箱索财灵：[Mariokart07 / Sketchfab，CC BY 4.0](https://sketchfab.com/3d-models/chest-gimmighoul-sv-68bbff72defd42808c713d914e46ad66)。
- 徒步索财灵：[Mariokart07 / Sketchfab，CC BY 4.0](https://sketchfab.com/3d-models/gimmighoul-sv-c70b33ba97674401bff5b03f3068c2ea)。

角色与游戏素材权利属于 Pokémon / Nintendo / Creatures / GAME FREAK；上传者的许可标注不等同于角色 IP 授权。本项目是非官方个人学习项目，与 Pokémon、Nintendo、Creatures 或 GAME FREAK 无隶属关系。源码公开不代表游戏素材获得商业使用或再次分发授权。
