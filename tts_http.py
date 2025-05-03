import asyncio

import aiohttp

from utils import generate_params


class HTTPClient:
    def __init__(self,
                 appid="",
                 token="",
                 cluster="volcano_tts",
                 voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
                 host="openspeech.bytedance.com"):
        self.appid = appid
        self.token = token
        self.cluster = cluster
        self.voice_type = voice_type
        self.host = host
        self.api_url = f"https://{host}/api/v1/tts"
        self.default_header = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }

    async def query(self, text, file_path):
        request_body = generate_params(self, operation="query", text=text)
        async with aiohttp.ClientSession() as session:
            print("request_body:\n", request_body)
            async with session.post(self.api_url, headers=self.default_header,
                                    json=request_body) as response:
                if response.status == 200:
                    data = await response.read()
                    print(data)
                    return True
                else:
                    print(f"请求失败: {await response.text()}")
                    return False


async def main():
    client = HTTPClient(
        appid="1323562191",
        token="wp5PV123TlJFDAGRpbTwWS901rp8hbIj",
        cluster="volcano_tts",
        voice_type="zh_female_meilinvyou_emo_v2_mars_bigtts",
        host="openspeech.bytedance.com",
        encoding="mp3"
    )
    await client.query("你好，我是豆包", "test_http.mp3")


if __name__ == '__main__':
    asyncio.run(main())
