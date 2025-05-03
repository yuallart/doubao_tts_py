import asyncio
import copy
import gzip
import json
import os
import shutil
import ssl
import uuid
from datetime import datetime
from pathlib import Path

import websockets

from utils import generate_params, parse_response

MESSAGE_TYPES = {
    11: "audio-only server response",
    12: "frontend server response",
    15: "error message from server"}
MESSAGE_TYPE_SPECIFIC_FLAGS = {
    0: "no sequence number",
    1: "sequence number > 0",
    2: "last message from server (seq < 0)",
    3: "sequence number < 0"
}
MESSAGE_SERIALIZATION_METHODS = {
    0: "no serialization",
    1: "JSON",
    15: "custom type"
}
MESSAGE_COMPRESSIONS = {
    0: "no compression",
    1: "gzip",
    15: "custom compression method"
}


class WebSocketTTSClient:
    def __init__(self,
                 appid="",
                 token="",
                 cluster="volcano_tts",
                 voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
                 host="openspeech.bytedance.com",
                 encoding="mp3"
                 ):
        self.appid = appid
        self.token = token
        self.cluster = cluster
        self.voice_type = voice_type
        self.host = host
        self.encoding = encoding
        self.api_url = f"wss://{host}/api/v1/tts/ws_binary"
        # 版本号version: b0001 0x1 (4 bits)
        # 头部长度header size: b0001 0x1 (4 bits)
        # 头部长度message type: b0001 0x1 (Full client request) (4bits)
        # 消息类型特定标志message type specific flags: b0000 0x0 (none) (4bits)
        # 序列化方式message serialization method: b0001 0x1 (JSON) (4 bits)
        # 压缩方式message compression: b0001 0x1 (gzip) (4bits)
        # 保留字段reserved data: 0x00 (1 byte)
        self.default_header = bytearray(b'\x11\x10\x11\x00')
        self.reconnect_attempts = 0
        self.websocket = None

    def deep_update(self, default, override):
        """
        Recursively merge two dictionaries.
        :param default: 原始默认值
        :param override: 要覆盖的值
        :return: merged dictionary
        """
        if isinstance(override, dict) and isinstance(default, dict):
            for key, value in override.items():
                if key in default:
                    default.deep_update(default[key], value)
                else:
                    default[key] = value
            return default
        else:
            return override

    async def connect(self):
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False  # 测试时可关闭主机名验证
        ssl_context.verify_mode = ssl.CERT_NONE  # 测试时跳过证书验证（生产环境需配置）
        header = {"Authorization": f"Bearer;{self.token}"}
        try:
            self.websocket = await websockets.connect(
                self.api_url,
                ssl=ssl_context,
                additional_headers=header,
                ping_interval=None
            )
            self.reconnect_attempts = 0
            print("连接成功")
        except Exception as e:
            print(f"连接失败: {e}")
            await self.handle_reconnect()

    async def query(self, text, file_name, file_path):
        full_client_request = generate_params(self, operation="submit", text=text)
        if not self.websocket:
            await self.connect()
        # 构建完整的文件路径，并解析为绝对路径
        save_dir = Path(__file__).parent / file_path  # 获取目标目录
        save_dir.mkdir(parents=True, exist_ok=True)  # 如果目录不存在，则递归创建
        file_gen_path = (
            Path(__file__).parent / file_path / (file_name + "." + self.encoding)).resolve()
        print(file_gen_path)
        with open(file_gen_path, "wb") as file_to_save:
            await self.websocket.send(full_client_request)
            print("发送消息成功")
            while True:
                try:
                    res = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                    condition = parse_response(self, res, file_to_save)
                    if condition:
                        file_to_save.flush()
                        os.fsync(file_to_save.fileno())
                        break
                except Exception as e:
                    print(f"连接失败: {e}")
                    break

        # 编译器并不是实时监控文件目录的，所以并不会在项目列表中实时刷新，请打开文件管理器手动刷新，以判断有没有生成文件
        print("文件已保存至:", file_gen_path)

    async def handle_reconnect(self):
        """指数退避重连机制"""
        self.reconnect_attempts += 1
        delay = min(2 ** self.reconnect_attempts, 30)  # 最大间隔30秒
        print(f"{delay}秒后尝试重连...")
        await asyncio.sleep(delay)
        await self.connect()

    async def listen(self):
        """持续监听消息"""
        while True:
            try:
                async for message in self.websocket:
                    print(f"收到消息: {message}")
            except websockets.ConnectionClosed:
                print("连接丢失，启动重连...")
                await self.handle_reconnect()

    pass


async def main():
    client = WebSocketTTSClient(
        appid="1323562191",
        token="wp5PV123TlJFDAGRpbTwWS901rp8hbIj",
        cluster="volcano_tts",
        voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
        host="openspeech.bytedance.com",
        encoding="mp3"
    )
    await client.connect()
    await client.query("你好，我是豆包", "test2", "./data")

    # 永久阻塞
    while True:
        await client.listen()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("客户端已手动终止")
