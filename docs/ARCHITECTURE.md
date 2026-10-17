# 架构说明

## 分层

项目按「界面层 / 业务层 / 基础层」三层组织，依赖方向自上而下，不允许反向依赖。

```
src/main.py            进程入口：环境检查、异常兜底、启动主窗口
src/ui/                界面层：只负责展示与交互，不包含任何解码算法
src/core/              业务层：NCM 解析与解密，不依赖任何界面代码
src/utils/             基础层：与业务无关的系统能力
tests/                 单元测试与测试用样本构造工具
```

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `src/core/constants.py` | 常量：掩码、前缀、标签结构、默认配置 |
| `src/core/errors.py` | 统一异常类型 `NcmError`，界面层据此把可读错误呈现给用户 |
| `src/core/crypto.py` | 密码学原语：AES-128-ECB 解密、RC4 变体 S-Box 与密钥流、按块流式异或 |
| `src/core/parser.py` | NCM 容器结构解析：魔数校验、各段长度与内容读取、封面图片格式判定 |
| `src/core/meta.py` | 段内载荷解码：密钥材料解码、元数据解码与 JSON 字段兼容处理 |
| `src/core/naming.py` | 输出文件名生成：非法字符过滤、保留设备名规避、长度限制、扩展名规范化 |
| `src/core/decryptor.py` | 业务编排：单文件解密、目录递归收集、批量任务与进度回调 |
| `src/core/tagger.py` | 封面内嵌：ID3v2 标签解析与 APIC 帧构造、FLAC PICTURE 块插入与替换、图片尺寸解析 |
| `src/core/settings.py` | 用户配置读写，落在用户配置目录 |
| `src/ui/app.py` | 主窗口：路径选择、文件列表、进度、日志、任务线程与事件泵 |
| `src/ui/dialogs.py` | 对话框：关于、设置 |
| `src/utils/system.py` | 打开链接、打开目录、致命错误提示 |
| `src/main.py` | 启动入口，保证源码运行与打包运行两种方式的导入路径都正确 |

## 数据流

```
用户选择路径
   -> ui/app.py 调用 collect_inputs() 递归收集 .ncm
   -> 线程中调用 process_files()
        -> 逐个文件调用 decrypt_file()
             -> parser.parse_header()    读出三个段
             -> meta.decode_key_material 得到 RC4 密钥材料
             -> meta.decode_meta         得到格式、歌名、歌手
             -> crypto.decrypt_audio_stream 流式写出音频
             -> naming 生成输出文件名
             -> tagger.embed_cover        把封面写入音频文件标签
        -> 每个文件通过回调把结果投递到队列
   -> 主线程 ui/app.py 轮询队列，刷新表格、进度条与日志
```

界面与任务线程之间只通过 `queue.Queue` 传递消息，不共享可变状态，避免线程安全问题。

## 关键约束

- 只使用标准库，不引入任何第三方运行时依赖，便于单文件打包与离线使用。
- 音频按 64 KB 分块流式解密，密钥流按音频全局偏移计算，因此分块大小不影响解密结果，内存占用与文件大小无关。
- 所有 S-Box 索引都显式与 `0xFF` 做与运算，避免越界。
- 可恢复错误一律抛 `NcmError`，不使用 `panic` 式的中断；单文件失败不影响批量任务里的其他文件。
- 封面以内嵌方式写入音频标签（MP3 的 ID3v2 APIC 帧、FLAC 的 PICTURE 块），不产生额外的图片文件。
- 写标签采用「同目录临时文件 + 原子替换」，失败时清理临时文件，不破坏已解密好的音频。

## 扩展方式

- 增加新的元数据字段：在 `src/core/meta.py` 的 `decode_meta` 返回值中补充，界面日志按需展示。
- 支持新的输出格式：`naming.normalize_ext` 已按元数据 `format` 字段透传，无需额外改动。
- 调整界面：界面层不参与解密，新增控件或改为其他 GUI 框架时业务层无需变更。
- 增加校验：在 `tests/` 下新增用例即可，测试通过构造符合规范的样本验证实现，不依赖真实音乐文件。
