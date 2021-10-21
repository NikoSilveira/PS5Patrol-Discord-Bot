import discord
import praw
import os
import re
from discord.ext import tasks
from replit import db
from keep_alive import keep_alive

posts_to_fetch = 11 #10+1 to skip pinned msg
frecuency = 5      #minutes

#------------
#   Reddit
#------------

reddit = praw.Reddit(
  client_id=os.environ['REDDIT_CID'], 
  client_secret=os.environ['REDDIT_SECRET'], 
  user_agent=os.environ['REDDIT_UAGENT']
)

def get_hot_posts(): #fetch top n posts from hot section of given subreddit
  hot_posts = reddit.subreddit('PS5restock').hot(limit=posts_to_fetch)
  title_list = []
  url_list = []
  flair_list = []
  id_list = []

  for post in hot_posts: #save titles and urls into lists and return them
    title_list.append(post.title)
    url_list.append(post.url)
    flair_list.append(post.link_flair_text)
    id_list.append(post.id)

  return title_list, url_list, flair_list, id_list

#-------------
#   Discord
#-------------

prefix = '&'
client = discord.Client()

#### Embed functions ####

def build_main_embed(title, url, flair):
  #Use regex to check flair
  x = re.findall('PS5 HAS BEEN RESTOCKED', flair) 
  if not x:
    return

  embed = discord.Embed(
    title='POTENTIAL RESTOCK!',
    description=title, 
    color=discord.Color.gold()
  )
  embed.add_field(name='Flair:', value=flair, inline=False)
  embed.add_field(name='Link:', value=url, inline=False)

  return embed

def build_help_embed(): #Assemble the embed with the bot info
  embed = discord.Embed(
    title='Hey, PS5 Patrol here!',
    description='I will frecuently search and notify you about PS5 restocks.',
    color=discord.Color.blue()
  )
  embed.add_field(
    name='&start command',
    value='This command will initiate the automatic search process. Use it in the channels you want me to post in.',
    inline=False
  )
  embed.add_field(
    name='&stop command',
    value='This command will stop me from posting in a previously set channel.',
    inline= False
  )
  embed.add_field(
    name='&hello command',
    value='Small greeting.',
    inline= False
  )
  embed.set_footer(text='Bot made by Outfasted')

  return embed

#### Database management ####

def add_to_db(message):
  channel_list = db['channels']           #Fetch the list
  current_channel_id = message.channel.id #Get the current ids to add

  if current_channel_id in channel_list:  #add only if not already present
    return
  else: 
    channel_list.append(current_channel_id)
    db['channels'] = channel_list

def del_from_db(message):
  channel_list = db['channels']           #Fetch the list
  current_channel_id = message.channel.id #Get the current ids to delete

  if current_channel_id in channel_list:  #del only if already present
    channel_list.remove(current_channel_id)
    db['channels'] = channel_list
  else:
    return
  
#### Automatic executions ####

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))
  await client.change_presence(activity=discord.Game(name='&help')) #Set status

  #Initialize db if it's empty
  try: db['channels'] 
  except: db['channels'] = []

  try: db['posted']
  except: db['posted'] = []

  search_loop.start() #Must be here to allow cache to fill up first; avoids errors
  
@client.event
async def on_guild_join(guild): 

  #Intro message when bot joins a server
  for channel in guild.text_channels:
    if channel.permissions_for(guild.me).send_messages:
      await channel.send('Hello, my name is PS5 Patrol! Use &help to see some info about me. Use &start to begin searching.')
    break

@tasks.loop(minutes=frecuency) #automatic loop (checks every 15min)
async def search_loop():

  target = db['channels'] #fetch list of guilds to post in
  title_list, url_list, flair_list, id_list = get_hot_posts() #fetch the data

  posted_list = db['posted'] #fetch anti-repost list

  #Posting process
  for i in range(len(target)):          #for every guild
    for j in range(len(title_list)):    #for every available reddit post
      if id_list[j] not in posted_list: #check for reposts

        try:
          await client.get_channel(target[i]).send(embed=build_main_embed(
            title_list[j], url_list[j], flair_list[j]))

        except: #If bot was kicked or server deleted, or anything else
          pass

  #Save new repost data to db
  for i in range(len(id_list)):
    if id_list[i] not in posted_list:
      posted_list.append(id_list[i])
  db['posted'] = posted_list

#### Commands ####

@client.event
async def on_message(message):
  
  if message.author == client.user or message.author.bot: #Ignore if own msg or if bot
    return

  if message.content.startswith(prefix + 'hello'):  #Test cmd
    await message.channel.send('Hello!')
    return

  if message.content.startswith(prefix + 'help'):   #Help embed cmd
    await message.channel.send(embed=build_help_embed())
    return

  if message.content.startswith(prefix + 'start'):  #Init automatic search cmd
    add_to_db(message)
    await message.channel.send('I will now post here!')
    return

  if message.content.startswith(prefix + 'stop'):   #Stop automatic search cmd
    del_from_db(message)
    await message.channel.send('I will no longer post here!')
    return

keep_alive()                    #Start web server
client.run(os.environ['TOKEN']) #Execute disc bot