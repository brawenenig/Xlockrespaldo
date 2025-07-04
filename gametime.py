import discord
from discord.ext import commands
from discord import app_commands
import datetime
from supabase import create_client, Client
url='https://ivygaxznxndtwyziklrz.supabase.co'
key='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class gametime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="gametime", description="create a gametime")
    @app_commands.describe(
        team='Opposing Team',
        time='Planned time Ex: 1:30PST'
    )
    async def gametime(self, interaction: discord.Interaction, team: discord.Role, time: str):
        response = supabase.table('teams').select('*').eq('owner', interaction.user.id).eq('guild', interaction.guild.id).execute()
        if not response.data[0]['owner']:
            await interaction.response.send_message("You don't own a team!", ephemeral=True)
            return

        data = response.data

        gettrans = supabase.table('servers').select('*').eq('guild_id', interaction.guild.id).execute()
        transchannel = gettrans.data
        channelid = transchannel[0]['GametimeChannel']
        channel = interaction.guild.get_channel(int(channelid))

        


        teamid = data[0]['role']
        teamhome = interaction.guild.get_role(int(teamid))
        hemoji = supabase.table('teams').select('emoji').eq('role', teamhome.id).eq('guild', interaction.guild.id).execute().data[0]['emoji']
        aemoji = supabase.table('teams').select('emoji').eq('role', team.id).eq('guild', interaction.guild.id).execute().data[0]['emoji']

        class Buttons(discord.ui.View):
            def __init__(self):
                super().__init__()
                self.streamer = 'N/A' 
                self.referee = 'N/A'  

            @discord.ui.button(label="Stream", style=discord.ButtonStyle.blurple, emoji='🎥')
            async def stream(self, interaction: discord.Interaction, button: discord.ui.Button):
                streamer = gettrans.data[0]['srole']
                role = interaction.guild.get_role(int(streamer))

                if streamer == None:
                    error = discord.Embed(title='<:offline:1352790185523282004> Error Detected', description=f'\n>>> Please run /setup. Make sure to set `Streamer Role`', color=0x8B0000)
                    await interaction.response.send_message(embed=error, ephemeral=True)
                    return
                if not role in interaction.user.roles:
                    error = discord.Embed(title='<:offline:1352790185523282004> Error Detected', description=f'\n>>> Invaild Permissinons for need the role `{role.name}`', color=0x8B0000)
                    await interaction.response.send_message(embed=error, ephemeral=True)
                    return
                self.streamer = interaction.user.display_name
                

                embed = discord.Embed(
                    title="Game Scheduled",
                    description=f"{hemoji}{teamhome.mention} **vs** {aemoji}{team.mention}\n"
                                f"> 🎥 Streamer: {self.streamer or 'N/A'}\n"
                                f"> 🏁 Referee: {self.referee or 'N/A'}\n"
                                f"> 🕛 Time: {time}",
                    colour=0x9d7240,
                    timestamp=datetime.datetime.now()
                )
                embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(
                    text=interaction.user.name,
                    icon_url=interaction.user.display_avatar.url
                )

                await msg.edit(embed=embed, view=self)
                await interaction.response.send_message('Done', ephemeral=True)

            @discord.ui.button(label="Referee", style=discord.ButtonStyle.blurple, emoji='🏁')
            async def refere(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.referee = interaction.user.display_name
                referee = gettrans.data[0]['referee']
                role = interaction.guild.get_role(int(referee))

                if referee == None:
                    error = discord.Embed(title='<:offline:1352790185523282004> Error Detected', description=f'\n>>> Please run /setup. Make sure to set `Referee Role`', color=0x8B0000)
                    await interaction.response.send_message(embed=error, ephemeral=True)
                    return
                if not role in interaction.user.roles:
                    error = discord.Embed(title='<:offline:1352790185523282004> Error Detected', description=f'\n>>> Invaild Permissinons for need the role `{role.name}`', color=0x8B0000)
                    await interaction.response.send_message(embed=error, ephemeral=True)
                    return


                embed = discord.Embed(
                    title="Game Scheduled",
                    description=f"{hemoji}{teamhome.mention} **vs** {aemoji}{team.mention}\n"
                                f"> 🎥 Streamer: {self.streamer or 'N/A'}\n"
                                f"> 🏁 Referee: {self.referee or 'N/A'}\n"
                                f"> 🕛 Time: {time}",
                    colour=0x9d7240,
                    timestamp=datetime.datetime.now()
                )
                embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(
                    text=interaction.user.name,
                    icon_url=interaction.user.display_avatar.url
                )

                await msg.edit(embed=embed, view=self)
                await interaction.response.send_message('Done', ephemeral=True)



        embed = discord.Embed(title="Game Scheduled",
                        description=f"{hemoji}{teamhome.mention} **vs** {aemoji}{team.mention}\n> 🎥 Streamer: N/A\n> 🏁 Referee: N/A\n> 🕛 Time: {time}",
                        colour=teamhome.color,
                        timestamp=datetime.datetime.now())
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        else: 
            pass



        embed.set_footer(
                text=interaction.user.name,
                icon_url=interaction.user.display_avatar.url
                )
            
        msg = await channel.send(embed=embed, view=Buttons())
        await interaction.response.send_message('Game Scheduled!', ephemeral=True)

async def setup(bot):
    await bot.add_cog(gametime(bot))
