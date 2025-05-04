import asyncio
import gzip
import json
import os
import ssl

import websockets

from tts_config import generate_params, print_text, generate_dir, parse_response


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

    def generate_websocket_params(
        self,
        operation="submit",
        text="",
    ):
        submit_request_json = generate_params(self, operation=operation, text=text)
        payload_bytes = str.encode(json.dumps(submit_request_json))
        payload_bytes = gzip.compress(payload_bytes)  # if no compression, comment this line
        full_client_request = bytearray(self.default_header)
        full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
        full_client_request.extend(payload_bytes)  # payload
        print("\n------------------------ test '{}' -------------------------".format(operation))
        print_text("request json: ", submit_request_json)
        print_text("request bytes: ", full_client_request)
        return full_client_request

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
            print("连接成功...")
        except Exception as e:
            print(f"连接失败: {e}")
            await self.handle_reconnect()

    async def query(self, text, file_name, file_path):
        full_client_request = self.generate_websocket_params(operation="submit", text=text)
        if not self.websocket:
            await self.connect()
        # 构建完整的文件路径，并解析为绝对路径
        file_gen_path = generate_dir(file_name, file_path, self.encoding)
        print("Downloads: ", file_gen_path)
        with open(file_gen_path, "wb") as file_to_save:
            await self.websocket.send(full_client_request)
            print("发送消息成功: ")
            while True:
                try:
                    res = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                    condition = parse_response(res, file_to_save)
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
    # 仅为示例，非真实 token，请前往火山引擎官网申请
    client = WebSocketTTSClient(
        appid="1371415591",
        token="wp5PV1P1TlIOIASPskTwSw901ux8hbIj",
        cluster="volcano_tts",
        voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
        host="openspeech.bytedance.com",
        encoding="mp3"
    )
    await client.connect()
    await client.query("你好，我是豆包", "test_websocket", "./data")
    # 永久阻塞
    while True:
        await client.listen()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("客户端已手动终止...")
