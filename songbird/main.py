import asyncio
import base64
import io
import random
import time
from typing import Union, List
import aiohttp
import discord
import pedalboard
import pydub
from pedalboard_native.io import AudioFile


class SongBirdError(Exception):
    pass


class Node:
    def __init__(self, host, region, auth):
        self.host = host
        self.region = region
        self.auth = auth

    async def connect(self):
        headers = {} if self.auth is None else {"Authorization": self.auth}
        session = aiohttp.ClientSession(base_url=self.host, headers=headers)
        ws = await session.ws_connect(f"/voice")
        return session, ws

    async def status(self):
        try:
            return (await req_get(self.host, "/status", self.auth, 3))["players"], self
        except BaseException as e:
            return


async def req_get(host, path, auth, timeout=60):
    headers = {} if auth is None else {"Authorization": auth}
    async with aiohttp.ClientSession(base_url=host, headers=headers) as s:
        async with s.get(path, timeout=timeout) as r:
            return await r.json()


# noinspection PyMethodMayBeStatic
class NodeManager:
    DEFAULT_REGIONS_BY_RTC = {
        'asia': ('hongkong', 'singapore', 'sydney', 'japan', 'india'),
        'eu': ('rotterdam', 'russia', 'southafrica'),
        'us': ('us-central', 'us-east', 'us-south', 'us-west', 'brazil')
    }

    DEFAULT_REGIONS = {
        'asia': ('Oceania', 'Asia'),
        'eu': ('Africa', 'Europe'),
        'us': ('North America', 'South America', 'Antarctic')
    }

    NODE = {
        'asia': [],
        'eu': [],
        'us': []
    }

    UNKNOWN_NODE = []

    def check_region(self, region):
        for k, v in self.DEFAULT_REGIONS.items():
            if region in v:
                return k

    async def add_nodes(self, *args):
        if not self._is_started:
            asyncio.create_task(self._start())
        for i, v in args:
            try:
                out = await req_get(i, "/region", v)
            except BaseException as e:
                print(e)
                self.UNKNOWN_NODE.append((i, v))
                continue
            region = self.check_region(out["continent"])
            node_class = Node(i, region, v)
            self.NODE[region].append(node_class)

    def get_all_nodes(self):
        return [v2 for i in self.NODE.values() for v2 in i]

    async def get_all_nodes_status(self, nodes: List[Node]):
        out_status = await asyncio.gather(*[i.status() for i in nodes])
        ok_host = [i for i in out_status if i is not None]
        return ok_host

    async def get_best_node(self, region=None):
        await self.check_node()
        all_nodes = None
        if region is not None:
            for k, v in self.DEFAULT_REGIONS_BY_RTC.items():
                if region not in v:
                    continue
                if len(self.NODE[k]) > 0:
                    all_nodes = self.NODE[k]
                break
        if all_nodes is None:
            all_nodes = self.get_all_nodes()
        out = await self.get_all_nodes_status(all_nodes)
        if len(out) == 0:
            raise SongBirdError("ALL NODES IS DOWN")
        best_out = min(out, key=lambda p: p[0] + random.random())
        return best_out[1]

    def __init__(self):
        self._is_started = False
        pass

    async def check_node(self):
        if self.UNKNOWN_NODE:
            cache_list = self.UNKNOWN_NODE.copy()
            self.UNKNOWN_NODE.clear()
            await self.add_nodes(*cache_list)

    async def _start(self):
        self._is_started = True
        while True:
            await self.check_node()
            await asyncio.sleep(300)


def empty_audio(*, ms, samplerate=48000, num_channels=2):
    import numpy
    sec = ms / 1000
    data = numpy.zeros((num_channels, int(samplerate * sec)), dtype=numpy.float32)
    return data


