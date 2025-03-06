import discord
from discord.ext import commands
import hashlib
import requests
import time
import pandas
from io import StringIO

env = {}
with open(".env", "r") as file:
	while True:
		line = file.readline()
		if line == "":
			break
		key, value = line.split('=')
		env[key] = value

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

def generate_md5(form, secret):
    return hashlib.md5((form + secret).encode('utf-8')).hexdigest()

async def redeemXD(code, id):
	url1 = 'https://wos-giftcode-api.centurygame.com/api/player'
	url2 = 'https://wos-giftcode-api.centurygame.com/api/gift_code'
	headers = {
		'Content-Type': 'application/x-www-form-urlencoded'
	}
	secret = 'tB87#kPtkxqOS2' #DO NOT EDIT
	form = f"cdk={code}&fid={id}&time={str(int(time.time() * 1000))}"
	form = f"sign={generate_md5(form, secret)}&" + form

	response1 = requests.post(url1, headers=headers, data=form)
	response2 = requests.post(url2, headers=headers, data=form)
	info = "{} : {}".format(
		f"{response1.json()['data']['nickname'].replace('\xa0', ' ')}".rjust(30),
		response2.json()['msg']
	)
	return info

@bot.event
async def on_ready():
	await bot.tree.sync()
	print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
	if message.content == "!ping":
		await message.channel.send("Pong!")
	await bot.process_commands(message)

@bot.command(help='blabla <test> 123')
async def redeem(ctx, code: str=None):
	if code is not None:
		channel = ctx.channel
		thread = channel.get_thread(1346985572983504918)
		message = [message async for message in thread.history(limit=2, oldest_first=True)][0]
		url = message.attachments[0].url
		rep = requests.get(url)
		buffer = StringIO(rep.text)
		ids = pandas.read_csv(buffer, index_col='ID', skip_blank_lines=True, comment='#').index
		for id in ids:
			result = await redeemXD(code, id)
			result = '```' + result + '```'
			await ctx.send(result)
		await ctx.send("Done")

@bot.tree.command(name="redeem", description="Redeem a code", extras=[{"name": "code", "required": True}])
async def redeem(interaction: discord.Interaction, code: str):
	if code:
		channel = interaction.channel
		thread = channel.get_thread(1346985572983504918)
		message = [message async for message in thread.history(limit=2, oldest_first=True)][0]
		url = message.attachments[0].url
		rep = requests.get(url)
		buffer = StringIO(rep.text)
		ids = pandas.read_csv(buffer, index_col='ID', skip_blank_lines=True, comment='#').index
		for id in ids:
			result = await redeemXD(code, id)
			result = '```' + result + '```'
			await interaction.channel.send(result)
		await interaction.channel.send("Done")

@bot.command(alisases=["hi", "hey"])
async def hello(ctx):
	await ctx.send("Miaou")

bot.run(env["DISCORD_TOKEN"])
