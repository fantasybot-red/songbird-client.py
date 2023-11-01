import asyncio
import os
from typing import Union

import discord
import aiohttp
from discord.ext import commands

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='fbt!', intents=intents)


@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')

class Node:
    pass

class NodeManager:
    DEFAULT_REGIONS_BY_RTC = {
        'asia': ('hongkong', 'singapore', 'sydney', 'japan', 'southafrica', 'india'),
        'eu': ('rotterdam', 'russia'),
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

    def __init__(self):
        pass

    async def _start(self):
        pass

    async def start(self):
        asyncio.create_task(self._start())


class Voice(discord.VoiceClient):

    def __init__(self, client: discord.Client, channel: Union[discord.channel.VoiceChannel, discord.abc.Connectable]):
        self.session = None
        self.callback = None
        self.volume = 100
        self.ready = asyncio.Event()
        self.ws = None
        self.client = client
        self.channel = channel

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
            if data['t'] == "STOP" and self.callback is not None:
                asyncio.create_task(self.callback)
        await self.ws.close()
        await self.session.close()
        await self.disconnect()

    async def connect_ws(self):
        self.session = aiohttp.ClientSession()
        self.ws = await self.session.ws_connect("https://songbird-node.shuttleapp.rs/voice")
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

    async def resume(self) -> None:
        await self.ready.wait()
        await self.ws.send_json({"t": "RESUME"})

    async def disconnect(self, *, force: bool = False) -> None:
        if self.ws is not None:
            await self.ws.close()
        await self.session.close()
        await self.channel.guild.change_voice_state(channel=None)
        self.cleanup()


@bot.command(name="in")
async def _in(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = await voice_channel.connect(cls=Voice)

    await ctx.send(f'Joined voice channel: {voice_channel.name}')


@bot.command(name="play")
async def _in(ctx: commands.Context, *, data):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    await ctx.guild.voice_client.play(data)


@bot.command(name="pause")
async def _in(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    await ctx.guild.voice_client.pause()


@bot.command(name="resume")
async def _in(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    await ctx.guild.voice_client.resume()


@bot.command(name="volume")
async def _in(ctx: commands.Context, volume: int):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return

    await ctx.guild.voice_client.set_volume(volume)


@bot.command(name="out")
async def _out(ctx: commands.Context):
    if ctx.voice_client is None:
        await ctx.send("I am not connected to a voice channel.")
        return

    await ctx.voice_client.disconnect()
    await ctx.send("Left the voice channel.")


bot.run('MTExMjQwNDA1NTk5NDY4MzUwMg.G_NQNb.xkMdDUb3SYahazni9Cw8BdZhnwifVoJJYSJsP4')
