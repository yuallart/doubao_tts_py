import copy
import gzip
import json
import uuid
from pathlib import Path

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

request_json = {
    "app": {
        "appid": "",
        "token": "",
        "cluster": "volcano_tts"
    },
    "user": {
        "uid": "qq_bot"
    },
    "audio": {
        "voice_type": "zh_female_meilinvyou_emo_v2_mars_bigtts",
        "encoding": "mp3",
        "speed_ratio": 1.0,
        "volume_ratio": 1.0,
        "pitch_ratio": 1.0,
    },
    "request": {
        "reqid": "",
        "text": "",
        "text_type": "plain",
        "operation": ""
    }
}


def print_text(*args):
    """
    接收任意多个参数，打印字符串或格式化输出字典

    :param args: 可变参数列表，每个参数可以是 str 或 dict
    """
    for arg in args:
        if isinstance(arg, dict):
            # 如果是字典，转为 json 格式并缩进 2 层
            print(json.dumps(arg, ensure_ascii=False, indent=2))
        elif isinstance(arg, str):
            # 如果是字符串，直接打印
            try:
                # 尝试将字符串解析为 JSON 对象（dict 或 list）
                json_obj = json.loads(arg)
                # 如果是字典或列表，格式化输出
                print(json.dumps(json_obj, ensure_ascii=False, indent=2))
            except json.JSONDecodeError:
                # 如果不是 JSON 字符串，直接打印原始内容
                print(arg)
        elif isinstance(arg, bytes):
            # 如果是字节串，尝试将其解码为字符串并打印
            try:
                print(arg.decode('utf-8'))
            except UnicodeDecodeError:
                print(arg)
        else:
            # 其他类型转为字符串打印
            print(str(arg))


def generate_params(
    self,
    text="",
    operation="submit",
    encoding="mp3",
    speed_ratio=1.0,
    volume_ratio=1.0,
    pitch_ratio=1.0,
    override=None
):
    """
    生成请求参数字典，仅当参数有值时覆盖默认值。
    """
    submit_request_json = copy.deepcopy(request_json)

    # 更新 app 字段（必填项）
    submit_request_json["app"].update({
        "appid": self.appid,
        "token": self.token,
        "cluster": self.cluster
    })

    # 更新 request 字段（非空时赋值）
    submit_request_json["request"].update({
        "reqid": str(uuid.uuid4()),
        "operation": operation if operation else submit_request_json["request"]["operation"],
        "text": text if text else submit_request_json["request"]["text"]
    })

    # 定义 audio 字段映射：(传入参数 -> 默认字段名)
    audio_fields = {
        "encoding": encoding,
        "voice_type": self.voice_type,
        "speed_ratio": speed_ratio,
        "volume_ratio": volume_ratio,
        "pitch_ratio": pitch_ratio
    }

    # 自动更新非空值
    for key, value in audio_fields.items():
        if value not in (None, ""):
            submit_request_json["audio"][key] = value

    # 处理 override
    if override and isinstance(override, dict):
        for k, v in override.items():
            if v not in (None, ""):
                submit_request_json["audio"][k] = v

    return submit_request_json

def generate_dir(file_name, file_path, encoding):
    """
        生成文件保存的目录路径。

        参数:
        - file_name: 文件名。
        - file_path: 文件路径。
        - encoding: 文件编码格式。

        返回:
        - 文件生成的完整路径。
    """
    save_dir = Path(__file__).parent / file_path  # 获取目标目录
    save_dir.mkdir(parents=True, exist_ok=True)  # 如果目录不存在，则递归创建
    file_gen_path = (
        Path(__file__).parent / file_path / (file_name + "." + encoding)).resolve()
    return file_gen_path


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
    header_extensions = res[4:header_size*4]
    payload = res[header_size*4:]
    print(f"            Protocol version: {protocol_version:#x} - version {protocol_version}")
    print(f"                 Header size: {header_size:#x} - {header_size * 4} bytes ")
    print(f"                Message type: {message_type:#x} - {MESSAGE_TYPES[message_type]}")
    print(f" Message type specific flags: {message_type_specific_flags:#x} - {MESSAGE_TYPE_SPECIFIC_FLAGS[message_type_specific_flags]}")
    print(f"Message serialization method: {serialization_method:#x} - {MESSAGE_SERIALIZATION_METHODS[serialization_method]}")
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
