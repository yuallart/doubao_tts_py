# doubao_tts_py

## 简介
本项目是一个火山引擎大模型语言合成API的封装库，用于与字节跳动开放平台的语音合成服务进行交互。
通过火山大模型的API，可以将文本转换为语音文件，并支持实时监听语音合成过程。

## 功能特点
- 支持WebSocket连接，实现与语音合成服务的实时通信
- 提供简单的API接口，方便集成到其他应用中
- 支持指数退避重连机制，提高连接稳定性
- 生成的语音文件可以保存到指定路径

## 技术栈
- Python 3.7+
- Websockets
- Asyncio库
- 字节跳动开放平台语音合成API

## 第三方库介绍

| 库名称       | 版本   | 简介                                                                 |
|--------------|--------|----------------------------------------------------------------------|
| Websockets   | 15.0.1 | 用于处理WebSocket协议的库，支持异步通信。                            |
| Asyncio      | 内置   | Python的异步I/O库，用于实现高并发的异步任务。                        |
| Requests     | 最新   | 用于发送HTTP请求，获取Open Key等信息。                               |

## 安装与运行

### 1. 环境准备
确保已安装Python 3.7或更高版本，并安装项目依赖：

```bash
pip install -r requirements.txt
```

### 2. 运行程序（websocket）

```bash
python tts_http.py
```

### 3. 运行程序（http）

```bash
python tts_websocket.py
```

## 相关
[字节跳动开放平台](https://open.bytedance.com/)

[豆包大模型语音生成TTS文档](https://www.volcengine.com/docs/6561/1257584)
