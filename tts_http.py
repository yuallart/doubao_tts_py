import asyncio
import base64
import json

import aiohttp

from tts_config import print_text, generate_dir, generate_params


class HTTPClient:
    def __init__(
        self,
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
        self.api_url = f"https://{host}/api/v1/tts"
        self.default_header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer;{token}"
        }
        self.encoding = encoding

    """
    将 base64 字符串保存为 MP3 文件

    :param file_name:
    :param file_path:
    :param base64_str: 包含或不包含 data URI 前缀的 base64 字符串
    :param output_file: 输出的 MP3 文件路径（例如："output.mp3"）
    """
    def save_base64_to_mp3(self, base64_str: str, file_path: str, file_name: str):

        file_gen_path = generate_dir(file_name, file_path, self.encoding)
        # 去除可能存在的 data URI 前缀
        if base64_str.startswith("data:"):
            base64_str = base64_str.split(",", 1)[1]
        # 解码 base64 数据
        audio_data = base64.b64decode(base64_str)
        # 写入文件
        with open(file_gen_path, "wb") as f:
            f.write(audio_data)
        print(f"音频文件已保存至: {file_gen_path}")

    async def query(self, text, file_name, file_path=""):
        if file_name is None and file_path is None:
            print("file_name and file_path cannot be None at the same time.")
            return False
        request_body = generate_params(self, operation="query", text=text)
        async with aiohttp.ClientSession() as session:
            print_text("request:", request_body)
            async with session.post(
                self.api_url,
                headers=self.default_header,
                json=request_body
            ) as response:
                if response.status == 200:
                    data: bytes = await response.read()
                    data_dict: dict = json.loads(data)
                    print_text("response:", json)
                    self.save_base64_to_mp3(data_dict["data"], file_path, file_name)
                    return True
                else:
                    print(f"请求失败: {await response.text()}")
                    return False


async def main():
    # 仅为示例，非真实 token，请前往火山引擎官网申请
    client = HTTPClient(
        appid="1371415591",
        token="wp5PV1P1TlIOIASPskTwSw901ux8hbIj",
        cluster="volcano_tts",
        voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
        host="openspeech.bytedance.com",
        encoding="mp3"
    )
    await client.query("你好，我是豆包", "test_http", "./data")


if __name__ == '__main__':
    asyncio.run(main())
