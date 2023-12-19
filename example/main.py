import io

import discord
import numpy
import pydub

import songbird
from songbird import VoiceClientModel
from discord.ext import commands

from songbird.main import empty_audio

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='fbt!', intents=intents)
bot.voice_manager = songbird.NodeManager()


@bot.event
async def setup_hook():
    # auth
    # await bot.voice_manager.add_nodes(["http://localhost:8080", "hi"])
    # no auth
    await bot.voice_manager.add_nodes(["http://localhost:8080", None])


@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')


class Voice(VoiceClientModel):
    decode_mode = True  # set True if you want to decode voice packet default ís False

    def __init__(self, *args, **kwargs):
        # set same key name that you to set NodeManager in bot
        super().__init__("voice_manager", *args, **kwargs)


@bot.command(name="in")
async def _in(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    elif ctx.guild.voice_client is None:
        if ctx.author.voice is None:
            await ctx.send("You are not connected to a voice channel.")
            return

        voice_channel = ctx.author.voice.channel
        voice_client = await voice_channel.connect(cls=Voice)
        await ctx.send(f'Joined voice channel: {voice_channel.name}')


@bot.command(name="p")
async def play(ctx: commands.Context, *, data):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    elif ctx.guild.voice_client is None:
        if ctx.author.voice is None:
            await ctx.send("You are not connected to a voice channel.")
            return

    voice_client = await ctx.author.voice.channel.connect(cls=Voice)
    mess = await ctx.send("Loading...")

    async def print_data(is_err):
        print(is_err)
        if is_err:
            await mess.edit(content="audio Error")
        await voice_client.disconnect()

    # type == None for type == "youtube" for youtube video support
    await voice_client.play(data, type="youtube", after=print_data)
    await mess.edit(content=f'Playing: {data}')


@bot.command(name="rs")
async def rs(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    if ctx.guild.voice_client.is_paused():
        await ctx.guild.voice_client.resume()
    else:
        await ctx.guild.voice_client.pause()


@bot.command(name="record_flush")
async def record_flush(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    out: pydub.AudioSegment = await ctx.guild.voice_client.flush_all()
    out_file = io.BytesIO()
    out.export(out_file, format="wav")
    file = discord.File(out_file, filename="output.wav")
    await ctx.send("Done", file=file)


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


bot.run('bot token')
