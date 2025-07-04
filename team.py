import discord
from discord.ext import commands
from discord import app_commands
from supabase import create_client, Client
from discord.app_commands import Choice
import json
from typing import Optional

url = 'https://ivygaxznxndtwyziklrz.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml2eWdheHpueG5kdHd5emlrbHJ6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDg0NzcwMzMsImV4cCI6MjA2NDA1MzAzM30.E7B-cdA5hySuhrwIGO2UPwlA5rzJIK0HzoZq8K_l2E0'
supabase: Client = create_client(url, key)

class Equipos(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    equipos_group = app_commands.Group(name='equipo', description='Comandos para gestionar equipos')

    async def obtener_config_servidor(self, guild_id: str):
        """Obtiene la configuración del servidor incluyendo roles de DT y sub-DT"""
        config = supabase.table('servers').select('*').eq('guild_id', guild_id).execute()
        if not config.data:
            return None
        return config.data[0]

    async def actualizar_rol_equipo(self, guild: discord.Guild, team_data: dict):
        """Actualiza el ID de rol si el nombre ha cambiado"""
        try:
            role = guild.get_role(int(team_data['role']))
            if not role:
                role = discord.utils.get(guild.roles, name=team_data['name'])
                if role:
                    supabase.table('teams').update({'role': str(role.id)}).eq('id', team_data['id']).execute()
                    team_data['role'] = str(role.id)
            return role
        except Exception:
            return None

    async def asignar_rol_administrativo(self, guild: discord.Guild, user_id: int, es_dt: bool = False):
        """Asigna el rol correspondiente (DT o sub-DT) según la configuración"""
        config = await self.obtener_config_servidor(str(guild.id))
        if not config:
            return False

        member = guild.get_member(user_id)
        if not member:
            return False

        try:
            rol_id = config['fowner'] if es_dt else config['subdts_role']
            if not rol_id:
                return False

            rol = guild.get_role(int(rol_id))
            if rol and rol not in member.roles:
                await member.add_roles(rol)
                return True
            return False
        except Exception as e:
            print(f"Error al asignar rol administrativo: {e}")
            return False

    async def remover_rol_administrativo(self, guild: discord.Guild, user_id: int, es_dt: bool = False):
        """Remueve el rol correspondiente si ya no es necesario"""
        config = await self.obtener_config_servidor(str(guild.id))
        if not config:
            return False

        member = guild.get_member(user_id)
        if not member:
            return False

        try:
            if es_dt:
                equipos = supabase.table('teams').select('owner').eq('guild', str(guild.id)).execute()
                necesita_rol = any(str(user_id) == equipo.get('owner') for equipo in equipos.data)
            else:
                equipos = supabase.table('teams').select('subdts').eq('guild', str(guild.id)).execute()
                necesita_rol = any(str(user_id) in equipo.get('subdts', []) for equipo in equipos.data)

            if not necesita_rol:
                rol_id = config['fowner'] if es_dt else config['subdts_role']
                if rol_id:
                    rol = guild.get_role(int(rol_id))
                    if rol and rol in member.roles:
                        await member.remove_roles(rol)
                        return True
            return False
        except Exception as e:
            print(f"Error al remover rol administrativo: {e}")
            return False

    @equipos_group.command(name="crear", description="Crear un nuevo equipo")
    async def crear(self, interaction: discord.Interaction, nombre: str, rol: discord.Role, emoji: str, dueño: discord.Member = None):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return
            
            if not config.get('fowner'):
                await interaction.response.send_message('❌ El rol de dueños no está configurado en el servidor.', ephemeral=True)
                return

            existing_team = supabase.table('teams').select('*').eq('name', nombre).eq('guild', str(interaction.guild.id)).execute()
            if existing_team.data:
                await interaction.response.send_message('❌ Ya existe un equipo con ese nombre.', ephemeral=True)
                return

            owner_id = str(dueño.id) if dueño else None
            response = supabase.table('teams').insert({
                "name": nombre,
                "role": str(rol.id),
                "owner": owner_id,
                "guild": str(interaction.guild.id),
                "emoji": emoji,
                "subdts": []
            }).execute()

            if dueño:
                await self.asignar_rol_administrativo(interaction.guild, dueño.id, es_dt=True)
                if rol not in dueño.roles:
                    await dueño.add_roles(rol)

            embed = discord.Embed(
                title="✅ Equipo Creado",
                description=f"El equipo **{nombre}** ha sido creado exitosamente.",
                color=0x1abc9c
            )
            embed.add_field(name="Nombre", value=nombre, inline=True)
            embed.add_field(name="Rol", value=rol.mention, inline=True)
            embed.add_field(name="Dueño", value=dueño.mention if dueño else "No asignado", inline=True)
            embed.add_field(name="Emoji", value=emoji, inline=True)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al crear el equipo:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @equipos_group.command(name='añadir_subdt', description='Añade un sub-DT a un equipo')
    async def añadir_subdt(self, interaction: discord.Interaction, equipo: discord.Role, usuario: discord.Member):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            if not config.get('subdts_role'):
                await interaction.response.send_message('❌ El rol de sub-DTs no está configurado en el servidor.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return

            team_data = supabase.table('teams').select('*').eq('role', str(equipo.id)).execute()
            if not team_data.data:
                await interaction.response.send_message('❌ No se encontró el equipo en la base de datos.', ephemeral=True)
                return

            data = team_data.data[0]
            await self.actualizar_rol_equipo(interaction.guild, data)
            
            subdts = data.get('subdts', [])
            if str(usuario.id) in subdts:
                await interaction.response.send_message('❌ Este usuario ya es sub-DT del equipo.', ephemeral=True)
                return
                
            subdts.append(str(usuario.id))
            supabase.table('teams').update({'subdts': subdts}).eq('role', str(equipo.id)).execute()
            
            await self.asignar_rol_administrativo(interaction.guild, usuario.id, es_dt=False)
            if equipo not in usuario.roles:
                await usuario.add_roles(equipo)
            
            await interaction.response.send_message(
                f'✅ {usuario.mention} ha sido añadido como sub-DT de {equipo.name}.',
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    @equipos_group.command(name='remover_subdt', description='Remueve un sub-DT de un equipo')
    async def remover_subdt(self, interaction: discord.Interaction, equipo: discord.Role, usuario: discord.Member):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return

            team_data = supabase.table('teams').select('*').eq('role', str(equipo.id)).execute()
            if not team_data.data:
                await interaction.response.send_message('❌ No se encontró el equipo en la base de datos.', ephemeral=True)
                return

            data = team_data.data[0]
            await self.actualizar_rol_equipo(interaction.guild, data)
            
            subdts = data.get('subdts', [])
            if str(usuario.id) not in subdts:
                await interaction.response.send_message('❌ Este usuario no es sub-DT del equipo.', ephemeral=True)
                return
                
            subdts.remove(str(usuario.id))
            supabase.table('teams').update({'subdts': subdts}).eq('role', str(equipo.id)).execute()
            
            await self.remover_rol_administrativo(interaction.guild, usuario.id, es_dt=False)
            
            await interaction.response.send_message(
                f'✅ {usuario.mention} ha sido removido como sub-DT de {equipo.name}.',
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(f'❌ Error: {str(e)}', ephemeral=True)

    @equipos_group.command(name='eliminar_todos', description='Elimina todos los equipos del servidor')
    async def eliminar_todos(self, interaction: discord.Interaction):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return
            
            class Confirmar(discord.ui.View):
                def __init__(self, cog):
                    super().__init__(timeout=None)
                    self.cog = cog
                
                @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
                async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer(thinking=True)
                    
                    equipos = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
                    
                    supabase.table('teams').delete().eq('guild', str(interaction.guild.id)).execute()
                    
                    for equipo in equipos.data:
                        if equipo.get('owner'):
                            await self.cog.remover_rol_administrativo(interaction.guild, int(equipo['owner']), es_dt=True)
                        
                        for subdt_id in equipo.get('subdts', []):
                            await self.cog.remover_rol_administrativo(interaction.guild, int(subdt_id), es_dt=False)
                        
                        role = interaction.guild.get_role(int(equipo['role']))
                        if role:
                            try:
                                await role.delete()
                            except:
                                continue
                    
                    await interaction.followup.send("✅ Todos los equipos han sido eliminados.", ephemeral=True)

            embed = discord.Embed(
                title="⚠️ Confirmar Eliminación",
                description="¿Estás seguro que quieres eliminar **todos** los equipos?",
                color=0xe74c3c
            )
            embed.set_footer(text="Esta acción no se puede deshacer")
            
            await interaction.response.send_message(embed=embed, view=Confirmar(self), ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @equipos_group.command(name='eliminar', description='Elimina un equipo específico')
    async def eliminar(self, interaction: discord.Interaction, equipo: discord.Role):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return

            team_data = supabase.table('teams').select('*').eq('role', str(equipo.id)).execute()
            if not team_data.data:
                await interaction.response.send_message('❌ No se encontró el equipo en la base de datos.', ephemeral=True)
                return

            data = team_data.data[0]
            
            if data.get('owner'):
                await self.remover_rol_administrativo(interaction.guild, int(data['owner']), es_dt=True)
            
            for subdt_id in data.get('subdts', []):
                await self.remover_rol_administrativo(interaction.guild, int(subdt_id), es_dt=False)

            supabase.table('teams').delete().eq('role', str(equipo.id)).execute()

            try:
                await equipo.delete()
            except discord.Forbidden:
                pass

            embed = discord.Embed(
                title="✅ Equipo Eliminado",
                description=f"El equipo {equipo.name} ha sido eliminado correctamente.",
                color=0x1abc9c
            )
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @equipos_group.command(name='lista', description='Muestra todos los equipos actuales')
    async def lista(self, interaction: discord.Interaction):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            roster_cap = config.get('rcap', 20)
            
            response = supabase.table('teams').select('*').eq('guild', str(interaction.guild.id)).execute()
            
            if not response.data:
                return await interaction.response.send_message("ℹ️ No hay equipos registrados en este servidor.", ephemeral=True)

            updated_teams = []
            for team in response.data:
                updated_role = await self.actualizar_rol_equipo(interaction.guild, team)
                if updated_role:
                    updated_teams.append(team)

            embed = discord.Embed(
                title="Lista de Equipos",
                description="Estos son los equipos actuales del servidor:",
                color=0x1abc9c
            )
            
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            
            for row in updated_teams:
                role = interaction.guild.get_role(int(row['role']))
                
                if not role:
                    continue
                
                owner_mention = "Sin dueño"
                if row['owner']:
                    owner = interaction.guild.get_member(int(row['owner']))
                    owner_mention = owner.mention if owner else f"ID: {row['owner']}"
                
                emoji = row.get('emoji', '🏈')
                
                subdts = row.get('subdts', [])
                subdt_mentions = []
                for subdt_id in subdts:
                    subdt = interaction.guild.get_member(int(subdt_id))
                    if subdt:
                        subdt_mentions.append(subdt.mention)
                
                team_info = f"**Rol:** {role.mention}\n"
                team_info += f"**Dueño (DT):** {owner_mention}\n"
                team_info += f"**Jugadores:** {len(role.members)}/{roster_cap}\n"
                if subdt_mentions:
                    team_info += f"**Sub-DTs:** {', '.join(subdt_mentions)}"
                else:
                    team_info += "**Sub-DTs:** Ninguno"
                
                embed.add_field(
                    name=f"{emoji} {row['name']}",
                    value=team_info,
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al listar los equipos:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    @equipos_group.command(name='detectar', description='Detecta equipos NFL/NCAA automáticamente')
    @app_commands.choices(opcion=[
        Choice(name='NFL', value=1),
        Choice(name='NCAA', value=2),
    ])
    async def detectar(self, interaction: discord.Interaction, opcion: app_commands.Choice[int]):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return

            with open('./commands/wteams.json', "r") as file:
                nfl_teams = json.load(file)

            await interaction.response.defer(thinking=True)
            
            creados = 0
            for role in interaction.guild.roles:
                if role.name in nfl_teams:
                    existing_team = supabase.table('teams').select('name').eq('role', str(role.id)).execute()
                    if not existing_team.data:
                        emoji = nfl_teams[role.name]
                        supabase.table('teams').insert({
                            "name": role.name,
                            "role": str(role.id),
                            "guild": str(interaction.guild.id),
                            "emoji": emoji,
                            "subdts": []
                        }).execute()
                        creados += 1

            embed = discord.Embed(
                title="✅ Equipos Detectados",
                description=f"Se detectaron y registraron {creados} equipos.",
                color=0x1abc9c
            )
            await interaction.followup.send(embed=embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al detectar equipos:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaction.followup.send(embed=error_embed)

    @equipos_group.command(name='editar', description='Edita la información de un equipo')
    async def editar(self, interaction: discord.Interaction, equipo: discord.Role):
        try:
            config = await self.obtener_config_servidor(str(interaction.guild.id))
            if not config:
                await interaction.response.send_message('❌ El servidor no está configurado correctamente.', ephemeral=True)
                return

            staff_rol = interaction.guild.get_role(int(config['staff']))
            if not (staff_rol in interaction.user.roles or interaction.user.guild_permissions.administrator):
                await interaction.response.send_message('❌ No tienes permisos para usar este comando.', ephemeral=True)
                return

            response = supabase.table('teams').select('*').eq('role', str(equipo.id)).execute()
            if not response.data:
                await interaction.response.send_message('❌ No se encontró el equipo en la base de datos.', ephemeral=True)
                return

            data = response.data[0]
            await self.actualizar_rol_equipo(interaction.guild, data)
            
            current_emoji = data.get('emoji', '🏈')
            current_owner_id = data.get('owner')
            current_subdts = data.get('subdts', [])

            embed = discord.Embed(
                title=f"✏️ Editor de Equipo: {data['name']}",
                description="Selecciona qué deseas editar:",
                color=0x1abc9c
            )
            embed.set_thumbnail(url=equipo.icon.url if hasattr(equipo, 'icon') and equipo.icon else None)
            
            current_owner = interaction.guild.get_member(int(current_owner_id)) if current_owner_id else None
            subdt_mentions = []
            for subdt_id in current_subdts:
                subdt = interaction.guild.get_member(int(subdt_id))
                if subdt:
                    subdt_mentions.append(subdt.mention)
            
            embed.add_field(
                name="⚙️ Configuración Actual",
                value=f"**Nombre:** {data['name']}\n"
                      f"**Emoji:** {current_emoji}\n"
                      f"**Dueño (DT):** {current_owner.mention if current_owner else 'No asignado'}\n"
                      f"**Sub-DTs:** {', '.join(subdt_mentions) if subdt_mentions else 'Ninguno'}\n"
                      f"**Color:** {str(equipo.color)}",
                inline=False
            )

            class SeleccionarDueño(discord.ui.UserSelect):
                def __init__(self, team_data, team_role, cog):
                    super().__init__(
                        placeholder="Selecciona un nuevo dueño...",
                        max_values=1
                    )
                    self.team_data = team_data
                    self.team_role = team_role
                    self.cog = cog
                
                async def callback(self, interaction: discord.Interaction):
                    nuevo_dueño = self.values[0]
                    antiguo_dueño_id = self.team_data.get('owner')
                    
                    supabase.table('teams').update({'owner': str(nuevo_dueño.id)}).eq('id', self.team_data['id']).execute()
                    
                    await self.cog.asignar_rol_administrativo(interaction.guild, nuevo_dueño.id, es_dt=True)
                    
                    if antiguo_dueño_id:
                        await self.cog.remover_rol_administrativo(interaction.guild, int(antiguo_dueño_id), es_dt=True)
                    
                    if self.team_role not in nuevo_dueño.roles:
                        await nuevo_dueño.add_roles(self.team_role)
                    
                    await interaction.response.send_message(
                        f"✅ Dueño actualizado a: {nuevo_dueño.mention}",
                        ephemeral=True
                    )

            class SeleccionarEmoji(discord.ui.Select):
                def __init__(self, team_data, guild):
                    emojis = guild.emojis
                    options = [
                        discord.SelectOption(
                            label="Emoji predeterminado",
                            value="🏈",
                            emoji="🏈",
                            description="Usar el emoji predeterminado"
                        )
                    ]
                    
                    for emoji in emojis:
                        options.append(
                            discord.SelectOption(
                                label=emoji.name,
                                value=str(emoji.id),
                                emoji=f"<:{emoji.name}:{emoji.id}>",
                                description=f"Emoji personalizado del servidor"
                            )
                        )
                    
                    super().__init__(
                        placeholder="Selecciona un emoji...",
                        options=options[:25],
                        max_values=1
                    )
                    self.team_data = team_data
                
                async def callback(self, interaction: discord.Interaction):
                    emoji_value = self.values[0]
                    if emoji_value == "🏈":
                        nuevo_emoji = "🏈"
                    else:
                        emoji = interaction.guild.get_emoji(int(emoji_value))
                        nuevo_emoji = f"<:{emoji.name}:{emoji.id}>"
                    
                    supabase.table('teams').update({'emoji': nuevo_emoji}).eq('id', self.team_data['id']).execute()
                    await interaction.response.send_message(
                        f"✅ Emoji actualizado a: {nuevo_emoji}",
                        ephemeral=True
                    )

            class VistaEditar(discord.ui.View):
                def __init__(self, team_data, team_role, cog, guild):
                    super().__init__(timeout=120)
                    self.team_data = team_data
                    self.team_role = team_role
                    self.cog = cog
                    self.guild = guild

                @discord.ui.button(label="Cambiar Nombre", style=discord.ButtonStyle.primary, emoji="📝")
                async def editar_nombre(self, interaction: discord.Interaction, button: discord.ui.Button):
                    modal = discord.ui.Modal(title=f"Cambiar nombre de {self.team_data['name']}")
                    nuevo_nombre = discord.ui.TextInput(
                        label="Nuevo nombre del equipo",
                        default=self.team_data['name'],
                        max_length=32
                    )
                    modal.add_item(nuevo_nombre)
                    
                    async def on_submit(interaction: discord.Interaction):
                        supabase.table('teams').update({'name': nuevo_nombre.value}).eq('id', self.team_data['id']).execute()
                        await interaction.response.send_message(
                            f"✅ Nombre actualizado a: **{nuevo_nombre.value}**",
                            ephemeral=True
                        )
                    
                    modal.on_submit = on_submit
                    await interaction.response.send_modal(modal)

                @discord.ui.button(label="Cambiar Emoji", style=discord.ButtonStyle.primary, emoji="😀")
                async def editar_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
                    vista = discord.ui.View(timeout=60)
                    vista.add_item(SeleccionarEmoji(self.team_data, self.guild))
                    await interaction.response.send_message(
                        "🔹 Selecciona un nuevo emoji para el equipo:",
                        view=vista,
                        ephemeral=True
                    )

                @discord.ui.button(label="Cambiar Dueño", style=discord.ButtonStyle.primary, emoji="👑")
                async def editar_dueño(self, interaction: discord.Interaction, button: discord.ui.Button):
                    vista = discord.ui.View(timeout=60)
                    vista.add_item(SeleccionarDueño(self.team_data, self.team_role, self.cog))
                    await interaction.response.send_message(
                        "🔹 Selecciona el nuevo dueño del equipo:",
                        view=vista,
                        ephemeral=True
                    )

                @discord.ui.button(label="Gestionar Sub-DTs", style=discord.ButtonStyle.secondary, emoji="👥")
                async def gestionar_subdts(self, interaction: discord.Interaction, button: discord.ui.Button):
                    class VistaSubDT(discord.ui.View):
                        def __init__(self, team_data, team_role, cog):
                            super().__init__(timeout=60)
                            self.team_data = team_data
                            self.team_role = team_role
                            self.cog = cog

                        @discord.ui.button(label="Añadir Sub-DT", style=discord.ButtonStyle.primary, emoji="➕")
                        async def añadir_subdt(self, interaction: discord.Interaction, button: discord.ui.Button):
                            class SeleccionarSubDT(discord.ui.UserSelect):
                                def __init__(self, team_data, cog):
                                    super().__init__(placeholder="Selecciona un miembro...", max_values=1)
                                    self.team_data = team_data
                                    self.cog = cog
                                
                                async def callback(self, interaction: discord.Interaction):
                                    usuario = self.values[0]
                                    subdts = self.team_data.get('subdts', [])
                                    
                                    if str(usuario.id) in subdts:
                                        await interaction.response.send_message("❌ Este usuario ya es sub-DT.", ephemeral=True)
                                        return
                                        
                                    subdts.append(str(usuario.id))
                                    supabase.table('teams').update({'subdts': subdts}).eq('id', self.team_data['id']).execute()
                                    
                                    await self.cog.asignar_rol_administrativo(interaction.guild, usuario.id, emoji=False)
                                    
                                    await interaction.response.send_message(
                                        f"✅ {usuario.mention} añadido como sub-DT.",
                                        ephemeral=True
                                    )
                            
                            vista = discord.ui.View(timeout=60)
                            vista.add_item(SeleccionarSubDT(self.team_data, self.cog))
                            await interaction.response.send_message(
                                "Selecciona un miembro para añadir como sub-DT:",
                                view=vista,
                                ephemeral=True
                            )

                        @discord.ui.button(label="Remover Sub-DT", style=discord.ButtonStyle.danger, emoji="➖")
                        async def remover_subdt(self, interaction: discord.Interaction, button: discord.ui.Button):
                            subdts = self.team_data.get('subdts', [])
                            if not subdts:
                                await interaction.response.send_message("ℹ️ No hay sub-DTs para remover.", ephemeral=True)
                                return
                            
                            opciones = []
                            for subdt_id in subdts:
                                miembro = interaction.guild.get_member(int(subdt_id))
                                if miembro:
                                    opciones.append(discord.SelectOption(
                                        label=miembro.display_name,
                                        value=subdt_id,
                                        description=f"Sub-DT de {self.team_data['name']}"
                                    ))
                            
                            if not opciones:
                                await interaction.response.send_message("ℹ️ No se encontraron sub-DTs válidos.", ephemeral=True)
                                return
                            
                            class RemoverSubDT(discord.ui.Select):
                                def __init__(self, team_data, cog):
                                    super().__init__(
                                        placeholder="Selecciona un sub-DT para remover...",
                                        options=opciones[:25],
                                        max_values=1
                                    )
                                    self.team_data = team_data
                                    self.cog = cog
                                
                                async def callback(self, interaction: discord.Interaction):
                                    subdts = self.team_data.get('subdts', [])
                                    if self.values[0] in subdts:
                                        subdts.remove(self.values[0])
                                        supabase.table('teams').update({'subdts': subdts}).eq('id', self.team_data['id']).execute()
                                        
                                        await self.cog.remover_rol_administrativo(interaction.guild, int(self.values[0]), es_dt=False)
                                        
                                        miembro = interaction.guild.get_member(int(self.values[0]))
                                        await interaction.response.send_message(
                                            f"✅ {miembro.mention if miembro else 'Sub-DT'} removido correctamente.",
                                            ephemeral=True
                                        )
                            
                            vista = discord.ui.View(timeout=60)
                            vista.add_item(RemoverSubDT(self.team_data, self.cog))
                            await interaction.response.send_message(
                                "Selecciona un sub-DT para remover:",
                                view=vista,
                                ephemeral=True
                            )

                    await interaction.response.send_message(
                        "🔹 Gestiona los sub-DTs del equipo:",
                        view=VistaSubDT(self.team_data, self.team_role, self.cog),
                        ephemeral=True
                    )

            await interaction.response.send_message(embed=embed, view=VistaEditar(data, equipo, self, interaction.guild), ephemeral=True)

        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Ocurrió un error al editar el equipo:\n```{str(e)}```",
                color=0xe74c3c
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Equipos(bot))