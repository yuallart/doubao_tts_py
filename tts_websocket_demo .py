# coding=utf-8

'''
requires Python 3.6 or later

pip install asyncio
pip install websockets

'''

import asyncio
import numbers

import websockets
import uuid
import json
import gzip
import copy
import ssl

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
appid = "1371562691"
token = "wp5PV1P1TlJFDAGRpbTwSw901rp8hbIj"
cluster = "volcano_tts"
voice_type = "zh_female_meilinvyou_emo_v2_mars_bigtts"
host = "openspeech.bytedance.com"
api_url = f"wss://{host}/api/v1/tts/ws_binary"

default_header = bytearray(b'\x11\x10\x11\x00')

request_json = {
    "app": {
        "appid": appid,
        "token": token,
        "cluster": cluster
    },
    "user": {
        "uid": "388808087185088"
    },
    "audio": {
        "voice_type": "xxx",
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
        "pitch_ratio": 1.0,
    },
    "request": {
        "reqid": "xxx",
        "text": "字节跳动语音合成。",
        "text_type": "plain",
        "operation": "xxx"
    }
}


def generate_params():
    submit_request_json = copy.deepcopy(request_json)
    submit_request_json["audio"]["voice_type"] = voice_type
    submit_request_json["request"]["reqid"] = str(uuid.uuid4())
    submit_request_json["request"]["operation"] = "submit"
    payload_bytes = str.encode(json.dumps(submit_request_json))
    payload_bytes = gzip.compress(payload_bytes)  # if no compression, comment this line
    full_client_request = bytearray(default_header)
    full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
    full_client_request.extend(payload_bytes)  # payload
    print("\n------------------------ test 'submit' -------------------------")
    print("request json: ", submit_request_json)
    print("\nrequest bytes: ", full_client_request)
    return submit_request_json


async def test_submit():
    full_client_request = generate_params()
    file_to_save = open("test_submit.mp3", "wb")
    header = {"Authorization": f"Bearer;{token}"}
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False  # 测试时可关闭主机名验证
    ssl_context.verify_mode = ssl.CERT_NONE  # 测试时跳过证书验证（生产环境需配置）
    try:
        async with websockets.connect(
                api_url,
                ssl=ssl_context,
                additional_headers=header,
                ping_interval=None
        ) as websocket:
            # 发送初始消息
            await websocket.send(full_client_request)
            while True:
                res = await websocket.recv()
                done = parse_response(res, file_to_save)
                if done:
                    file_to_save.close()
                    break
            # 持续接收消息
            while True:
                response = await websocket.recv()
                print(f"收到响应: {response}")
    except websockets.exceptions.ConnectionClosed as e:
        print(f"连接异常关闭: {e.code} - {e.reason}")
    except Exception as e:
        print(f"发生错误: {e}")
        print("\nclosing the connection...")


def parse_response(res, file):
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


if __name__ == '__main__':
    asyncio.run(test_submit())
