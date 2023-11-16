import discord
import songbird
from songbird import VoiceClientModel
from discord.ext import commands

intents = discord.Intents.all()

bot = commands.Bot(command_prefix='fbt!', intents=intents)
bot.voice_manager = songbird.NodeManager()


@bot.event
async def setup_hook():
    await bot.voice_manager.add_nodes(["http://192.168.1.14:1999", "5a21b246343746f98f013532f61dee5b"])


@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user.name}')


class Voice(VoiceClientModel):
    def __init__(self, *args, **kwargs):
        super().__init__("voice_manager", *args, **kwargs)


@bot.command(name="p")
async def _in(ctx: commands.Context, *, data):
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

    async def print_data(is_err):
        if is_err:
            await mess.edit(content="audio Error")
        await ctx.guild.voice_client.disconnect()

    await ctx.guild.voice_client.play(data, print_data)
    mess = await ctx.send(f'Playing: {data}')


@bot.command(name="rs")
async def _in(ctx: commands.Context):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return
    if ctx.guild.voice_client.is_paused():
        await ctx.guild.voice_client.resume()
    else:
        await ctx.guild.voice_client.pause()


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