class VoiceClientModel(discord.VoiceClient):
    audio_list = {}
    khown_ssrc = {}
    decode_mode = False
    node = None
    callback = None
    volume = 100
    ready = asyncio.Event()
    connected = asyncio.Event()
    session = None
    ws = None
    _is_paused = False

    def __init__(self, node_manager_key: str, client: discord.Client,
                 channel: Union[discord.channel.VoiceChannel, discord.abc.Connectable]):
        self.node_manager: NodeManager = getattr(client, node_manager_key, None)
        if type(self.node_manager) is not NodeManager:
            raise SongBirdError(f"{type(self.node_manager).__name__} is not NodeManager")
        self.client = client
        self.channel = channel

    def is_paused(self):
        return self._is_paused

    async def on_voice_state_update(self, data: dict) -> None:
        await self.ready.wait()
        if self.ws is None:
            return
        await self.ws.send_json({
            "t": "VOICE_STATE_UPDATE",
            "d": data
        })

    async def on_voice_server_update(self, data: dict) -> None:
        await self.ready.wait()
        if self.ws is None:
            return
        await self.ws.send_json({
            "t": "VOICE_SERVER_UPDATE",
            "d": data
        })

    async def heartbeat(self):
        while True:
            await asyncio.sleep(30)
            if not self.ws.closed:
                await self.ws.send_json({
                    "t": "PING"
                })
            else:
                break

    def sync_flush_all(self):
        list_voice = []
        data_all = self.audio_list.copy().items()
        for k, v in data_all:
            data = io.BytesIO()
            with AudioFile(data, "w", samplerate=48000, num_channels=2, format="wav") as fs:
                start_time = None
                last_time = False
                for i in v:
                    if start_time is None:
                        start_time = i["got_at"]
                    sem = i["data"]
                    sem.seek(0)
                    with AudioFile(sem, "r") as f_sem:
                        d = f_sem.duration * 1000
                        if i["got_at"] - int(last_time) - int(d) > 30 and last_time is not False:
                            fs.write(empty_audio(ms=int(i["got_at"] - last_time - d)))
                        fs.write(f_sem.read(f_sem.samplerate * f_sem.frames))
                        last_time = i["got_at"]
            list_voice.append({"start_time": start_time, "data": pydub.AudioSegment.from_file(data, format="wav"),
                               "last_time": last_time})
        if len(list_voice) == 0:
            return None
        min_time = min(list_voice, key=lambda x: x["start_time"])
        max_time = min(list_voice, key=lambda x: x["last_time"])
        list_voice.remove(min_time)
        min_time["data"] = min_time["data"] + pydub.AudioSegment.silent(
            duration=(max_time["last_time"] - min_time["last_time"]))
        for i in list_voice:
            min_time["data"] = min_time["data"].overlay(i["data"], i["start_time"] - min_time["start_time"])
        return min_time["data"]

    async def flush_all(self):
        return await asyncio.to_thread(self.sync_flush_all)

    async def decode_voice_packet(self, data):
        bytes_data = base64.urlsafe_b64decode(data["data"])
        audio_bytes = io.BytesIO(bytes_data)
        audio_dict = {"data": audio_bytes, "got_at": time.time() * 1000}
        if self.audio_list.get(data['ssrc']):
            self.audio_list[data['ssrc']].append(audio_dict)
        else:
            self.audio_list[data['ssrc']] = [audio_dict]

    async def ws_read(self):
        async for i in self.ws:
            if i.type == aiohttp.WSMsgType.TEXT:
                data = i.json()
                if data['t'] == "CONNECTED":
                    self.connected.set()
                elif data['t'] == "STOP" and self.callback is not None:
                    asyncio.create_task(self.callback(False))
                    self._is_paused = False
                elif data['t'] == "STOP_ERROR" and self.callback is not None:
                    asyncio.create_task(self.callback(True))
                    self._is_paused = False
                elif data['t'] == "VOICE_PACKET":
                    if self.decode_mode:
                        asyncio.create_task(self.decode_voice_packet(data['d']))
                elif data['t'] == "SSRC_UPDATE":
                    self.khown_ssrc[data['d']['ssrc']] = data['d']['user']
            elif i.type == aiohttp.WSMsgType.CLOSED:
                break
            elif i.type == aiohttp.WSMsgType.ERROR:
                break
        await self.ws.close()
        await self.session.close()
        await self.disconnect()

    async def connect_ws(self):
        self.session, self.ws = await self.node.connect()
        asyncio.create_task(self.ws_read())
        asyncio.create_task(self.heartbeat())

    async def connect(self, *, timeout: float = 60.0, reconnect: bool = True, self_deaf: bool = False,
                      self_mute: bool = False) -> None:
        self.node = await self.node_manager.get_best_node(self.channel.rtc_region)
        try:
            await self.connect_ws()
            self.ready.set()  # for safety
            await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)
            await asyncio.wait_for(self.connected.wait(), timeout=timeout)
        except BaseException as e:
            await self.disconnect()
            self.ready.set()
            self.connected.set()
            raise e

    async def play(self, data, type=None, after=None):
        await self.connected.wait()
        await self.ws.send_json({
            "t": "PLAY",
            "d": {
                "url": data,
                "type": type
            }
        })
        self.callback = after

    async def stop(self):
        await self.connected.wait()
        await self.ws.send_json({"t": "STOP"})

    async def set_volume(self, volume):
        await self.connected.wait()
        await self.ws.send_json({"t": "VOLUME", "d": volume})
        self.volume = volume

    async def pause(self) -> None:
        await self.connected.wait()
        await self.ws.send_json({"t": "PAUSE"})
        self._is_paused = True

    async def resume(self) -> None:
        await self.connected.wait()
        await self.ws.send_json({"t": "RESUME"})
        self._is_paused = False

    async def disconnect(self, *, force: bool = False) -> None:
        if self.ws is not None:
            await self.ws.close()
        await self.session.close()
        await self.channel.guild.change_voice_state(channel=None)
        self.cleanup()
