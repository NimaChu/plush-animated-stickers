# 可替换的提示词模板

模板中的双花括号表示要填写的输入变量，不是提交给生成器的文字。把每个实际动作的完整提示词保存下来；不要只保留模板。身份块从目标参考中提取，不能把其他案例特征留在当前角色上。

## 文字描述生成角色基准图

此模板先用于新建单个角色形象，不是关键帧提示词。基准图生成后，后续所有动作与配套素材改为带同一基准图作为参考；不要在每项素材中重新从文字设计角色。

```text
Use case: stylized-concept.
Asset type: original character identity reference, one character, not a sprite sheet.
User brief: {{user's original character description}}.
Subject: {{character type, silhouette, head/body proportions, colors}}.
Identity details: {{specified face, ears/horns/tail, markings and accessories}}.
Personality expressed through neutral stance: {{personality}}.
Rendering: {{requested 3D plush/soft-toy material}}, clear soft studio lighting.
Composition: {{front-facing full body or requested framing}}, entire intended
silhouette visible, generous margins around all protrusions, face easy to read.
Background: {{genuine transparent alpha or simple contrasting opaque backdrop}}.
Keep the design suitable for consistent facial and articulated poses later.
No labels, captions, logos, grid, extra characters or unrequested props.
Preserve all specified traits; unspecified choices: {{limited design assumptions}}.
```

只填当前角色实际存在的特征；不要把模板里的耳/角/尾当作必须同时具备。只有参考图或说明需要时才做多视图，单张基准图不自动证明被遮挡部位的设计。

## 身份与网格

```text
Use case: stylized-concept; preserve the supplied character identity.
Asset type: keyframe sheet for an animated chat sticker, not a finished GIF.
Input image(s): {{reference roles and filenames}}.
Identity: reproduce exactly {{observed silhouette, proportions, face markings,
ears/horns/tail, limbs, material, colors and existing accessories}}.
Keep these features unchanged across poses: {{identity invariants}}.
Rendering: {{approved plush/soft-toy material, camera and lighting}}.
Canvas: {{width}} by {{height}} pixels; {{columns}} columns by {{rows}} rows.
Exactly {{frame_count}} complete poses, one per equal-sized cell.
Reading order: {{order}}. Consistent character scale and {{stable body anchor}}.
Keep the entire pose including all protrusions within its cell, with
{{safe margin}} clear padding. {{Grounded baseline or planned jump offsets}}.
Background: genuine transparent alpha; empty outside character silhouettes.
No floor, external cast shadows, glow, painted checkerboard, text, labels,
borders, visible grid, extra limbs or unrequested props.
Action meaning: {{chat meaning}}.
Chronological poses:
{{one explicit pose description per frame}}.
Changes must come from articulated limbs, face and head movement.
Do not duplicate and translate the same static render.
Loop intent: {{forward/backward or start/end match}}.
```

单格尺寸、整图比例与网格应相容。若工具实际不支持要求的尺寸，不把数字换个写法当作成功；记录真实结果并调整生成或合成方案。背景写「true transparent alpha」也可能只得到不透明白底或画上的棋盘格，交付前必须读取实际 alpha；回退做法见 [合成与验证](compositing.md#生成器没有给真实-alpha-时)。

## 动作拆解方法

轻动作可从“起势→蓄势→动作中段→强调→保持→回收”组织少量关键帧，但按情绪修改，不要求每个动作恰好六帧。每帧描述具体关节位置、头部角度、眼眉状态与接地状态。

例如“收到”可以拆为手臂放松、抬到胸前、靠近额头、停留并点头、轻回收、回到起势。角色没有手时改用它实际拥有的可动部位表达，不生成不存在的肢体。单向的点头/落地动作不一定适合倒放；循环方式与帧时长由动作决定。

## 配套三件套

这三项是微信表情上传时要一并提交的配套素材：详情页横幅、表情封面、聊天图标；只出 GIF 不算完成交付。三项都复用同一身份块和原始身份参考，每项独立生成并保存完整提示词。输出尺寸与文件体积从本次平台/项目目标读取，不在模板中固化微信数值（尺寸以提交页面核对为准）。

**详情页横幅**：

```text
Asset type: sticker album detail banner.
Identity reference and invariants: {{same identity block}}.
Landscape composition: {{target aspect ratio}}.
Scene: {{scene related to this series' actual emotions}}.
Opaque colored backdrop, distinguishable from the character and page background.
Keep ears, limbs and other important features safe from edge cropping.
Consistent material and lighting with the stickers.
No text, logos or watermark. No stretching or white/transparent edge bands.
```

**专辑封面**：

```text
Asset type: album cover for {{series}}.
Identity reference and invariants: {{same identity block}}.
One clear front-facing half-body or full-body character in {{representative pose}}.
Composition suited to {{target dimensions}}, ample subject size and safe margins.
Genuine transparent alpha, clean silhouette, no ground or external shadow.
No text, frame, white graphic outline or unrelated decorations.
```

**聊天图标**：

```text
Asset type: small chat-panel icon for {{series}}.
Identity reference and invariants: {{same identity block}}.
One recognizable front-facing head with all distinctive protrusions visible.
Strong readable face at {{actual display dimensions}}.
Rounded complete silhouette, no hard rectangular cut edge.
Genuine transparent alpha; no text, frame, white graphic outline or decorations.
```

艺术家头像/横幅仅在首次资料或本次请求要求时补齐：头像按角色资料构图并明确是角色图，主页横幅按角色/作者整体风格构图，避免混用为系列专辑横幅。参考原图即可锁定身份，不必依赖另一个生成结果来累积形象漂移。
