import asyncio
import os
from typing import Union

import aiohttp
import discord


class Node:
    def __init__(self, host, region):
        self.host = host
        self.region = region

    async def connect(self):
        session = aiohttp.ClientSession()
        ws = await session.ws_connect(f"https://{self.host}/voice")
        return session, ws

    async def status(self):
        await req_get(self.host, "/status")
        return



async def req_get(host, path):
    async with aiohttp.ClientSession(base_url=host) as s:
        async with s.get(path) as r:
            return await r.json()


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

    def check_region(self, region):
        for k, v in self.DEFAULT_REGIONS.items():
            if region in v:
                return k

    async def add_nodes(self, *args):
        for i in args:
            out = await req_get(i, "/region")
            region = self.check_region(out["continent"])
            node_class = Node(i, region)
            self.NODE[region].append(node_class)

    def __init__(self):
        pass

class Voice(discord.VoiceClient):
    def __init__(self, client: discord.Client, channel: Union[discord.channel.VoiceChannel, discord.abc.Connectable]):
        self.session = None
        self.callback = None
        self.volume = 100
        self.ready = asyncio.Event()
        self.ws = None
        self.client = client
        self.channel = channel
        self._is_paused = False

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
        sid = os.urandom(13).hex()
        while True:
            await asyncio.sleep(30)
            if not self.ws.closed:
                await self.ws.send_json({
                    "t": "PING"
                })
            else:
                break

    async def ws_read(self):
        async for i in self.ws:
            data = i.json()
            print(data)
            if data['t'] == "STOP" and self.callback is not None:
                asyncio.create_task(self.callback(False))
                self._is_paused = False
            elif data['t'] == "STOP_ERROR" and self.callback is not None:
                asyncio.create_task(self.callback(True))
                self._is_paused = False
        await self.ws.close()
        await self.session.close()
        await self.disconnect()

    async def connect_ws(self):
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect("http://localhost:8080/voice")
        asyncio.create_task(self.ws_read())
        asyncio.create_task(self.heartbeat())

    async def connect(self, *, timeout: float = 60.0, reconnect: bool = True, self_deaf: bool = False,
                      self_mute: bool = False) -> None:
        try:
            await self.connect_ws()
            self.ready.set()
            await self.channel.guild.change_voice_state(channel=self.channel, self_mute=self_mute, self_deaf=self_deaf)
        except BaseException as e:
            await self.disconnect()
            self.ready.set()
            raise e

    async def play(self, data, after=None):
        await self.ready.wait()
        await self.ws.send_json({
            "t": "PLAY",
            "d": data
        })
        self.callback = after

    async def stop(self):
        await self.ready.wait()
        await self.ws.send_json({"t": "STOP"})

    async def set_volume(self, volume):
        await self.ready.wait()
        await self.ws.send_json({"t": "VOLUME", "d": volume})
        self.volume = volume

    async def pause(self) -> None:
        await self.ready.wait()
        await self.ws.send_json({"t": "PAUSE"})
        self._is_paused = True

    async def resume(self) -> None:
        await self.ready.wait()
        await self.ws.send_json({"t": "RESUME"})
        self._is_paused = False

    async def disconnect(self, *, force: bool = False) -> None:
        if self.ws is not None:
            await self.ws.close()
        await self.session.close()
        await self.channel.guild.change_voice_state(channel=None)
        self.cleanup()