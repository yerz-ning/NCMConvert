# NCMConvert

## 软件介绍

NCMConvert 用来把网易云音乐客户端下载的 `.ncm` 加密文件还原成可直接播放的音频文件，并把专辑封面内嵌进音频文件自身的标签中。全部处理在本机完成，不访问网络。

主要特点：

- 图形界面操作，输入输出路径全部用系统文件选择器指定，不需要手输路径
- 单个文件或整个文件夹（含子目录）都能处理
- 输出文件名取元数据里的「歌名 - 歌手」，扩展名跟随元数据中的格式（mp3、flac 等）
- 封面内嵌进音频标签：MP3 写入 ID3v2 的 APIC 帧，FLAC 写入 PICTURE 块
- 批量处理时单个文件失败不会中断整体任务，处理结束给出成功与失败统计
- 单文件可执行程序，运行时不需要 Python 环境
- 音频按 64 KB 分块流式解密，可处理数百 MB 的大文件而内存占用保持平稳
- 只依赖 Python 标准库，无第三方运行时依赖，Windows 与 Linux 通用

---

## 下载与快速使用

使用无需配置 Python 环境或自行编译，请直接前往本仓库右侧的 **[Releases](https://github.com/yerz-ning/NCMConvert/releases)** 页面：

1. 下载最新版本的 `NCMConvert.exe` 文件。
2. 双击直接运行即可（发行版已内置完整解密功能）。
3. 选择你的 NCM 文件或文件夹，点击“开始解密”即可。

**注意**：如果你选择克隆源码自行编译，因为版权原因，源码中移除了解密密钥，你需要自行配置密钥后才能使用（详见下方“关于密钥”）。

---

## 系统要求

- Windows 7 及以上
- 图形界面需要系统已安装 tcl/tk（Windows 官方 Python 安装包默认包含，Linux 需安装 `python3-tk`）
- 很抱歉，目前 Releases 中仅提供了 Windows(x86-64) 版本的编译产物，其他系统/架构请自行编译，。

## 项目结构

```text
NCMConvert/
  README.md               项目说明
  requirements.txt        依赖说明
  .gitignore
  src/                    源代码
    main.py               启动入口
    core/                 业务层：NCM 解析与解密
      constants.py        常量：掩码、前缀、标签结构、默认配置
      errors.py           统一异常类型
      crypto.py           AES-128-ECB 解密、RC4 变体密钥流、流式异或
      parser.py           NCM 容器结构解析、封面格式判定
      tagger.py           封面写入 ID3v2 标签与 FLAC PICTURE 块
      meta.py             密钥材料与元数据的解码
      naming.py           输出文件名生成与非法字符过滤
      decryptor.py        单文件解密、目录收集、批量任务编排
      settings.py         用户配置读写
    ui/                   界面层
      app.py              主窗口
      dialogs.py          关于、设置对话框
    utils/                基础层
      system.py           打开链接、打开目录、错误提示
  tests/                  单元测试
    test_crypto.py        AES 与密钥流测试
    test_parser.py        容器解析测试
    test_meta.py          载荷解码测试
    test_naming.py        文件命名测试
    test_decryptor.py     端到端解密与批量流程测试
    test_tagger.py        封面内嵌与标签读写测试
    aes_ref.py            测试用参考实现（标准 AES 查表版本）
    sample.py             测试用 NCM 样本构造工具
  docs/                   文档
    ARCHITECTURE.md       架构与模块说明
  scripts/                构建脚本
    build.py              打包单文件程序
```

架构与模块划分见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 使用说明

Windows 请直接双击 `NCMConvert.exe` 打开程序。

如果选择从源码运行：

```bash
python src/main.py
```

界面从上到下分四个区域：

1. 输入区：「选择 NCM 文件」选择一个 `.ncm` 文件，「选择文件夹」选择一个文件夹并递归收集其中所有 `.ncm`
2. 输出区：「输出到源目录」勾选时解密结果写在各自的 NCM 文件旁边；取消勾选后可用「选择输出文件夹」指定统一目录
3. 文件列表：显示待处理的全部文件，以及每个文件的状态（等待 / 处理中 / 成功 / 失败）和输出位置
4. 控制区与日志：「开始解密」「停止」「打开输出目录」按钮，进度条与状态栏，以及逐条显示处理过程的运行日志（成功为绿色，失败为红色，失败信息含文件路径与具体原因）

### 菜单

- 文件：设置、打开输出目录、退出
- 帮助：关于 NCMConvert、项目仓库

### 设置项

配置保存在 `%APPDATA%\NCMConvert\settings.json`（Linux 为 `~/.config/NCMConvert/settings.json`）。

- 将封面内嵌到音频文件的标签中：开启时把封面写进音频标签（MP3 为 ID3v2 的 APIC 帧，FLAC 为 PICTURE 块）；关闭则丢弃封面，只输出音频
- 导出元数据 JSON：预留项，暂不影响处理流程
- 跳过输出目录中已存在的同名文件：预留项，暂不影响处理流程

「恢复默认」可把三项还原为初始值。

### 输出规则

- 主体名：元数据的歌名 + ` - ` + 歌手，多位歌手用顿号连接
- 元数据缺失时回退使用输入文件的原文件名
- 扩展名取元数据的 `format` 字段，无元数据时默认 `mp3`
- 文件名中的 Windows 保留字符 `<>:"/\|?*` 与控制字符会被替换为下划线，并规避 CON、PRN、NUL、COM1-9、LPT1-9 等保留设备名
- 输出与输入路径相同时自动追加 `_decoded`，不覆盖源文件
- 封面不单独生成图片文件，而是写进音频文件自身的标签，由播放器读取显示
- 音频格式不是 mp3 / flac 时无法写入标签，此时保留音频、丢弃封面，并在日志中说明原因

### 关于密钥

本仓库源码不包含任何真实解密密钥，运行所需的相关信息因版权原因不在此公开。

## 运行测试

```bash
python -m unittest discover -s tests -t .
```

测试用例通过构造样本验证解析与解密实现，覆盖 AES 标准测试向量、密钥流周期性、容器解析、元数据兼容、文件名过滤、标签读写与端到端解密。

## 自行打包

项目提供了打包脚本，会调用 PyInstaller 生成单文件程序，中间产物放在系统临时目录，不污染工程目录：

```bash
pip install -r requirements.txt
python scripts/build.py
```

等价的 PyInstaller 命令（Linux 下把 `--noconsole` 保留即可，产物为无扩展名的可执行文件）：

```bash
pyinstaller --onefile --noconsole --clean --name NCMConvert --paths . src/main.py
```

Linux 需先安装 tcl/tk：

```bash
sudo apt install python3-tk
chmod +x NCMConvert
```

PyInstaller 不支持跨平台打包，Linux 的可执行文件需要在 Linux 上生成。

## 常见问题

- 双击没反应：确认使用的是打包好的 `NCMConvert.exe`；若运行源码，需已安装 tkinter
- 提示无法加载 tkinter：重新安装 Python 并勾选 tcl/tk 组件，Linux 下安装 `python3-tk`
- 提示元数据校验失败：文件可能不是标准 NCM 文件，或下载过程中被损坏
- 播放器里看不到封面：即便封面已写入音频标签，也需要播放器支持读取内嵌封面（如 VLC）；不支持标签读取的播放器不会显示

## 协议

本项目以 GNU General Public License v3.0 发布，全文见 **[LICENSE](https://github.com/yerz-ning/NCMConvert/blob/main/LICENSE)**。

请仅对你自己合法获取的音乐文件使用本工具，严禁用于传播受版权保护的内容。