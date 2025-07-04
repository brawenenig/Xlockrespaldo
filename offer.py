import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from datetime import datetime

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class OfferCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_notification(self, guild: discord.Guild, embed: discord.Embed, notification_type: str):
        """
        Envía notificaciones a los canales correspondientes
        Tipos: 'sign' (fichajes), 'trade' (traspasos), 'release' (bajas)
        """
        # Primero intentar con el canal específico
        channel_field = {
            'sign': 'signChannel',
            'trade': 'transferChannel',
            'release': 'releaseChannel'
        }.get(notification_type, 'TransChannel')
        
        specific_channel = supabase.table('servers').select(channel_field).eq('guild_id', str(guild.id)).execute()
        
        if specific_channel.data and specific_channel.data[0].get(channel_field):
            channel = guild.get_channel(int(specific_channel.data[0][channel_field]))
            if channel:
                await channel.send(embed=embed)
                return True
        
        # Si no hay canal específico configurado, usar el canal general de transacciones
        trans_channel = supabase.table('servers').select('TransChannel').eq('guild_id', str(guild.id)).execute()
        if trans_channel.data and trans_channel.data[0].get('TransChannel'):
            channel = guild.get_channel(int(trans_channel.data[0]['TransChannel']))
            if channel:
                await channel.send(embed=embed)
                return True
        
        return False

    async def send_transfer_notification(self, guild: discord.Guild, jugador: discord.Member, dt: discord.Member, team_data: dict):
        """Envía la notificación de fichaje"""
        team_role = guild.get_role(int(team_data['role']))
        emoji = team_data['emoji']
        emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
        
        config = supabase.table('servers').select('rcap').eq('guild_id', str(guild.id)).execute()
        roster_cap = config.data[0]['rcap'] if config.data and config.data[0]['rcap'] else 20
        
        embed = discord.Embed(
            title="✅ Jugador Fichado",
            description=(
                f"**{team_role.name}** ha fichado a {jugador.mention} `{jugador.display_name}`!\n"
                f"> **Coach:** {dt.mention if dt else 'No asignado'} `{dt.display_name if dt else 'N/A'}`\n"
                f"> **Roster:** {len(team_role.members)}/{roster_cap}"
            ),
            color=team_role.color
        )
        
        if emoji_id:
            embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96")
        
        embed.set_footer(text="XY Lock APP", icon_url=dt.display_avatar.url if dt else "https://cdn.discordapp.com/emojis/1107540193645039626.png")
        
        await self.send_notification(guild, embed, 'sign')

    async def send_trade_notification(self, guild: discord.Guild, embed: discord.Embed):
        """Envía la notificación de traspaso"""
        await self.send_notification(guild, embed, 'trade')

    @app_commands.command(name='oferta', description="Ofrecer a un jugador unirse a tu equipo")
    async def offer(self, interaction: discord.Interaction, jugador: discord.Member):
        """Envía una oferta de equipo a un jugador con el estilo XY Lock"""
        # Verificación de equipo existente
        all_teams = supabase.table('teams').select('role').eq('guild', str(interaction.guild.id)).execute()
        team_roles = [int(team['role']) for team in all_teams.data]
        
        if any(role_id in team_roles for role_id in [r.id for r in jugador.roles]):
            await interaction.response.send_message(
                "❌ Este jugador ya pertenece a un equipo",
                ephemeral=True
            )
            return

        # Obtener datos del equipo
        response = supabase.table('teams').select('*').or_(
            f"owner.eq.{interaction.user.id},coach.eq.{interaction.user.id},general.eq.{interaction.user.id}"
        ).eq('guild', str(interaction.guild.id)).execute()
        
        if not response.data:
            all_teams = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
            user_teams = [team for team in all_teams.data if str(interaction.user.id) in team.get('subdts', [])]
            
            if not user_teams:
                await interaction.response.send_message("❌ No tienes un equipo para ofrecer", ephemeral=True)
                return
            
            data = user_teams[0]
        else:
            data = response.data[0]

        team = interaction.guild.get_role(int(data['role']))
        dt = interaction.guild.get_member(int(data['owner'])) if data.get('owner') else None
        emoji = data['emoji']
        emoji_id = str(emoji).split(":")[-1][:-1] if ":" in emoji else None
        
        config = supabase.table('servers').select('rcap').eq('guild_id', str(interaction.guild.id)).execute()
        roster_cap = config.data[0]['rcap'] if config.data and config.data[0]['rcap'] else 20

        # Embed de oferta estilo XY Lock
        embed = discord.Embed(
            title="📩 Oferta de Equipo",
            description=f"{interaction.user.mention} te ha ofrecido unirte a {emoji} **{team.name}**.",
            color=team.color
        )
        
        if emoji_id:
            embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{emoji_id}.png?size=96")
        
        embed.add_field(
            name="Información del Equipo",
            value=(
                f"> **Coach:** {dt.mention if dt else 'No asignado'}\n"
                f"> **Roster actual:** {len(team.members)}/{roster_cap}"
            ),
            inline=False
        )
        
        embed.set_footer(
            text=f"XY Lock APP • Oferta enviada por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        class OfertaView(discord.ui.View):
            def __init__(self, bot, guild_id: int, team_data: dict, dt: discord.Member):
                super().__init__(timeout=600)
                self.bot = bot
                self.guild_id = guild_id
                self.team_data = team_data
                self.dt = dt
                self.value = None

            @discord.ui.button(label="ACEPTAR", style=discord.ButtonStyle.success, emoji="✅")
            async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                guild = self.bot.get_guild(self.guild_id)
                team_role = guild.get_role(int(self.team_data['role'])) if guild else None
                member = guild.get_member(interaction.user.id) if guild else None
                
                if not all([guild, team_role, member]):
                    await interaction.response.send_message("❌ Error al procesar", ephemeral=True)
                    return
                
                await member.add_roles(team_role)
                await interaction.response.send_message(
                    f"✅ Ahora formas parte de **{team_role.name}**",
                    ephemeral=True
                )
                
                await self.bot.get_cog('OfferCog').send_transfer_notification(guild, interaction.user, self.dt, self.team_data)
                self.value = True
                self.stop()

            @discord.ui.button(label="RECHAZAR", style=discord.ButtonStyle.danger, emoji="✖️")
            async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.send_message(
                    "❌ Oferta declinada",
                    ephemeral=True
                )
                self.value = False
                self.stop()

        try:
            await jugador.send(embed=embed, view=OfertaView(self.bot, interaction.guild.id, data, dt))
            await interaction.response.send_message(
                f"✉ Oferta enviada a {jugador.mention}",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ No se pudo enviar la oferta (MDs bloqueados)",
                ephemeral=True
            )

    @app_commands.command(name='traspaso', description="Ofrecer un traspaso de jugador a otro equipo")
    @app_commands.describe(
        jugador="Jugador que quieres traspasar",
        equipo_destino="Equipo al que quieres enviar al jugador",
        motivo="Motivo del traspaso (opcional)",
        jugador_a_recibir="Jugador que recibirías a cambio (opcional)"
    )
    async def traspaso(
        self,
        interaction: discord.Interaction,
        jugador: discord.Member,
        equipo_destino: discord.Role,
        motivo: str = None,
        jugador_a_recibir: discord.Member = None
    ):
        """Gestiona traspasos con estilo XY Lock"""
        try:
            # Verificación de permisos
            response = supabase.table('teams').select('*').or_(
                f"owner.eq.{interaction.user.id},coach.eq.{interaction.user.id},general.eq.{interaction.user.id}"
            ).eq('guild', str(interaction.guild.id)).execute()
            
            if not response.data:
                all_teams = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
                user_teams = [team for team in all_teams.data if str(interaction.user.id) in team.get('subdts', [])]
                
                if not user_teams:
                    await interaction.response.send_message("❌ No tienes permiso para traspasos", ephemeral=True)
                    return
                
                equipo_origen_data = user_teams[0]
            else:
                equipo_origen_data = response.data[0]

            equipo_origen_role = interaction.guild.get_role(int(equipo_origen_data['role']))
            if equipo_origen_role not in jugador.roles:
                await interaction.response.send_message("❌ El jugador no es de tu equipo", ephemeral=True)
                return

            equipo_destino_data = supabase.table('teams').select('*').eq('role', str(equipo_destino.id)).eq('guild', str(interaction.guild.id)).execute()
            if not equipo_destino_data.data:
                await interaction.response.send_message("❌ Equipo destino no registrado", ephemeral=True)
                return
            
            equipo_destino_data = equipo_destino_data.data[0]
            dt_destino = interaction.guild.get_member(int(equipo_destino_data['owner'])) if equipo_destino_data.get('owner') else None

            # Obtener emoji del equipo destino
            emoji_destino = equipo_destino_data['emoji']
            emoji_destino_id = str(emoji_destino).split(":")[-1][:-1] if ":" in emoji_destino else None
            emoji_destino_url = f"https://cdn.discordapp.com/emojis/{emoji_destino_id}.png?size=96" if emoji_destino_id else None

            # Embed de traspaso estilo XY Lock
            embed = discord.Embed(
                title="🔄 Oferta de Traspaso",
                description=f"{interaction.user.mention} te ha enviado una oferta de traspaso",
                color=0xf39c12  # Naranja
            )
            
            if emoji_destino_url:
                embed.set_thumbnail(url=emoji_destino_url)
            
            embed.add_field(
                name="Jugador Ofrecido",
                value=f"{jugador.mention} `{jugador.display_name}`",
                inline=False
            )
            
            embed.add_field(
                name="De Equipo",
                value=f"{equipo_origen_data['emoji']} {equipo_origen_role.name}",
                inline=True
            )
            
            embed.add_field(
                name="A Equipo",
                value=f"{equipo_destino_data['emoji']} {equipo_destino.name}",
                inline=True
            )
            
            if jugador_a_recibir:
                embed.add_field(
                    name="Jugador Solicitado",
                    value=f"{jugador_a_recibir.mention} `{jugador_a_recibir.display_name}`",
                    inline=False
                )
            
            if motivo:
                embed.add_field(
                    name="Motivo",
                    value=motivo,
                    inline=False
                )
            
            embed.set_footer(
                text=f"XY Lock APP • Oferta enviada por {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            class TraspasoView(discord.ui.View):
                def __init__(self, bot, guild_id: int, equipo_origen_data: dict, equipo_destino_data: dict, jugador: discord.Member, jugador_a_recibir: discord.Member = None):
                    super().__init__(timeout=86400)
                    self.bot = bot
                    self.guild_id = guild_id
                    self.equipo_origen_data = equipo_origen_data
                    self.equipo_destino_data = equipo_destino_data
                    self.jugador = jugador
                    self.jugador_a_recibir = jugador_a_recibir
                    self.value = None

                @discord.ui.button(label="ACEPTAR", style=discord.ButtonStyle.success, emoji="✅")
                async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    guild = self.bot.get_guild(self.guild_id)
                    rol_origen = guild.get_role(int(self.equipo_origen_data['role'])) if guild else None
                    rol_destino = guild.get_role(int(self.equipo_destino_data['role'])) if guild else None
                    
                    if not all([guild, rol_origen, rol_destino]):
                        await interaction.response.send_message("❌ Error al procesar", ephemeral=True)
                        return
                    
                    await self.jugador.remove_roles(rol_origen)
                    await self.jugador.add_roles(rol_destino)
                    
                    if self.jugador_a_recibir:
                        await self.jugador_a_recibir.remove_roles(rol_destino)
                        await self.jugador_a_recibir.add_roles(rol_origen)
                    
                    # Notificación de traspaso completado
                    emoji_destino = self.equipo_destino_data['emoji']
                    emoji_destino_id = str(emoji_destino).split(":")[-1][:-1] if ":" in emoji_destino else None
                    emoji_destino_url = f"https://cdn.discordapp.com/emojis/{emoji_destino_id}.png?size=96" if emoji_destino_id else None

                    embed = discord.Embed(
                        title="✅ Traspaso Completado",
                        description=(
                            f"**{self.jugador.mention}** ha sido traspasado a **{rol_destino.name}**\n" +
                            (f"**{self.jugador_a_recibir.mention}** ha sido traspasado a **{rol_origen.name}**" if self.jugador_a_recibir else "")
                        ),
                        color=0x2ecc71  # Verde
                    )
                    
                    if emoji_destino_url:
                        embed.set_thumbnail(url=emoji_destino_url)
                    
                    embed.set_footer(
                        text="XY Lock APP",
                        icon_url=interaction.user.display_avatar.url
                    )
                    
                    await self.bot.get_cog('OfferCog').send_trade_notification(guild, embed)
                    
                    await interaction.response.send_message(
                        f"✅ Traspaso completado. Ahora formas parte de **{rol_destino.name}**",
                        ephemeral=True
                    )
                    self.value = True
                    self.stop()

                @discord.ui.button(label="RECHAZAR", style=discord.ButtonStyle.danger, emoji="✖️")
                async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.send_message("❌ Traspaso rechazado", ephemeral=True)
                    self.value = False
                    self.stop()

            if dt_destino:
                try:
                    view = TraspasoView(
                        self.bot, 
                        interaction.guild.id, 
                        equipo_origen_data, 
                        equipo_destino_data, 
                        jugador, 
                        jugador_a_recibir
                    )
                    
                    await dt_destino.send(embed=embed, view=view)
                    
                    await interaction.response.send_message(
                        f"✉ Oferta de traspaso enviada a {dt_destino.mention}",
                        ephemeral=True
                    )
                except discord.Forbidden:
                    await interaction.response.send_message(
                        "❌ No se pudo enviar la oferta (MDs bloqueados)",
                        ephemeral=True
                    )
            else:
                await interaction.response.send_message(
                    "❌ DT no encontrado",
                    ephemeral=True
                )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(OfferCog(bot))