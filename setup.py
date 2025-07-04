import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase = create_client(url, key)

class Configuracion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="configurar",
        description="Configura los parámetros iniciales del servidor"
    )
    @app_commands.describe(
        rol_staff="Rol de administradores/moderadores",
        rol_duenos="Rol de dueños de equipos",
        canal_fichajes="Canal para fichajes de jugadores",
        canal_traspasos="Canal para traspasos de jugadores",
        canal_bajas="Canal para bajas de jugadores",
        canal_partidos="Canal para programación de partidos",
        limite_jugadores="Límite de jugadores por equipo (1-50)",
        rol_streamers="Rol de streamers (opcional)",
        rol_arbitros="Rol de árbitros (opcional)",
        rol_subdts="Rol de sub-DTs",
        canal_transacciones="Canal para todas las transacciones (opcional, para compatibilidad)"
    )
    @app_commands.default_permissions(administrator=True)
    async def configurar(
        self,
        interaccion: discord.Interaction,
        rol_staff: discord.Role,
        rol_duenos: discord.Role,
        canal_fichajes: discord.TextChannel,
        canal_traspasos: discord.TextChannel,
        canal_bajas: discord.TextChannel,
        canal_partidos: discord.TextChannel,
        rol_subdts: discord.Role,
        limite_jugadores: app_commands.Range[int, 1, 50] = 15,
        rol_streamers: discord.Role = None,
        rol_arbitros: discord.Role = None,
        canal_transacciones: discord.TextChannel = None
    ):
        """Configura los roles y canales necesarios para el bot"""
        
        if not interaccion.user.guild_permissions.administrator:
            await interaccion.response.send_message("❌ **Necesitas ser administrador para usar este comando**", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚙️ **Configuración del Servidor**",
            description="Guardando los parámetros...",
            color=0x1abc9c
        )
        
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        embed.add_field(name="**👮 Rol Staff**", value=rol_staff.mention, inline=True)
        embed.add_field(name="**👑 Rol Dueños**", value=rol_duenos.mention, inline=True)
        embed.add_field(name="**📥 Canal Fichajes**", value=canal_fichajes.mention, inline=True)
        embed.add_field(name="**🔄 Canal Traspasos**", value=canal_traspasos.mention, inline=True)
        embed.add_field(name="**📤 Canal Bajas**", value=canal_bajas.mention, inline=True)
        embed.add_field(name="**⏰ Canal Partidos**", value=canal_partidos.mention, inline=True)
        embed.add_field(name="**🧾 Límite Jugadores**", value=str(limite_jugadores), inline=True)
        embed.add_field(name="**👥 Rol Sub DTs**", value=rol_subdts.mention, inline=True)
        
        if rol_streamers:
            embed.add_field(name="**🎥 Rol Streamers**", value=rol_streamers.mention, inline=True)
        if rol_arbitros:
            embed.add_field(name="**🏁 Rol Árbitros**", value=rol_arbitros.mention, inline=True)
        if canal_transacciones:
            embed.add_field(name="**💱 Canal Transacciones**", value=canal_transacciones.mention, inline=True)

        config_data = {
            "guild_id": str(interaccion.guild.id),
            "staff": str(rol_staff.id),
            "fowner": str(rol_duenos.id),
            "signChannel": str(canal_fichajes.id),
            "transferChannel": str(canal_traspasos.id),
            "releaseChannel": str(canal_bajas.id),
            "GametimeChannel": str(canal_partidos.id),
            "rcap": limite_jugadores,
            "srole": str(rol_streamers.id) if rol_streamers else None,
            "referee": str(rol_arbitros.id) if rol_arbitros else None,
            "subdts_role": str(rol_subdts.id),
            "sign": True,
            "TransChannel": str(canal_transacciones.id) if canal_transacciones else None  # Campo opcional para compatibilidad
        }

        try:
            existing = supabase.table("servers").select("*").eq("guild_id", str(interaccion.guild.id)).execute()
            
            if existing.data:
                supabase.table("servers").update(config_data).eq("guild_id", str(interaccion.guild.id)).execute()
                embed.set_footer(text="✅ **Configuración actualizada**")
            else:
                supabase.table("servers").insert(config_data).execute()
                embed.set_footer(text="✅ **Configuración creada**")
            
            await interaccion.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ **Error en la configuración**",
                description=f"Ocurrió un error al guardar:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaccion.response.send_message(embed=error_embed, ephemeral=True)

    @app_commands.command(
        name="verconfiguracion",
        description="Muestra la configuración actual del servidor"
    )
    @app_commands.default_permissions(administrator=True)
    async def verconfiguracion(self, interaccion: discord.Interaction):
        """Muestra la configuración actual del servidor"""
        
        if not interaccion.user.guild_permissions.administrator:
            await interaccion.response.send_message("❌ **Necesitas ser administrador para usar este comando**", ephemeral=True)
            return

        try:
            config = supabase.table('servers').select('*').eq('guild_id', str(interaccion.guild.id)).execute()
            
            if not config.data:
                await interaccion.response.send_message("ℹ️ **No hay configuración guardada para este servidor**", ephemeral=True)
                return

            config_data = config.data[0]
            
            embed = discord.Embed(
                title="⚙️ **Configuración Actual del Servidor**",
                color=0x1abc9c
            )
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            
            rol_staff = interaccion.guild.get_role(int(config_data["staff"])) if config_data["staff"] else "No configurado"
            rol_duenos = interaccion.guild.get_role(int(config_data["fowner"])) if config_data["fowner"] else "No configurado"
            canal_fichajes = interaccion.guild.get_channel(int(config_data["signChannel"])) if config_data.get("signChannel") else "No configurado"
            canal_traspasos = interaccion.guild.get_channel(int(config_data["transferChannel"])) if config_data.get("transferChannel") else "No configurado"
            canal_bajas = interaccion.guild.get_channel(int(config_data["releaseChannel"])) if config_data.get("releaseChannel") else "No configurado"
            canal_partidos = interaccion.guild.get_channel(int(config_data["GametimeChannel"])) if config_data["GametimeChannel"] else "No configurado"
            canal_transacciones = interaccion.guild.get_channel(int(config_data["TransChannel"])) if config_data.get("TransChannel") else None
            rol_streamers = interaccion.guild.get_role(int(config_data["srole"])) if config_data["srole"] else None
            rol_arbitros = interaccion.guild.get_role(int(config_data["referee"])) if config_data["referee"] else None
            rol_subdts = interaccion.guild.get_role(int(config_data["subdts_role"])) if config_data.get("subdts_role") else None
            
            embed.add_field(name="**👮 Rol Staff**", value=rol_staff.mention if hasattr(rol_staff, "mention") else rol_staff, inline=True)
            embed.add_field(name="**👑 Rol Dueños**", value=rol_duenos.mention if hasattr(rol_duenos, "mention") else rol_duenos, inline=True)
            embed.add_field(name="**📥 Canal Fichajes**", value=canal_fichajes.mention if hasattr(canal_fichajes, "mention") else canal_fichajes, inline=True)
            embed.add_field(name="**🔄 Canal Traspasos**", value=canal_traspasos.mention if hasattr(canal_traspasos, "mention") else canal_traspasos, inline=True)
            embed.add_field(name="**📤 Canal Bajas**", value=canal_bajas.mention if hasattr(canal_bajas, "mention") else canal_bajas, inline=True)
            embed.add_field(name="**⏰ Canal Partidos**", value=canal_partidos.mention if hasattr(canal_partidos, "mention") else canal_partidos, inline=True)
            if canal_transacciones:
                embed.add_field(name="**💱 Canal Transacciones**", value=canal_transacciones.mention, inline=True)
            embed.add_field(name="**🧾 Límite Jugadores**", value=str(config_data["rcap"]) if config_data["rcap"] else "No configurado", inline=True)
            embed.add_field(name="**👥 Rol Sub DTs**", value=rol_subdts.mention if rol_subdts else "No configurado", inline=True)
            
            if rol_streamers:
                embed.add_field(name="**🎥 Rol Streamers**", value=rol_streamers.mention, inline=True)
            if rol_arbitros:
                embed.add_field(name="**🏁 Rol Árbitros**", value=rol_arbitros.mention, inline=True)
            
            embed.set_footer(text="🔍 **Configuración actual**")
            
            await interaccion.response.send_message(embed=embed)
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ **Error al obtener configuración**",
                description=f"Ocurrió un error:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaccion.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Configuracion(bot))
