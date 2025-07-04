import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import asyncio
import aiohttp
import logging
from datetime import datetime, timedelta
import random

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Configuración del servidor HTTP para Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de Discord en funcionamiento"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Configuración del bot con rate limiting mejorado
intents = discord.Intents.default()  # Usar intents por defecto en lugar de all()
intents.message_content = True
intents.guilds = True
intents.members = True

# Configuración de rate limiting personalizada
class RateLimitedBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.startup_time = datetime.now()
        self.request_count = 0
        self.last_request_time = datetime.now()
        self.rate_limit_delay = 1.0  # Delay base entre requests
        
    async def safe_http_request(self, coro, max_retries=3):
        """Wrapper para requests HTTP con rate limiting y reintentos"""
        for attempt in range(max_retries):
            try:
                # Aplicar delay aleatorio para evitar patrones predecibles
                delay = self.rate_limit_delay + random.uniform(0.1, 0.5)
                await asyncio.sleep(delay)
                
                self.request_count += 1
                self.last_request_time = datetime.now()
                
                return await coro
                
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = getattr(e, 'retry_after', 60)
                    logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    await asyncio.sleep(retry_after + random.uniform(1, 5))
                    self.rate_limit_delay = min(self.rate_limit_delay * 1.5, 5.0)  # Aumentar delay
                    continue
                elif e.status in [500, 502, 503, 504]:  # Server errors
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"Server error {e.status}. Retry {attempt + 1}/{max_retries} in {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"HTTP Error {e.status}: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in HTTP request: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise Exception(f"Max retries ({max_retries}) exceeded")

# Crear bot con configuración mejorada
bot = RateLimitedBot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True,
    strip_after_prefix=True
)

# Lista de todos los cogs/modulos
COGS = [
    "setup",  # Primero el setup para asegurar configuración inicial
    "gametime",
    "kick",
    "offer",
    "sign",
    "stream",
    "team",
    "ban",
    "demand",
    "demote"
]

async def load_cogs():
    """Carga todos los módulos y maneja errores con rate limiting"""
    loaded = []
    failed = []
    
    for i, cog in enumerate(COGS):
        try:
            # Delay progresivo entre cargas de cogs
            if i > 0:
                await asyncio.sleep(2 + random.uniform(0, 1))
            
            await bot.load_extension(cog)
            loaded.append(cog)
            logger.info(f"✅ Cog {cog} cargado exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error al cargar {cog}: {type(e).__name__}: {e}")
            failed.append(cog)
    
    print(f"\n✅ Módulos cargados: {', '.join(loaded)}")
    if failed:
        print(f"❌ Módulos fallidos: {', '.join(failed)}")

@bot.event
async def on_ready():
    print(f"\nBot conectado como {bot.user.name} (ID: {bot.user.id})")
    print(f"Conectado a {len(bot.guilds)} servidores")
    
    # Esperar un poco antes de cargar cogs para evitar rate limiting inicial
    await asyncio.sleep(3)
    await load_cogs()
    
    # Sincronizar comandos con rate limiting
    try:
        print("\n🔄 Sincronizando comandos...")
        await asyncio.sleep(2)  # Delay antes de sincronizar
        
        synced = await bot.safe_http_request(bot.tree.sync())
        print(f"🔁 Comandos sincronizados: {len(synced)}")
        
    except Exception as e:
        logger.error(f"⚠️ Error al sincronizar comandos: {e}")

# Manejo de errores global mejorado
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏱️ Este comando está en cooldown. Intenta en {error.retry_after:.1f} segundos.")
        return
    elif isinstance(error, discord.HTTPException) and error.status == 429:
        await ctx.send("⚠️ Bot temporalmente limitado. Intenta más tarde.")
        return
    
    logger.error(f"Error en comando {ctx.command}: {error}")
    
    try:
        await ctx.send("❌ Ocurrió un error al ejecutar el comando.")
    except:
        pass  # Evitar errores en cascade

# Event para monitorear rate limiting
@bot.event
async def on_socket_response(msg):
    # Reducir delay si no hemos tenido problemas
    if hasattr(bot, 'rate_limit_delay') and bot.rate_limit_delay > 1.0:
        if datetime.now() - bot.last_request_time > timedelta(minutes=5):
            bot.rate_limit_delay = max(bot.rate_limit_delay * 0.9, 1.0)

# Comando para ver estadísticas del bot
@bot.command(name="stats")
@commands.cooldown(1, 60, commands.BucketType.guild)  # Cooldown de 1 minuto
async def stats(ctx):
    """Muestra estadísticas del bot"""
    uptime = datetime.now() - bot.startup_time
    
    embed = discord.Embed(
        title="📊 Estadísticas del Bot",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="⏱️ Uptime", 
        value=f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m",
        inline=True
    )
    
    embed.add_field(
        name="🌐 Servidores", 
        value=len(bot.guilds),
        inline=True
    )
    
    embed.add_field(
        name="📡 Requests", 
        value=getattr(bot, 'request_count', 0),
        inline=True
    )
    
    embed.add_field(
        name="⚡ Rate Limit Delay", 
        value=f"{getattr(bot, 'rate_limit_delay', 1.0):.1f}s",
        inline=True
    )
    
    await ctx.send(embed=embed)

async def run_bot():
    """Ejecuta el bot con manejo de errores y reconexión"""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("No se encontró el token de Discord en las variables de entorno")
    
    max_retries = 3
    retry_delay = 30
    
    for attempt in range(max_retries):
        try:
            await bot.start(token)
            break
        except discord.LoginFailure:
            logger.error("❌ Error: Token de Discord inválido. Verifica tu .env o variables de entorno")
            break
        except (discord.HTTPException, aiohttp.ClientError) as e:
            if attempt < max_retries - 1:
                logger.warning(f"Error de conexión (intento {attempt + 1}/{max_retries}): {e}")
                logger.info(f"Reintentando en {retry_delay} segundos...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Backoff exponencial
            else:
                logger.error(f"❌ Error de conexión después de {max_retries} intentos: {e}")
                raise
        except Exception as e:
            logger.error(f"❌ Error inesperado: {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise

def main():
    print("🚀 Iniciando bot...")
    
    # Iniciar servidor HTTP en un hilo separado
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Iniciar el bot de Discord
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido manualmente")
    except Exception as e:
        print(f"❌ Error inesperado: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()