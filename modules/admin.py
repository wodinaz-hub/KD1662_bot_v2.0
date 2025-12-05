import discord
from discord.ext import commands
from discord import app_commands
import os
import logging

# Logging configuration
logger = logging.getLogger('discord_bot.admin')

# List of available KvK seasons, updated according to the KvK folder structure
KVK_OPTIONS = [
    {"label": "KvK 1", "value": "kvk1", "description": "KvK Season 1"},
    {"label": "KvK 2", "value": "kvk2", "description": "KvK Season 2"},
    {"label": "KvK 3", "value": "kvk3", "description": "KvK Season 3"},
    {"label": "Alliance Invictus", "value": "alliance_invictus", "description": "Alliance Invictus KvK"},
    {"label": "Heroic Anthem", "value": "heroic_anthem", "description": "Heroic Anthem KvK"},
    {"label": "Keener Blades", "value": "keener_blades", "description": "Keener Blades KvK"},
    {"label": "King of all Britain", "value": "king_of_all_britain", "description": "King of all Britain KvK"},
    {"label": "King of the Nile", "value": "king_of_the_nile", "description": "King of the Nile KvK"},
    {"label": "Shifting Gears", "value": "shifting_gears", "description": "Shifting Gears KvK"},
    {"label": "Siege of Orleans", "value": "siege_of_orleans", "description": "Siege of Orleans KvK"},
    {"label": "Storm of Stratagems", "value": "storm_of_stratagems", "description": "Storm of Stratagems KvK"},
    {"label": "Strife of the Eight", "value": "strife_of_the_eight", "description": "Strife of the Eight KvK"},
    {"label": "Tides of War", "value": "tides_of_war", "description": "Tides of War KvK"},
    {"label": "Warriors Unbound", "value": "warriors_unbound", "description": "Warriors Unbound KvK"},
    {"label": "Song of Troy", "value": "song_of_troy", "description": "Song of Troy KvK"}
]

        kvk_name = db_manager.get_current_kvk_name()
        
        embed = discord.Embed(title="Bot Status", color=discord.Color.gold())
        
        if kvk_name and kvk_name != "Not set":
            embed.add_field(name="Current KvK Season", value=f"**{kvk_name}**", inline=False)
            
            # Check requirements
            reqs = db_manager.get_all_requirements(kvk_name)
            if reqs:
                embed.add_field(name="Requirements", value=f"✅ Set ({len(reqs)} brackets)", inline=False)
            else:
                embed.add_field(name="Requirements", value="⚠️ Not set", inline=False)
        else:
            embed.add_field(name="Current KvK Season", value="❌ Not selected", inline=False)
            embed.description = "Use `/set_kvk` to select a season."

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="finish_kvk", description="Finish the current KvK season and archive data.")
    async def finish_kvk(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        from database import database_manager as db_manager
        
        current_kvk_name = db_manager.get_current_kvk_name()
        
        if not current_kvk_name or current_kvk_name == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            return

        # Confirm action
        await interaction.response.send_message(
            f"Are you sure you want to finish **{current_kvk_name}**?\n"
            "This will archive all stats and snapshots with today's date and reset the active season.",
            view=FinishKvKConfirmView(interaction, current_kvk_name),
            ephemeral=True
        )


class FinishKvKConfirmView(discord.ui.View):
    def __init__(self, original_interaction, kvk_name):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.kvk_name = kvk_name

    @discord.ui.button(label="Yes, Finish & Archive", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from database import database_manager as db_manager
        from datetime import datetime
        
        # Get start date
        start_date = db_manager.get_kvk_start_date()
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = "Unknown"
            
        archive_name = f"{self.kvk_name} ({start_date} - {end_date})"
        
        # Archive data
        if db_manager.archive_kvk_data(self.kvk_name, archive_name):
            # Reset current KvK
            db_manager.set_current_kvk_name("Not set")
            # Reset start date (optional, or just leave it until next set)
            
            global current_kvk
            current_kvk = "Not set"
            
            await interaction.response.edit_message(
                content=f"✅ Season **{self.kvk_name}** finished.\n"
                        f"📂 Data archived as: **{archive_name}**.\n"
                        f"Bot is now ready for a new season.",
                view=None
            )
        else:
            await interaction.response.edit_message(content="❌ Error archiving data. Check logs.", view=None)
        
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        self.stop()


# Cog for administrator commands
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.admin_role_id = None
        try:
            # Attempt to load the admin role ID from environment variables
            self.admin_role_id = int(os.getenv('ADMIN_ROLE_ID'))
            logger.info(f"Admin role ID successfully loaded: {self.admin_role_id}")
        except (ValueError, TypeError):
            # Log an error if the role ID could not be loaded
            logger.error(
                "Failed to load Admin role ID. Ensure ADMIN_ROLE_ID is set in the .env file and is a number.")

    # Admin role check function
    def is_admin(self, interaction: discord.Interaction):
        if not self.admin_role_id:
            logger.warning(f"Admin role check failed because the role ID was not loaded.")
            return False

        # Retrieve the role and check if the user has it
            
            try:
                # Extract Power Range
                min_power = 0
                max_power = 0
                
                # Check for "X - Y Power"
                range_match = re.search(r'(\d+)[Mm]?\s*-\s*(\d+)[Mm]?\s*Power', line, re.IGNORECASE)
                if range_match:
                    # Usually higher number is first in text (109M - 100M), but we need min/max
                    val1 = int(range_match.group(1)) * 1_000_000
                    val2 = int(range_match.group(2)) * 1_000_000
                    min_power = min(val1, val2)
                    max_power = max(val1, val2)
                else:
                    # Check for "X+ Power"
                    plus_match = re.search(r'(\d+)[Mm]?\+\s*Power', line, re.IGNORECASE)
                    if plus_match:
                        min_power = int(plus_match.group(1)) * 1_000_000
                        max_power = 2_000_000_000 # Arbitrary high cap
                
                if min_power == 0 and max_power == 0:
                    logger.warning(f"Could not parse power range in line: {line}")
                    continue

                # Extract Goals
                # Look for numbers before "Kills" and "deads"
                # Remove dots/commas from numbers first? No, regex handles it better if we are careful.
                # Pattern: ([\d\.,]+)\s*Kills
                
                kills_match = re.search(r'([\d\.,]+)\s*Kills', line, re.IGNORECASE)
                deads_match = re.search(r'([\d\.,]+)\s*deads', line, re.IGNORECASE)
                
                req_kp = 0
                req_deads = 0
                
                if kills_match:
                    # Remove separators (. or ,)
                    clean_num = re.sub(r'[.,]', '', kills_match.group(1))
                    req_kp = int(clean_num)
                    
                if deads_match:
                    clean_num = re.sub(r'[.,]', '', deads_match.group(1))
                    req_deads = int(clean_num)
                    
                if req_kp == 0 and req_deads == 0:
                    logger.warning(f"Could not parse goals in line: {line}")
                    continue
                    
                requirements.append({
                    'min_power': min_power,
                    'max_power': max_power,
                    'required_kill_points': req_kp,
                    'required_deaths': req_deads
                })
                
            except Exception as e:
                logger.error(f"Error parsing line '{line}': {e}")
                continue
                
        return requirements


    @app_commands.command(name="set_requirements_text", description="Enter KvK requirements via text paste.")
    async def set_requirements_text(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            return

        await interaction.response.send_modal(RequirementsModal(self))


    @app_commands.command(name="status", description="Check the current status of the bot (Active KvK, Requirements).")
    async def status(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        from database import database_manager as db_manager
        
        # Get current KvK
        kvk_name = db_manager.get_current_kvk_name()
        
        embed = discord.Embed(title="Bot Status", color=discord.Color.gold())
        
        if kvk_name and kvk_name != "Not set":
            embed.add_field(name="Current KvK Season", value=f"**{kvk_name}**", inline=False)
            
            # Check requirements
            reqs = db_manager.get_all_requirements(kvk_name)
            if reqs:
                embed.add_field(name="Requirements", value=f"✅ Set ({len(reqs)} brackets)", inline=False)
            else:
                embed.add_field(name="Requirements", value="⚠️ Not set", inline=False)
        else:
            embed.add_field(name="Current KvK Season", value="❌ Not selected", inline=False)
            embed.description = "Use `/set_kvk` to select a season."

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="finish_kvk", description="Finish the current KvK season and archive data.")
    async def finish_kvk(self, interaction: discord.Interaction):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        from database import database_manager as db_manager
        
        current_kvk_name = db_manager.get_current_kvk_name()
        
        if not current_kvk_name or current_kvk_name == "Not set":
            await interaction.response.send_message("No KvK season is currently active.", ephemeral=True)
            return

        # Confirm action
        await interaction.response.send_message(
            f"Are you sure you want to finish **{current_kvk_name}**?\n"
            "This will archive all stats and snapshots with today's date and reset the active season.",
            view=FinishKvKConfirmView(interaction, current_kvk_name, self),
            ephemeral=True
        )


class FinishKvKConfirmView(discord.ui.View):
    def __init__(self, original_interaction, kvk_name, admin_cog):
        super().__init__(timeout=60)
        self.original_interaction = original_interaction
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    @discord.ui.button(label="Yes, Finish & Archive", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        from database import database_manager as db_manager
        from datetime import datetime
        
        # Get start date
        start_date = db_manager.get_kvk_start_date()
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = "Unknown"
            
        archive_name = f"{self.kvk_name} ({start_date} - {end_date})"
        
        # Archive data
        if db_manager.archive_kvk_data(self.kvk_name, archive_name):
            # Reset current KvK
            db_manager.set_current_kvk_name("Not set")
            # Reset start date (optional, or just leave it until next set)
            
            global current_kvk
            current_kvk = "Not set"
            
            await interaction.response.edit_message(
                content=f"✅ Season **{self.kvk_name}** finished.\n"
                        f"📂 Data archived as: **{archive_name}**.\n"
                        f"Bot is now ready for a new season.",
                view=None
            )
            await self.admin_cog.log_to_channel(interaction, "Finish KvK", f"KvK: {self.kvk_name}\nArchived as: {archive_name}")
        else:
            await interaction.response.edit_message(content="❌ Error archiving data. Check logs.", view=None)
            await self.admin_cog.log_to_channel(interaction, "Finish KvK Failed", f"KvK: {self.kvk_name}\nError: Archiving failed.")
        
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Action cancelled.", view=None)
        self.stop()


# Cog for administrator commands
class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.admin_role_id = None
        try:
            # Attempt to load the admin role ID from environment variables
            self.admin_role_id = int(os.getenv('ADMIN_ROLE_ID'))
            logger.info(f"Admin role ID successfully loaded: {self.admin_role_id}")
        except (ValueError, TypeError):
            # Log an error if the role ID could not be loaded
            logger.error(
                "Failed to load Admin role ID. Ensure ADMIN_ROLE_ID is set in the .env file and is a number.")

    # Admin role check function
    def is_admin(self, interaction: discord.Interaction):
        if not self.admin_role_id:
            logger.warning(f"Admin role check failed because the role ID was not loaded.")
            return False

        # Retrieve the role and check if the user has it
        admin_role = discord.utils.get(interaction.guild.roles, id=self.admin_role_id)
        if admin_role and admin_role in interaction.user.roles:
            return True
        return False

    async def log_to_channel(self, interaction: discord.Interaction, action: str, details: str):
        """Logs an admin action to the specified Discord channel."""
        log_channel_id = 1365374885404086342 # Hardcoded as per user request
        channel = self.bot.get_channel(log_channel_id)
        
        if not channel:
            logger.warning(f"Log channel {log_channel_id} not found.")
            return

        embed = discord.Embed(title="🛡️ Admin Action Logged", color=discord.Color.blue(), timestamp=interaction.created_at)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="Details", value=details, inline=False)
        embed.set_footer(text=f"ID: {interaction.user.id}")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to send log message: {e}")

    @app_commands.command(name="set_kvk", description="Sets the current KvK season (admin only).")
    async def set_kvk_command(self, interaction: discord.Interaction):
        # Role permission check
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        # Check the list of options before creating the View
        if not KVK_OPTIONS:
            logger.error("KVK_OPTIONS list is empty. Cannot create a select menu.")
            await interaction.response.send_message(
                "Sorry, the list of available KvK is empty. Please contact the developer.",
                ephemeral=True
            )
            return

        logger.info(f"Number of options in KVK_OPTIONS: {len(KVK_OPTIONS)}")
        # Respond to the interaction by sending the View (dropdown menu)
        await interaction.response.send_message("Select the current KvK:", view=KvKSelectView(interaction, self))


    @app_commands.command(name="upload_snapshot", description="Upload a KvK snapshot (Start or End).")
    @app_commands.describe(
        file="Excel file (.xlsx)",
        period_name="Name of the period (e.g., 'Pass 4')",
        snapshot_type="Type of snapshot: 'start' or 'end'"
    )
    @app_commands.choices(snapshot_type=[
        app_commands.Choice(name="Start", value="start"),
        app_commands.Choice(name="End", value="end")
    ])
    async def upload_snapshot(self, interaction: discord.Interaction, file: discord.Attachment, period_name: str, snapshot_type: app_commands.Choice[str]):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            return

        if not file.filename.endswith('.xlsx'):
            await interaction.response.send_message("Please upload a valid Excel file (.xlsx).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        # Save file temporarily
        file_path = f"temp_uploads/{file.filename}"
        if not os.path.exists("temp_uploads"):
            os.makedirs("temp_uploads")
        
        await file.save(file_path)

        from database import database_manager as db_manager
        success = db_manager.import_snapshot(file_path, current_kvk, period_name, snapshot_type.value)

        # Clean up
        os.remove(file_path)

        if success:
            await interaction.followup.send(f"Snapshot '{snapshot_type.value}' for period '{period_name}' uploaded successfully.")
            await self.log_to_channel(interaction, "Upload Snapshot", f"Period: {period_name}\nType: {snapshot_type.value}\nFile: {file.filename}")
        else:
            await interaction.followup.send("Failed to import snapshot. Check logs for details.")
            await self.log_to_channel(interaction, "Upload Snapshot Failed", f"Period: {period_name}\nType: {snapshot_type.value}\nFile: {file.filename}\nError: Import failed.")

    @app_commands.command(name="set_requirements", description="Upload KvK requirements.")
    @app_commands.describe(file="Excel file with requirements")
    async def set_requirements(self, interaction: discord.Interaction, file: discord.Attachment):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            return

        if not file.filename.endswith('.xlsx'):
            await interaction.response.send_message("Please upload a valid Excel file (.xlsx).", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        file_path = f"temp_uploads/{file.filename}"
        if not os.path.exists("temp_uploads"):
            os.makedirs("temp_uploads")
        
        await file.save(file_path)

        from database import database_manager as db_manager
        success = db_manager.import_requirements(file_path, current_kvk)

        os.remove(file_path)

        if success:
            await interaction.followup.send(f"Requirements for '{current_kvk}' uploaded successfully.")
            await self.log_to_channel(interaction, "Set Requirements (File)", f"KvK: {current_kvk}\nFile: {file.filename}")
        else:
            await interaction.followup.send("Failed to import requirements. Check logs for details.")
            await self.log_to_channel(interaction, "Set Requirements (File) Failed", f"KvK: {current_kvk}\nFile: {file.filename}\nError: Import failed.")

    @app_commands.command(name="calculate_period", description="Calculate results for a period.")
    @app_commands.describe(period_name="Name of the period to calculate")
    async def calculate_period(self, interaction: discord.Interaction, period_name: str):
        if not self.is_admin(interaction):
            await interaction.response.send_message("You do not have permissions to use this command.", ephemeral=True)
            return

        if not current_kvk or current_kvk == "Not set":
            await interaction.response.send_message("Please set the current KvK season first using /set_kvk.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from core import calculation
        success, message = calculation.calculate_period_results(current_kvk, period_name)

        if success:
            await interaction.followup.send(f"Calculation successful: {message}")
            await self.log_to_channel(interaction, "Calculate Period", f"KvK: {current_kvk}\nPeriod: {period_name}\nResult: {message}")
        else:
            await interaction.followup.send(f"Calculation failed: {message}")
            await self.log_to_channel(interaction, "Calculate Period Failed", f"KvK: {current_kvk}\nPeriod: {period_name}\nError: {message}")


async def setup(bot: commands.Bot):
    # Add the cog to the bot
    await bot.add_cog(Admin(bot))
