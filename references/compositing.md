# 独立安装、配置与技术核验

本技能所有运行资源都在技能文件夹中，不需要原 Sticker 项目、羊羊素材或某个父目录。生成新角色画面依赖宿主环境可用的图像生成工具，安装技能不会自动获得模型或 API 权限。

## 安装与依赖

把完整 `plush-animated-stickers/` 复制到目标客户端认可的技能目录，例如 Codex 的用户技能目录 `~/.codex/skills/`。不要覆盖已经存在的同名技能；先比较或另存旧版本。本次源码留在项目 skills 中，打包分发不等于已安装到全局目录。

Python 3.10+，依赖为 `Pillow>=9.1`。优先复用已有环境，可先运行 `python3 -c "import PIL; print(PIL.__version__)"`。需要安装时在工作区创建虚拟环境，使用该环境的 Python 安装技能内的 requirements.txt，不向技能目录写虚拟环境。无需 Blender、NumPy 或 OpenAI API Key 来运行合成器；出图工具的可用性另行检查。

定位实际的技能绝对路径为 SKILL_DIR，工作区路径为 WORKSPACE。以下示意使用 shell 变量 `sticker_skill_dir`，调用前赋为实际路径；配置和输出路径同样换成自己的文件：

```sh
python3 "$sticker_skill_dir/scripts/build_stickers.py" --help
python3 "$sticker_skill_dir/scripts/build_stickers.py" --config /absolute/workspace/config.json --check
python3 "$sticker_skill_dir/scripts/build_stickers.py" --config /absolute/workspace/config.json --output /absolute/workspace/work/new-release
python3 "$sticker_skill_dir/scripts/build_stickers.py" --verify /absolute/workspace/work/new-release
```

`--check` 在内存执行预处理、编码及技术校验，但不创建文件/目录。实际构建拒绝已有输出目录与安装技能内部目录。输入路径相对配置文件，不依赖 shell 当前目录。`--verify` 只读取成品目录及其中归档副本，不要求原输入路径仍存在。

## 配置字段

从 [示例](../assets/config.example.json) 复制并修改。它不是可直接出图的样本，先准备各输入文件。数字均为可配置制作目标，未声明为平台规则。

| 字段 | 含义 |
|---|---|
| version | 当前配置版本 1 |
| canvas | GIF 画布 [宽,高] |
| character_box | 人物安全区域 [左,上,右,下]，下方可留字幕空间 |
| alpha_threshold | 1–254，前景框和 GIF 单比特透明阈值 |
| font / font_size / caption_y / text_color | 字幕字体文件及布局；仅有非空 caption 时需要 font。字体可读取不等于能覆盖所有字形，实际效果由人查看 |
| matte | 共享色板采样时的合成底色，默认 white；不改变导出透明背景 |
| provenance | 参考图、实际提示词、身份记录、生成记录等需要原样保留的文件路径数组 |
| stickers | 至少一个动作，见下表 |
| companions | 必含 banner、cover、icon，可增加 artist-avatar、artist-banner |

每个 `stickers` 项：

| 字段 | 含义 |
|---|---|
| id | 唯一文件名前缀；不含斜杠，不能与其他动作/配套角色 id 相同 |
| sheet | 规则关键帧网格 PNG 路径 |
| grid | [列数,行数]；按从左到右、从上到下切格 |
| sheet_size | 可选，期望的原图 [宽,高]；有则与实际尺寸精确比对 |
| caption | 可选；空串表示无字 |
| order | 零起始关键帧索引；缺省按网格阅读顺序 |
| durations_ms | 与 order 等长，正数且为 10 毫秒的整数倍，避免 GIF 时间量化差异；缺省每帧 200ms |
| offsets | 每个源格对应 [x,y] 输出像素位移，顺序与源格一致，向上跳跃用负 y；缺省全零 |
| loop | GIF 循环字段，默认 0 无限循环 |
| max_bytes | 可选，本次文件体积目标，不代表平台限制 |

每个配套项配置 `source`、`size`、`format`（PNG/JPEG），可选 `max_bytes`。透明封面与图标只接受 PNG，其他素材需要不透明源图。导出时等比居中裁切，不能自动保证主体不被裁切，需人工查看。JPEG 在若干质量档位下尝试体积目标；PNG 无损输出，超限时保留原图并在新版本调整，不偷偷扁平化透明背景。

## 输出与边界

- `upload/`：所有动作 GIF 与独立配套文件。既可逐项使用，也可由调用者再打包。
- `sources/`：实际配置、脚本、参考/提示词/字体（列入 provenance 或实际使用的输入）、源关键帧和配套原图的哈希命名副本。
- `manifest.json`：每个输入与成品哈希、实际技术属性、输出目标、依赖版本、技术以外的 pending 状态。
- `validation.json`：对保存后文件再次解码核验的报告。`--verify` 会重新读取实际文件，不信任旧报告。

默认算法使用前景下部中心锚点、统一尺度和固定脚底基线，结合用户的 offsets 表达位移。这适合许多站立角色；蛇形、飞行、极度变化的轮廓或多角色同格需专门调整。不要用自动验证来推断角色一致性。六格、多帧往返与示例字幕只是配置选择，动作是否自然需要人观看。

## 可重复的离线检查

`tests/test_portability.py` 使用几何测试图核验独立复制、跨工作目录调用、切格/位移、GIF 时间/循环/透明、配套导出、来源完整性和拒绝覆盖。它不会调用生成工具，不产生新的角色设计，不证明任何角色的视觉效果。运行：

```sh
python3 -m unittest discover -s "$sticker_skill_dir/tests" -v
```
