import hashlib
import requests
import time
import pandas
import asyncio
import threading
from io import StringIO

import discord
from discord.ext import commands

lock = threading.Lock()
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

def redeem_request(code, id, responses):
	url = "https://wos-giftcode-api.centurygame.com/api/"
	headers = {"Content-Type": "application/x-www-form-urlencoded"}
	secret = "tB87#kPtkxqOS2"
	form = f"cdk={code}&fid={id}&time={str(time.time_ns())}"
	form = f"sign={generate_md5(form, secret)}&" + form

	login_response = requests.post(url + "player", headers=headers, data=form)
	if login_response.status_code != 200:
		print(login_response)
		with lock:
			responses["critical"].append(str(login_response))
		return
	
	login_response = login_response.json()
	if login_response["err_code"] == 40004:
		with lock:
			responses["error"].append(f"Could not login player: {id}")
		return
	
	redeem_response = requests.post(url + "gift_code", headers=headers, data=form)
	if redeem_response.status_code != 200:
		with lock:
			responses["critical"].append(str(redeem_response))
		return
	
	redeem_response = redeem_response.json()
	user = f"{f'{id}'.rjust(10)} : {login_response['data']['nickname'].replace('\xa0', ' ')}"

	if redeem_response["err_code"] == 20000:
		with lock:
			responses["success"].append(user)
	elif redeem_response["err_code"] == 40007:
		with lock:
			responses["critical"].append("Redeem code is expired")
	elif redeem_response["err_code"] == 40008 or redeem_response["err_code"] == 40011:
		with lock:
			responses["used"].append(user)
	elif redeem_response["err_code"] == 40014:
		with lock:
			responses["critical"].append("Redeem code doesn't exist")
	else:
		with lock:
			print(login_response)
			print(redeem_response)
			responses["error"].append(f"{str(redeem_response["msg"]).ljust(20)} {user}")
	return

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


@bot.tree.command(name="redeem", description="Redeem a code", extras=[{"name": "code", "required": True}])
async def redeem(interaction: discord.Interaction, code: str):

	if code is None:
		print("Code missing")
		return
	channel = interaction.channel

	if channel.id != int(env["CHANNEL_ID"]):
		print("Wrong channel")
		return
	
	start = time.time()
	
	REP = await channel.send("Starting process...")
	thread_channel = channel.get_thread(int(env["THREAD_ID"]))
	message = [message async for message in thread_channel.history(limit=1, oldest_first=True)][0]
	url = message.attachments[0].url
	rep = requests.get(url)
	buffer = StringIO(rep.text)
	ids = pandas.read_csv(buffer, index_col='ID', skip_blank_lines=True, comment='#').index
	
	size = len(ids)

	id_per_batch = 30
	responses = {"success": [], "used": [], "error": [], "critical": []}
	counter = {"success": 0, "used": 0, "error": 0, "critical": 0}

	for i in range(0, size, id_per_batch):
		batch_ids = ids[i:i + id_per_batch]

		threads = []
		for id in batch_ids:
			threads.append(threading.Thread(target=redeem_request, args=[code, id, responses]))
		for t in threads:
			t.start()
		for t in threads:
			t.join()

		for key, val in responses.items():
			counter[key] += len(val)
			if len(val) == 0:
				responses[key].append('-')

		if counter["critical"] != 0:
			await REP.delete()
			await channel.send(f"Gift code {code} is expired/not working!")
			return
		
		now = time.time()
		threshold = now + 60
		if len(batch_ids) % id_per_batch == 0:
			while now < threshold:
				await REP.edit(content=("{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}\n{}".format(
					f":alarm_clock: Process continues in {(threshold - now):.0f} secs... ",
					f":peach: Progress: {i + len(batch_ids)}/{size}",
					f":white_check_mark: Success: {counter["success"]}",
					"```\n" + "\n".join(responses["success"]) + "```",
					f":sunglasses: Already claimed: {counter["used"]}",
					"```\n" + "\n".join(responses["used"]) + "```",
					f":warning: Error: {counter["error"]}",
					"```\n" + "\n".join(responses["error"]) + "```",
					f":x: Critical: {counter["critical"]}",
					"```\n" + "\n".join(responses["critical"])  + "```"
				)))
				await asyncio.sleep(3)
				now = time.time()

		for key, val in responses.items():
			responses[key].clear()
				
	await REP.delete()
	await channel.send("{}\n{}\n{}\n{}\n{}\n{}\n{}".format(
		f":gift: Gift code {code} redeemed!",
		f":hourglass: Process completed in {(time.time() - start):.0f} secs ",
		f":peach: Progress: {size}/{size}",
		f":white_check_mark: Success: {counter["success"]}",
		f":sunglasses: Already claimed: {counter["used"]}",
		f":warning: Error: {counter["error"]}",
		f":x: Critical: {counter["critical"]}"
	))

bot.run(env["DISCORD_TOKEN"])
