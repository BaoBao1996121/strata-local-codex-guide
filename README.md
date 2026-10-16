# Windows 8GB 显存运行 Strata，并接入 Codex：64K 日常配置实测

测试日期：2026-10-16。硬件：i5-12600KF、64GB 内存、RTX 3060 Ti 8GB，Windows。

这是一份本机配置记录，不是通用速度承诺。日常推荐 **64K 上下文、FP16 KV、20K GPU KV 驻留、512 prefill**。本机约 8K 冷输入后输出 29.6–29.8 token/s，约 61K 冷输入后输出 27.5 token/s。后者首 token 等待约 211 秒：长上下文能放下，不代表能瞬间读完。

## 版本和边界

- 推理项目：[Niko1221/Strata](https://github.com/Niko1221/Strata)，本次 checkout `296b59d2f73c8f04a805df29c2fa97655adace78`。
- 引擎：0.1.44.1，CUDA 13；Python 3.13。
- 模型：[SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF](https://huggingface.co/SC117/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-GGUF/tree/eec4e10a2c29b440a2ae85591fa11569ce752963/IQ2_XS)，IQ2_XS，两个 GGUF 分片，合计约68.47GB。服务模型 ID：`qwen3.8-flash-next-abliterated-iq2_xs`。
- 权重下载时锁定 revision：`eec4e10a2c29b440a2ae85591fa11569ce752963`。两个分片的实际 SHA256 和当时仓库期望值见 [校验记录](strata-weight-sha256.json)。此记录不能代替下载新版本时重新核对来源。
- Codex CLI：`0.162.0-alpha.17.2`。配置和模型目录格式可能随版本变化。
- 这里只测试速度、合成文本检索和基本工具调用，没有测 IQ2_XS 的全面能力，也不能据此说它等于某个闭源模型。
- 当前没有加载视觉编码器，不能识图；保留图片工具入口不等于模型获得视觉能力。

## 安装路线

1. 在有足够空间的 SSD 上克隆 Strata，按仓库的 [安装指南](https://github.com/Niko1221/Strata/blob/296b59d2f73c8f04a805df29c2fa97655adace78/docs/AI_SETUP.md) 检查驱动、内存、Python 和 GPU。Windows 从 `START-HERE.bat --check` 开始。
2. 准备匹配的 GGUF 两个分片、Strata expert pack、tokenizer 和 MTP 文件。**本攻略的 JSON 不是自动安装器**；先按对应版本的 Strata 自定义 GGUF/打包流程完成资源准备，再填写路径。不要拿默认下载的另一种量化代替这次测试模型。
3. 下载大文件可用支持断点续传及 HTTP Range 的下载器，单文件 4–8 连接起步，例如 `aria2c -c -x 8 -s 8 -k 16M "固定版本的下载URL"`。链接必须来自模型仓库；过多连接可能触发限流。
4. 每个分片下载后执行 `Get-FileHash -Algorithm SHA256 -LiteralPath '分片绝对路径'`，逐个比对仓库固定 revision 下的 LFS SHA256。分片分别校验，不能只比文件大小；不应把 ETag 一律当成 SHA256。
5. 复制 [服务配置模板](strata-64k.example.json)，把示例 `D:\LocalAI` 路径换成实际目录。不要整份覆盖另一种模型的配置；尤其核对 pack、native、ple-gguf、MTP 和 tokenizer 是否配套。
6. 在 Strata 目录用 `.venv\Scripts\python.exe serve\server.py --engine strata --config <配置路径> --port 8080` 启动。保持监听 `127.0.0.1`。`/health` 返回 `loaded=true` 和 `max_context=65536` 后才算加载完成。

如果本地路径包含特殊字符造成底层引擎读文件失败，可使用英文目录；同一 NTFS 卷可用硬链接避免额外复制大权重，但应先确认源文件和目标路径。不要删除唯一的权重副本。

已有 GGUF 可先运行 `START-HERE.bat --inspect <分片绝对路径>`，确认架构和量化可读，再用安装器的 `--gguf-dir <分片目录>` 导入。自定义文件名是否自动识别以该版本检查结果为准。底层准备过程见固定版本 `setup.py`：`tools/iq_pack.py --gguf <第一分片> --out <pack目录>`；低内存模式还需同工具的 `--experts-bin` 打包；MTP 依次使用 `mtp_fetch.py`、`mtp_pack.py`、`mtp_rt.py`，并核对下载校验。首次运行需要的临时空间和额外expert文件不包含在68.47GB权重大小里。不要对其他模型已有的pack目录强制覆盖。

## 最终日常参数

```text
--mmap-experts
--expert-cache auto
--max-context 65536
--kv fp16
--kv-resident 20480
--prefill 512
--vram-reserve-mib 1100
--spec 4
--spec-min-p 0.5
```

MTP、expert profile 和模型路径见模板。环境变量 `STRATA_ROUTE_TAIL_SKIP=0`。同一张 8GB 卡运行大型 ComfyUI 工作流前需要协调卸载 LLM；本仓库未实现自动资源调度。

这里没有为了扩展上下文换成 int8 KV。IQ2_XS 是**权重量化**，FP16 是**上下文 KV 缓存格式**，两者不是同一件事。启动时看到 READY 还不够，还要检查可用内存、显存余量，并完成真实请求。

## 各档实测

每档用约 8K 的自建合成输入做两次冷请求，最多输出 256 token；在输入的 10%、50%、90% 放置检索标记。另对实用档做接近上限的输入。temperature=0、seed=42、reasoning_effort=none。完成的请求均通过本次三个标记的检索检查。不同档位为可运行而调整过参数，因此不是严格单变量实验。样本很少。

| 上下文上限 | 约8K输入后的输出速度 token/s | 接近上限输入后的输出速度 | 结论 |
|---|---:|---:|---|
| 32K，原配置 | 28.5 / 26.0 | 28,681 输入：27.6 | 可用 |
| 48K，32K KV 驻留 | 28.8 / 28.1 | 45,061 输入：23.6 | 可用，收益不如最终64K |
| **64K，最终日常配置** | **29.6 / 29.8** | **61,441 输入：27.5** | **推荐** |
| 96K，20K驻留/512 prefill/700 reserve | 26.1 / 29.0 | 未测 | 仅短输入验证 |
| 128K，同上 | 28.9 / 30.9 | 中止 | 长输入时显存接近占满 |
| 192K，同上 | 21.8 / 27.8 | 未测 | 速度及资源余量变差 |
| 256K，同上 | 21.9 / 26.2 | 未测 | 可用内存跌至约1.9GiB，停止 |

64K 最终配置的 61,441-token 请求：冷首 token 211.460 秒，总耗时 220.730 秒，输出256 token；结束时显存约7502MiB，可用内存约7629MiB。32K 接近上限请求冷首 token 107.645 秒，48K 为160.526秒。后续有前缀缓存的会话可能不同，不能直接拿冷输入等待时间当每轮等待时间。

128K 长输入请求在预填充期间观察到显存约8106.8MiB/8192MiB，按“跳过明显不适合日常的档位”停止。不能将短输入成功说成128K满上下文已验证，更不能把256K当作本机稳定日常档。

原始文件 [context-ladder-results.json](context-ladder-results.json) 只含数值及通过标记，也包含64K中间调参结果。最终配置的记录以 `cap=65536`、`reserve_mib=1100`、`prefill="512"`、`mode="stream20k"` 区分；未保存生成正文。

## 上下文如何换算内存

本模型此次 FP16 主 KV：12层 QSA，合计每 token 24,576 字节（24KiB）。当前实现下可以用：

```text
主KV内存 = token数 × 24,576 字节
64K = 65,536 token → 1.5GiB
96K → 2.25GiB；128K → 3GiB；192K → 4.5GiB；256K → 6GiB
GPU主KV驻留 = 20,480 × 24KiB = 480MiB
```

流式 KV 将主缓存放在锁页内存中，GPU 保留驻留部分。MTP/draft KV、计算缓冲、权重、expert cache、桌面显示仍需额外空间。因此这不是进程总内存/显存公式。显存可能一直很满，因为自动 expert cache 会利用余量。

token不是字节，也不是固定数量的中文字。应先经过对应tokenizer计数。上述系数只适用于本模型及此次FP16实现，不应套到所有模型。Strata安装脚本中的约13,728字节/token估算针对int8及draft口径，不能混用。

## 接入 Codex

[local-codex.config.toml](local-codex.config.toml) 将 provider 指向本地 Responses API。已验证合成文件读取、工作流 JSON 修改，以及 Python urllib 的 HTTPS 请求。它不是完整的 Codex 所有功能兼容性认证。

默认上下文65536，自动压缩触发49152，工具单次输出限制2048。早期精简配置初始工具/指令开销曾测得约6138 token；加入模型目录后的本次工具测试单轮前缀约6.9K，距压缩阈值约有42K token可容纳任务输入、对话和工具结果；还留16K名义余量给压缩、回复等。实际开销随任务目录、AGENTS和版本变化，不能保证恒定。

保留shell、文件读写、HTTP联网；关闭浏览器控制、应用连接器、图片生成和大量技能发现。联网通过本地shell，不依赖OpenAI托管搜索。Windows沙箱下系统curl/PowerShell可能遇到Schannel凭据错误，可用安装环境的Python urllib，保持TLS校验。

### 推荐入口：不保存会话的本地任务启动器

安装Codex CLI并确保 `codex` 在PATH、Python3.11以上可用，然后双击 [Start-Local-Codex.bat](Start-Local-Codex.bat)。先启动Strata。选择64K日常或32K较早压缩，再输入工作目录和任务。

启动器使用隔离的临时CODEX_HOME和 `codex exec --ephemeral`，正常退出后清理临时目录；不会更改现有云端默认模型。32K选项只收紧Codex客户端上下文和压缩阈值，**服务仍保持64K，不能据此期待显存下降，也不是重新测过的32K引擎配置**。异常断电/强制结束可能留下临时目录，需要另行清理。

### 模型下拉菜单的实际状态

[strata-models.json](strata-models.json) 是为本次Codex版本准备的单模型目录。隔离app-server的 `model/list` 已正确返回 `Qwen3.8 IQ2_XS - Local 64K`；带此目录的临时Codex任务也通过了合成文件读取测试，不再提示缺少模型metadata。加载配置时使用 `model_catalog_json` 的绝对路径；provider也必须同时选择strata。目录本身不负责跨provider路由。

这证明后端识别该条目，**尚未证明当前桌面UI可以和云端模型在同一下拉菜单无缝切换**。没有替换用户全局模型目录，也没有重启桌面应用。独立profile可以用CLI的 `--profile` 选择，但不能当成已验证的桌面菜单入口。

桌面会话有保存记录的机制，`history.persistence=none` 不等于关闭所有会话存储。需要不保存回答时应使用上面的临时exec启动器，不要仅因为配置了history=none就直接用于敏感桌面聊天。

官方参考：[配置](https://learn.chatgpt.com/docs/config-file/config-reference)、[Profile](https://learn.chatgpt.com/docs/config-file/config-advanced)、[自定义模型目录](https://learn.chatgpt.com/docs/enterprise/roll-out-a-gateway)。

## 隐私、验证及回退

- 服务配置为 `log=null`、`api_monitor=false`；不要将服务器标准输出重定向到永久日志。浏览器历史聊天另有存储，需独立关闭/清理；本机曾修改网页存储逻辑，本模板不自动修改上游网页。
- 本仓库不包含真实会话、生成正文、密钥、用户工作流、权重或私人绝对路径。模型推理本地化不等于联网工具不会访问外网。
- 调参前备份原服务配置；失败时恢复配置并重启**确认属于本服务**的进程。不要关闭其他GPU任务来掩盖资源冲突。
- `--prefill auto` 的上限8192，显式写8192并没有真正缩小默认上限；本次真正有效的是512。
- 48K FP16全显存、以及部分32K驻留的大上下文配置曾出现expert cache无可用槽。最终采用20K驻留；不要只提高max-context。
- 自动压缩行为和复杂多轮ComfyUI自动执行仍需后续验证；不要将基本文件编辑测试夸大成完整工作流代理已交付。

攻略只记录这次实际结果。换显卡、引擎、量化、桌面负载后，应重新做短请求和接近目标输入长度的验证。
