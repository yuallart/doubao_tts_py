import asyncio
import copy
import gzip
import json
import ssl
import uuid
from datetime import datetime
import websockets

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
    def __init__(
            self,
            appid="1371562691",
            token="wp5PV1P1TlJFDAGRpbTwSw901rp8hbIj",
            cluster="volcano_tts",
            voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
            host="openspeech.bytedance.com"):
        self.appid = appid
        self.token = token
        self.cluster = cluster
        self.voice_type = voice_type
        self.host = host
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
        self.request_json = {
            "app": {
                "appid": appid,
                "token": token,
                "cluster": cluster
            },
            "user": {
                "uid": "qq_bot"
            },
            "audio": {
                "voice_type": "xxx",
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": "uuid",
                "text": "字节跳动语音合成。",
                "text_type": "plain",
                "operation": "query"
            }
        }

    def _generate_params(self, operation="submit", text=""):
        submit_request_json = copy.deepcopy(self.request_json)
        submit_request_json["audio"]["voice_type"] = self.voice_type
        submit_request_json["request"]["reqid"] = str(uuid.uuid4())
        submit_request_json["request"]["operation"] = operation
        submit_request_json["request"]["text"] = text
        payload_bytes = str.encode(json.dumps(submit_request_json))
        payload_bytes = gzip.compress(payload_bytes)  # if no compression, comment this line
        full_client_request = bytearray(self.default_header)
        full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
        full_client_request.extend(payload_bytes)  # payload
        print("\n------------------------ test '{}' -------------------------".format(operation))
        print("request json: ", submit_request_json)
        print("\nrequest bytes: ", full_client_request)
        return full_client_request

    def parse_response(self, res, file):
        print("--------------------------- response ---------------------------")
        # print(f"response raw bytes: {res}")
        protocol_version = res[0] >> 4
        header_size = res[0] & 0x0f
        message_type = res[1] >> 4
        message_type_specific_flags = res[1] & 0x0f
        serialization_method = res[2] >> 4
        message_compression = res[2] & 0x0f
        reserved = res[3]
        header_extensions = res[4:header_size * 4]
        payload = res[header_size * 4:]
        print(f"            Protocol version: {protocol_version:#x} - version {protocol_version}")
        print(f"                 Header size: {header_size:#x} - {header_size * 4} bytes ")
        print(f"                Message type: {message_type:#x} - {MESSAGE_TYPES[message_type]}")
        print(
            f" Message type specific flags: {message_type_specific_flags:#x} - {MESSAGE_TYPE_SPECIFIC_FLAGS[message_type_specific_flags]}")
        print(
            f"Message serialization method: {serialization_method:#x} - {MESSAGE_SERIALIZATION_METHODS[serialization_method]}")
        print(f"         Message compression: {message_compression:#x} - {MESSAGE_COMPRESSIONS[message_compression]}")
        print(f"                    Reserved: {reserved:#04x}")
        if header_size != 1:
            print(f"           Header extensions: {header_extensions}")
        if message_type == 0xb:  # audio-only server response
            if message_type_specific_flags == 0:  # no sequence number as ACK
                print("                Payload size: 0")
                return False
            else:
                sequence_number = int.from_bytes(payload[:4], "big", signed=True)
                payload_size = int.from_bytes(payload[4:8], "big", signed=False)
                payload = payload[8:]
                print(f"             Sequence number: {sequence_number}")
                print(f"                Payload size: {payload_size} bytes")
            file.write(payload)
            if sequence_number < 0:
                return True
            else:
                return False
        elif message_type == 0xf:
            code = int.from_bytes(payload[:4], "big", signed=False)
            msg_size = int.from_bytes(payload[4:8], "big", signed=False)
            error_msg = payload[8:]
            if message_compression == 1:
                error_msg = gzip.decompress(error_msg)
            error_msg = str(error_msg, "utf-8")
            print(f"          Error message code: {code}")
            print(f"          Error message size: {msg_size} bytes")
            print(f"               Error message: {error_msg}")
            return True
        elif message_type == 0xc:
            msg_size = int.from_bytes(payload[:4], "big", signed=False)
            payload = payload[4:]
            if message_compression == 1:
                payload = gzip.decompress(payload)
            print(f"            Frontend message: {payload}")
        else:
            print("undefined message type!")
            return True

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

    async def query(self, text, file_path):
        full_client_request = self._generate_params(operation="query", text=text)
        file_to_save = open(file_path, "wb")
        """发送结构化JSON数据"""
        if not self.websocket:
            await self.connect()
        try:
            await self.websocket.send(full_client_request)
            res = await self.websocket.recv()
            self.parse_response(res, file_to_save)
            print("\nclosing the connection...")
        except websockets.ConnectionClosed:
            await self.handle_reconnect()

    async def handle_reconnect(self):
        """指数退避重连机制"""
        self.reconnect_attempts += 1
        delay = min(2 ** self.reconnect_attempts, 30)  # 最大间隔30秒
        print(f"{delay}秒后尝试重连...")
        await asyncio.sleep(delay)
        await self.connect()
        pass


if __name__ == '__main__':
    client = WebSocketTTSClient(
        appid="1371562691",
        token="wp5PV1P1TlJFDAGRpbTwSw901rp8hbIj",
        cluster="volcano_tts",
        voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
        host="openspeech.bytedance.com"
    )
    asyncio.run(client.submit("你好，我是豆包", "test_submit1.mp3"))
