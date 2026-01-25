import discord
from discord.ext import commands
from discord import app_commands
import logging
import pandas as pd
import io
import os
from datetime import datetime, timedelta
import asyncio
from database import database_manager as db_manager

logger = logging.getLogger('forts_commands')

class Forts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fort_channel_id = 1368845134791184484
        self.admin_role_ids = []
        
        # Load multiple admin role IDs from environment variables (comma-separated)
        role_ids_str = os.getenv('ADMIN_ROLE_IDS', '')
        
        # Fallback to old single ADMIN_ROLE_ID for backwards compatibility
        if not role_ids_str:
            role_ids_str = os.getenv('ADMIN_ROLE_ID', '')
        
        if role_ids_str:
            for rid in role_ids_str.split(','):
                rid = rid.strip()
                if rid:
                    try:
                        self.admin_role_ids.append(int(rid))
                    except ValueError:
                        logger.warning(f"Invalid role ID in ADMIN_ROLE_IDS: {rid}")
            
            if self.admin_role_ids:
                logger.info(f"Admin role IDs successfully loaded: {self.admin_role_ids}")
            else:
                logger.error("No valid admin role IDs found. Check ADMIN_ROLE_IDS in .env file.")
        else:
            logger.error("ADMIN_ROLE_IDS not set in .env file.")

    @app_commands.command(name='fort_stats', description='Show your fort participation statistics.')
    async def fort_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Get linked account
        accounts = db_manager.get_linked_accounts(interaction.user.id)
        if not accounts:
            await interaction.followup.send("You have no linked accounts. Use `/link_account` first.", ephemeral=False)
            return

        # Use main account by default or let user choose? For now, main or first.
        player_id = accounts[0]['player_id']
        player_name = accounts[0]['player_name']
        
        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk:
            # Fallback to "General" if no KvK is set, as per user request
            current_kvk = "General"

        stats = db_manager.get_fort_stats(player_id, current_kvk)
        
        embed = discord.Embed(title=f"🏰 Fort Statistics: {player_name}", color=discord.Color.dark_orange())
        embed.set_footer(text=f"Season: {current_kvk}")
        
        if stats:
            # Requirements: 35 forts combined (joined + launched?)
            # User said: "сколько фортов запущено, к скольки присоедиился и вместе"
            # "требования к каждому игроку - вместе 35 фортов"
            
            joined = stats['forts_joined']
            launched = stats['forts_launched']
            total = stats['total_forts']
            penalties = stats['penalties']
            
            req_forts = 35
            diff = total - req_forts
            status = "✅ Met" if diff >= 0 else f"❌ Missing {abs(diff)}"
            
            embed.add_field(name="Joined", value=str(joined), inline=True)
            embed.add_field(name="Launched", value=str(launched), inline=True)
            embed.add_field(name="Total", value=f"**{total}** / {req_forts}", inline=True)
            embed.add_field(name="Status", value=status, inline=False)
            
            if penalties > 0:
                embed.add_field(name="⚠️ Penalties", value=f"{penalties} points ({penalties} days ban)", inline=False)
        else:
            embed.description = f"No fort statistics found for **{current_kvk}**."
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name='fort_downloads', description='Download and parse fort stats from the stats channel.')
    @app_commands.describe(start_date="DD/MM/YYYY HH:MM", end_date="DD/MM/YYYY HH:MM")
    @app_commands.default_permissions(administrator=True)
    async def fort_downloads(self, interaction: discord.Interaction, start_date: str, end_date: str):
        # Check admin
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        
        channel = self.bot.get_channel(self.fort_channel_id)
        if not channel:
            await interaction.followup.send(f"❌ Could not find fort stats channel ({self.fort_channel_id}). Check permissions.")
            return

        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, "%d/%m/%Y %H:%M")
            end_dt = datetime.strptime(end_date, "%d/%m/%Y %H:%M")
            
            if start_dt > end_dt:
                await interaction.edit_original_response(content="❌ Start date cannot be after end date.")
                return
        except ValueError:
            await interaction.edit_original_response(content="❌ Invalid date format. Use DD/MM/YYYY HH:MM (e.g., 08/08/2025 00:00)")
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk:
            # Fallback to "General" if no KvK is set
            current_kvk = "General"
            await interaction.followup.send("⚠️ No active KvK season set. Saving stats to **General** category.")

    async def process_fort_file(self, attachment, current_kvk):
        """Helper to process a single fort stats file."""
        try:
            data = await attachment.read()
            if attachment.filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(data))
            else:
                df = pd.read_excel(io.BytesIO(data))
            
            # Process DF
            df.columns = [c.strip().lower() for c in df.columns]
            logger.info(f"Processing file {attachment.filename}. Columns: {df.columns.tolist()}")
            
            # Mapping logic
            col_id = next((c for c in df.columns if 'governor_id' in c or ('id' in c and 'message' not in c and 'governor' not in c)), None)
            # Prefer 'governor_id' if available, else 'id'
            if 'governor_id' in df.columns:
                col_id = 'governor_id'
            
            col_name = next((c for c in df.columns if 'governor_name' in c or 'name' in c), None)
            
            # Try to find joined/launched columns
            # Common names: 'joined', 'is_joined', 'participated'
            col_joined = next((c for c in df.columns if any(x in c for x in ['join', 'participat', 'member'])), None)
            
            # Common names: 'launched', 'is_captain', 'captain', 'rally_leader', 'creator'
            col_launched = next((c for c in df.columns if any(x in c for x in ['launch', 'captain', 'leader', 'creat'])), None)
            
            logger.info(f"Mapped columns: ID={col_id}, Name={col_name}, Joined={col_joined}, Launched={col_launched}")
            
            stats_data = {}
            
            if col_id and (col_joined or col_launched):
                for _, row in df.iterrows():
                    try:
                        pid = int(row[col_id])
                        pname = str(row[col_name]) if col_name else "Unknown"
                        
                        # Handle boolean/int conversion
                        joined_val = row[col_joined] if col_joined else 0
                        if isinstance(joined_val, str):
                            joined = 1 if joined_val.lower() in ['true', 'yes', '1'] else 0
                        else:
                            joined = int(joined_val)
                            
                        launched_val = row[col_launched] if col_launched else 0
                        if isinstance(launched_val, str):
                            launched = 1 if launched_val.lower() in ['true', 'yes', '1'] else 0
                        else:
                            launched = int(launched_val)
                        
                        if pid not in stats_data:
                            stats_data[pid] = {'name': pname, 'joined': 0, 'launched': 0}
                            
                        stats_data[pid]['joined'] += joined
                        stats_data[pid]['launched'] += launched
                    except ValueError:
                        continue
            else:
                logger.warning("Could not find required columns.")
                        
            return stats_data
        except Exception as e:
            logger.error(f"Failed to process file {attachment.filename}: {e}")
            return None

    @app_commands.command(name='fort_wait', description='Wait for a fort stats file to be uploaded in this channel.')
    @app_commands.default_permissions(administrator=True)
    async def fort_wait(self, interaction: discord.Interaction):
        # Check admin
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=True)
            return

        current_kvk = db_manager.get_current_kvk_name() or "General"
        
        await interaction.response.send_message(
            f"👀 **Listening Mode Active**\n"
            f"Waiting for a CSV/Excel file in this channel for 60 seconds...\n"
            f"Target Season: **{current_kvk}**\n"
            f"👉 *Run the other bot's command now!*",
            ephemeral=False
        )
        
        def check(m):
            return m.channel.id == interaction.channel_id and m.attachments and \
                   (m.attachments[0].filename.endswith('.csv') or m.attachments[0].filename.endswith('.xlsx'))

        try:
            message = await self.bot.wait_for('message', check=check, timeout=60.0)
            
            # Process the file
            attachment = message.attachments[0]
            await interaction.followup.send(f"📥 File detected: `{attachment.filename}`. Processing...")
            
            stats_data = await self.process_fort_file(attachment, current_kvk)
            
            if not stats_data:
                await interaction.followup.send("❌ Failed to parse the file or no valid data found.")
                return

            # Save to DB
            stats_list = []
            req_forts = 35
            
            for pid, data in stats_data.items():
                total = data['joined'] + data['launched']
                penalty = 1 if total < req_forts else 0
                
                stats_list.append({
                    'player_id': pid,
                    'player_name': data['name'],
                    'forts_joined': data['joined'],
                    'forts_launched': data['launched'],
                    'total_forts': total,
                    'penalties': penalty,
                    'kvk_name': current_kvk,
                    'period_key': 'total'
                })
                
            if db_manager.import_fort_stats(stats_list):
                await interaction.followup.send(f"✅ Successfully imported stats for {len(stats_list)} players from `{attachment.filename}`!")
            else:
                await interaction.followup.send("❌ Database error.")
                
        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ Timeout. No file received in 60 seconds.")
        except Exception as e:
            logger.error(f"Error in fort_wait: {e}")
            await interaction.followup.send(f"❌ An error occurred: {e}")

    @commands.command(name='fort_upload')
    async def fort_upload_prefix(self, ctx):
        """Upload a fort stats file manually (Prefix Command). Usage: !fort_upload (attach file)"""
        # Check admin
        if not self.is_admin_ctx(ctx):
            await ctx.send("❌ You do not have permissions.")
            return

        if not ctx.message.attachments:
            await ctx.send("❌ Please attach a CSV or Excel file to your message.")
            return

        attachment = ctx.message.attachments[0]
        if not (attachment.filename.endswith('.csv') or attachment.filename.endswith('.xlsx')):
            await ctx.send("❌ Please upload a CSV or Excel file.")
            return

        # Always use "General" or "Total" for forts, ignoring KvK as requested
        current_kvk = "General"
        
        await ctx.send(f"📥 Processing `{attachment.filename}`...")
        
        stats_data = await self.process_fort_file(attachment, current_kvk)
        
        if not stats_data:
            await ctx.send("❌ Failed to parse the file or no valid data found.")
            return

        # Save to DB
        stats_list = []
        req_forts = 35
        
        for pid, data in stats_data.items():
            total = data['joined'] + data['launched']
            penalty = 1 if total < req_forts else 0
            
            stats_list.append({
                'player_id': pid,
                'player_name': data['name'],
                'forts_joined': data['joined'],
                'forts_launched': data['launched'],
                'total_forts': total,
                'penalties': penalty,
                'kvk_name': current_kvk,
                'period_key': 'total'
            })
            
        if db_manager.import_fort_stats(stats_list):
            await ctx.send(f"✅ Successfully imported stats for {len(stats_list)} players from `{attachment.filename}`!")
        else:
            await ctx.send("❌ Database error.")

    def is_admin_ctx(self, ctx):
        if not self.admin_role_ids:
            return False
        for role_id in self.admin_role_ids:
            role = discord.utils.get(ctx.guild.roles, id=role_id)
            if role and role in ctx.author.roles:
                return True
        return False

    @app_commands.command(name='fort_downloads', description='Download and parse fort stats from the stats channel.')
    @app_commands.describe(start_date="Optional: Start date (DD/MM/YYYY HH:MM). Defaults to 24h ago.", 
                          end_date="Optional: End date (DD/MM/YYYY HH:MM). Defaults to now.")
    @app_commands.default_permissions(administrator=True)
    async def fort_downloads(self, interaction: discord.Interaction, start_date: str = None, end_date: str = None):
        # Check admin
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)
        
        channel = self.bot.get_channel(self.fort_channel_id)
        if not channel:
            await interaction.followup.send(f"❌ Could not find fort stats channel ({self.fort_channel_id}). Check permissions.")
            return

        try:
            # Parse dates or use defaults (UTC)
            now = discord.utils.utcnow()
            if end_date:
                # Parse as naive then replace with UTC (assuming user input is UTC? Or local?)
                # Usually users input local time. But history expects UTC.
                # Let's assume user input is roughly local, but we need to be careful.
                # For simplicity, let's treat input as UTC or just use naive if discord.py handles it.
                # Safest: Use naive if comparing with naive, or aware if comparing with aware.
                # discord.py history yields aware datetimes (UTC).
                # So we must use aware datetimes.
                dt = datetime.strptime(end_date, "%d/%m/%Y %H:%M")
                # Assume user input is local time (UTC+2 or whatever). 
                # Converting to UTC is hard without knowing offset.
                # Let's just make it UTC-aware for now to match types, even if time is off by a few hours.
                # Or better: don't convert, just set tzinfo=utc.
                # But if user says 21:00 and it's 21:00 local, that's 19:00 UTC.
                # If we say 21:00 UTC, we look into the future.
                # Let's just use the "24h ago" logic relative to NOW (UTC).
                end_dt = dt.replace(tzinfo=None) # Keep naive for now, let's see.
                # Actually, discord.py history(after=...) works best with UTC aware.
                # Let's just use defaults mostly.
                pass
            
            # RE-WRITE:
            # If user provides dates, we assume they are server-local time.
            # We convert them to UTC? No, simple approach:
            # If no dates provided, use discord.utils.utcnow() - 24h.
            
            if not start_date and not end_date:
                end_dt = discord.utils.utcnow()
                start_dt = end_dt - timedelta(hours=24)
            else:
                # Fallback to naive parsing if user specified dates
                # This might miss some messages if timezone differs, but it's what we had.
                # We'll just make them naive to avoid "can't compare offset-naive and offset-aware"
                if end_date:
                    end_dt = datetime.strptime(end_date, "%d/%m/%Y %H:%M")
                else:
                    end_dt = datetime.now()
                    
                if start_date:
                    start_dt = datetime.strptime(start_date, "%d/%m/%Y %H:%M")
                else:
                    start_dt = end_dt - timedelta(days=7)
                
                if start_dt > end_dt:
                    await interaction.edit_original_response(content="❌ Start date cannot be after end date.")
                    return
        except ValueError:
            await interaction.edit_original_response(content="❌ Invalid date format. Use DD/MM/YYYY HH:MM (e.g., 08/08/2025 00:00)")
            return

        current_kvk = db_manager.get_current_kvk_name()
        if not current_kvk:
            # Fallback to "General" if no KvK is set
            current_kvk = "General"
            await interaction.followup.send("⚠️ No active KvK season set. Saving stats to **General** category.")

        # Format dates for display
        s_str = start_dt.strftime("%d/%m/%Y %H:%M")
        e_str = end_dt.strftime("%d/%m/%Y %H:%M")
        
        logger.info(f"Scanning channel {channel.name} ({channel.id}) from {s_str} to {e_str}")
        await interaction.followup.send(f"🔄 Scanning channel <#{channel.id}> for CSV files between {s_str} and {e_str}...")
        
        processed_files = 0
        total_stats = {} # player_id -> {joined, launched, name}
        
        msg_count = 0
        found_attachments = 0
        
        # Check permissions
        permissions = channel.permissions_for(interaction.guild.me)
        if not permissions.read_message_history:
            await interaction.followup.send("❌ I do not have 'Read Message History' permission in this channel.")
            return

        # Use limit only, filter manually to avoid timezone/iterator issues
        async for message in channel.history(limit=500):
            # Filter by date manually
            # message.created_at is UTC aware
            if not (start_dt <= message.created_at <= end_dt):
                continue
                
            msg_count += 1
            if message.attachments:
                found_attachments += len(message.attachments)
                for attachment in message.attachments:
                    logger.info(f"Found attachment: {attachment.filename}")
                    if attachment.filename.lower().endswith('.csv') or attachment.filename.lower().endswith('.xlsx'):
                        file_stats = await self.process_fort_file(attachment, current_kvk)
                        if file_stats:
                            for pid, data in file_stats.items():
                                if pid not in total_stats:
                                    total_stats[pid] = {'name': data['name'], 'joined': 0, 'launched': 0}
                                
                                total_stats[pid]['joined'] += data['joined']
                                total_stats[pid]['launched'] += data['launched']
                                # Update name if unknown
                                if total_stats[pid]['name'] == "Unknown" and data['name'] != "Unknown":
                                    total_stats[pid]['name'] = data['name']
                            
                            processed_files += 1
                        else:
                            logger.warning(f"File {attachment.filename} processed but returned no stats.")
                    else:
                        logger.info(f"Skipping non-CSV/Excel file: {attachment.filename}")
        
        logger.info(f"Scanned {msg_count} messages, found {found_attachments} attachments, processed {processed_files} files.")

        if not total_stats:
            await interaction.followup.send(f"⚠️ No valid data found. Scanned {msg_count} messages, found {found_attachments} attachments.")
            return

        # Calculate totals and penalties
        stats_list = []
        req_forts = 35
        
        for pid, data in total_stats.items():
            total = data['joined'] + data['launched']
            penalty = 1 if total < req_forts else 0
            
            stats_list.append({
                'player_id': pid,
                'player_name': data['name'],
                'forts_joined': data['joined'],
                'forts_launched': data['launched'],
                'total_forts': total,
                'penalties': penalty,
                'kvk_name': current_kvk,
                'period_key': 'total'
            })
            
        # Save to DB
        if db_manager.import_fort_stats(stats_list):
            await interaction.followup.send(f"✅ Successfully processed {processed_files} files. Updated stats for {len(stats_list)} players.")
        else:
            await interaction.followup.send("❌ Error saving stats to database.")

    def is_admin(self, interaction: discord.Interaction):
        if not self.admin_role_ids:
            logger.warning("Admin role check failed because no role IDs were loaded.")
            return False

        # Check if user has any of the admin roles
        for role_id in self.admin_role_ids:
            admin_role = discord.utils.get(interaction.guild.roles, id=role_id)
            if admin_role and admin_role in interaction.user.roles:
                return True
        return False
