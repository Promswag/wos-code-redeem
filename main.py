import hashlib
import requests
import time
import pandas
import asyncio
from datetime import datetime
from io import StringIO

import discord
from discord.ext import commands

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

async def redeem_request(code, id, count_retries=0, max_retries=6):
	url = "https://wos-giftcode-api.centurygame.com/api/"
	headers = {"Content-Type": "application/x-www-form-urlencoded"}
	secret = "tB87#kPtkxqOS2"
	form = f"cdk={code}&fid={id}&time={str(int(time.time() * 1000))}"
	form = f"sign={generate_md5(form, secret)}&" + form

	login_response = requests.post(url + "player", headers=headers, data=form)
	if login_response.status_code != 200:
		if count_retries < max_retries:
			await asyncio.sleep(10)
			return await redeem_request(code, id, count_retries + 1)
		else:
			print(str(login_response))
			return -1, "Too many retries, aborting"
	
	login_response = login_response.json()
	if login_response["err_code"] == 40004:
		return 1, f"Could not login player : {id}"
	
	redeem_response = requests.post(url + "gift_code", headers=headers, data=form)
	if redeem_response.status_code != 200:
		if count_retries < max_retries:
			await asyncio.sleep(10)
			return await redeem_request(code, id, count_retries + 1)
		else:
			print(str(login_response))
			print(str(redeem_response))
			return -1, "Too many retries, aborting"
	
	redeem_response = redeem_response.json()
	user = f"{id}; {login_response['data']['nickname'].replace('\xa0', ' ')};"

	# SUCCESS
	if redeem_response["err_code"] == 20000:
		return 1, user + " Gift code successfully claimed"
	# USED
	elif redeem_response["err_code"] == 40005:
		return -1, f"Gift code {code} has reached max redeem limit"
	# TIME ERROR
	elif redeem_response["err_code"] == 40007:
		return -1, f"Gift code {code} is expired"
	# RECEIVED
	elif redeem_response["err_code"] == 40008:
		return 2, user + " Gift code already claimed"
	# SAME TYPE EXCHANGE
	elif  redeem_response["err_code"] == 40011:
		return 2, user + " Gift code already claimed"
	# CDK NOT FOUND
	elif redeem_response["err_code"] == 40014:
		return -1, f"Gift code {code} doesn't exist"
	# TIMEOUT RETRY
	elif redeem_response["err_code"] == 40004:
		if count_retries < max_retries:
			await asyncio.sleep(10)
			return await redeem_request(code, id, count_retries + 1)
		else:
			print(str(login_response))
			print(str(redeem_response))
			return -1, "Too many retries, aborting"
	else:
		print(str(login_response))
		print(str(redeem_response))
		return 0, "Unknown Error"

@bot.event
async def on_ready():
	await bot.tree.sync()
	print(f"Logged in as {bot.user}")

@bot.event
async def on_message(message):
	if message.mentions:
		for m in message.mentions:
			if m.id == bot.user.id:
				await message.channel.send("Wesh ma poule!")
	await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
	print(f"{type(error).__name__}: {error}")

@bot.tree.command(name="redeem", description="Redeem a code", extras=[{"name": "code", "required": True}])
async def redeem(interaction: discord.Interaction, code: str):
	print(interaction.user)
	await interaction.response.defer()

	if code is None:
		await interaction.edit_original_response(content="Gift code missing!")
		return
	
	channel = interaction.channel
	if channel.id != int(env["CHANNEL_ID"]):
		await interaction.edit_original_response(content="Wrong channel!")
		return
	
	embed = discord.Embed(title=":gift: Gift code redeem processing...", color=discord.Color.yellow())
	embed.add_field(name="", value="")
	REP = await interaction.channel.send(embed=embed)
	
	start = time.time()
	
	thread = channel.get_thread(int(env["THREAD_ID"]))
	message = [message async for message in thread.history(limit=1, oldest_first=True)][0]
	url = message.attachments[0].url
	rep = requests.get(url)
	buffer = StringIO(rep.text)
	ids = pandas.read_csv(buffer, index_col='ID', skip_blank_lines=True, comment='#').index
	
	size = len(ids)
	counter = {"success" : 0, "used": 0, "error": 0}

	for i, id in enumerate(ids):
		err, msg = await redeem_request(code, id)

		if err == -1:
			print(msg)
			await REP.delete()
			await interaction.edit_original_response(content=msg)
			return
		elif err == 0:
			print(msg)
			counter["error"] += 1
		elif err == 1:
			counter["success"] += 1
		elif err == 2:
			counter["used"] += 1

		formated_message = "{}\n{}\n{}\n{}\n{}\n".format(
			f":alarm_clock: Process ongoing for {(time.time() - start):.0f} secs... ",
			f":peach: Progress: {i + 1}/{size}",
			f":white_check_mark: Success: {counter["success"]}",
			f":warning: Already claimed: {counter["used"]}",
			f":x: Error: {counter["error"]}"
		)
		embed.set_field_at(index=0, name="", value=formated_message)
		await REP.edit(embed=embed)
				
	await REP.delete()
	embed.title = f":gift: Gift code {code} redeemed!"
	embed.color = discord.Color.green()
	formated_message = "{}\n{}\n{}\n{}\n{}".format(
		f":hourglass: Process completed in {(time.time() - start):.0f} secs ",
		f":peach: Progress: {size}/{size}",
		f":white_check_mark: Success: {counter["success"]}",
		f":warning: Already claimed: {counter["used"]}",
		f":x: Error: {counter["error"]}"
	)
	embed.set_field_at(0, name="", value=formated_message)
	await channel.send(embed=embed)
	await interaction.edit_original_response(content="Gift code redeem completed")

@bot.tree.command(name="add", description="Adds the given ID(s) to the redeem list", extras=[{"name": "ID(s)", "required": True}])
async def add(interaction: discord.Interaction, ids: str):
	print(interaction.user)
	await interaction.response.defer(ephemeral=True)

	try:
		ids = [int(id) for id in ids.split(' ')]
	except:
		await interaction.edit_original_response(content="ID(s) must be digits only")
		return

	thread = interaction.channel.get_thread(int(env["THREAD_ID"]))
	message = [message async for message in thread.history(limit=1, oldest_first=True)][0]

	await interaction.edit_original_response(content="Inserting new ID(s)...")
	if message.attachments:
		url = message.attachments[0].url
		rep = requests.get(url)
		buffer_in = StringIO(rep.text)
		df = pandas.read_csv(buffer_in, index_col='ID', skip_blank_lines=True, comment='#')

		ids = [id for id in ids if id not in df.index]
		if len(ids) == 0:
			await interaction.edit_original_response(content="No new ID(s) found, aborting")
			return
		
		df.to_csv("backup/" + datetime.now().strftime("%d-%m-%Y_%H-%M-%S"), index_label='ID')
		df = pandas.concat([df, pandas.DataFrame(index=ids)])
		with StringIO() as buffer_out:
			df.to_csv(buffer_out, index=True, index_label='ID')
			buffer_out.seek(0)
			try:
				await thread.send(file=discord.File(buffer_out, filename="ID.csv"))
			except Exception as error:
				print(f"{type(error).__name__}: {error}")
				await interaction.edit_original_response(content=f"{type(error).__name__}: {error}")
				return
			await interaction.edit_original_response(content="New ID(s) succesfully inserted!")
			await message.delete()

bot.run(env["DISCORD_TOKEN"])
