import os
from typing import List

import discord
import requests
from discord import Client, Intents, app_commands, Embed
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


class CharSheetFetch(Client):
    def __init__(self):
        intents = Intents.default()
        super().__init__(intents=intents)

        self.__GUILD_ID = discord.Object(id=os.getenv("GUILD_ID"))
        self.tree = app_commands.CommandTree(self)

    def get_guild_id(self):
        return self.__GUILD_ID

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=self.__GUILD_ID)
        await self.tree.sync(guild=self.__GUILD_ID)
        pass


client = CharSheetFetch()


# == Create Commands & Events here! ==
@client.event
async def on_ready():
    console.print(f"Logged in as [bold green]{client.user.name}[/bold green]", justify="center")


@client.tree.command(name="fetch",
                     description="Fetches all the character sheets made by your account, and returns a link to a pastebin.")
# Cooldown for command
@app_commands.checks.cooldown(1, 300, key=lambda i: i.user.id)  # Uncomment to enable cooldown
async def fetch(interaction: discord.Interaction):
    # We respond with a message saying "searching..." so that we don't get the application didn't respond error
    # Then scrub through the forum channels for threads authored by the interaction.user and append them all to an array
    # Then compile it all into a string and send 'er to pastebin / google sheets / etc etc
    embed = Embed(title="Character Sheet Scrubber", color=discord.Color.greyple(),
                  description="Searching for character sheet posts, please be patient!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    messages = await scrub_forums(interaction)
    await compile_sheets(interaction, messages)
    
@fetch.error
async def fetch_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await read_error(interaction, error)
    


# == Helper Functions ==

async def read_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction[0].response.send_message("You don't have permission to use this command.",
                                                   ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction[0].response.send_message(error, ephemeral=True)
    else:
        console.print(f"[red]Error[/red] {error}")
        await interaction[0].response.send_message("An error occurred while running the command",
                                                   ephemeral=True)

async def scrub_forums(interaction: discord.Interaction) -> List[discord.Message]:
    guild = client.get_guild(client.get_guild_id().id)
    posts: List[discord.Message] = []
    forum_ids = [int(forum_id) for forum_id in os.getenv("FORUM_IDS").split(",")]

    console.print(f"Fetching messages from {interaction.user.name} ({interaction.user.id})")
    for forum in guild.forums:
        # Filtering out nonspecified channels
        if forum.id not in forum_ids:
            continue
        
        for thread in forum.threads:
            if thread.owner_id != interaction.user.id:
                continue
            async for message in thread.history(limit=None, oldest_first=True):
                if message.author == interaction.user:
                    posts.append(message)

    console.print(f"Fetched {len(posts)} messages from {interaction.user.name} ({interaction.user.id})")
    return posts


async def compile_sheets(interaction: discord.Interaction, messages: List[discord.Message]):
    if len(messages) == 0:
        embed = Embed(title="No messages found!", color=discord.Color.blue(), description="Welp, looks like ya dont have any posts in the forums!")
        await interaction.response.edit_message(embed=embed)
        return
    
    embed = Embed(title="Error!!!",
                  description="Something went wrong!\nQuick! Let parrot know!!!!\n-# Oh dear, how could this have happened!",
                  color=discord.Color.red())

    # Mashing all the messages together
    content = ""
    for message in messages:
        content = content + f"{message.content}\n"

    try:
        # Posting to pastebin
        response = requests.post(
            "https://pastebin.com/api/api_post.php",
            data={
                "api_dev_key": os.getenv("PASTEBIN_KEY"),
                "api_option": "paste",
                "api_paste_code": content,
                "api_paste_name": str(interaction.user.id),
                "api_paste_private": 1,
                "api_paste_expire_date": "10M"
            }
        )

        # Catching errors
        if response.status_code != 200:
            console.print(f"HTTP Error: https://http.cat/{response.status_code}\n{response.text}")
            embed.set_image(url=f"https://http.cat/{response.status_code}")
            await interaction.edit_original_response(embed=embed)
            return
        if response.text.startswith('Bad API request'):
            console.print(f"HTTP Error: {response.text}")
            embed.add_field(name="Bad API Request", value=f"HTTP Error: {response.text}")
            await interaction.edit_original_response(embed=embed)
            return

        # All good! Send happy message!
        embed = Embed(title="Success!", color=discord.Color.green(),
                      description=f"Scrubbed all your posts from the character sheet forums! Check 'em out!!")
        embed.add_field(name="Pastebin URL", value=response.text.strip())
        embed.set_image(url=f"https://http.cat/{response.status_code}")
        await interaction.edit_original_response(embed=embed)
        console.print(f"Sent {interaction.user.name}'s scraped messages to pastebin. {response.text.strip()}")

    except requests.exceptions.RequestException as e:
        console.print(f"Request failed: {e}")
        await interaction.edit_original_response(embed=embed)


# == Running the bot ==
client.run(token=os.getenv("TOKEN"))
