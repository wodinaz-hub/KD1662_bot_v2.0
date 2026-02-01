import discord
import re
import logging
from database import database_manager as db_manager

logger = logging.getLogger('discord_bot.admin.modals')

class RequirementsModal(discord.ui.Modal, title="Set KvK Requirements"):
    requirements_text = discord.ui.TextInput(
        label="Paste Requirements Text",
        style=discord.TextStyle.paragraph,
        placeholder="100M - 150M Power\n100M Kills / 1M deads\n...",
        required=True,
        max_length=2000
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        text = self.requirements_text.value
        parsed_reqs = self.parse_requirements(text)
        
        if not parsed_reqs:
            await interaction.response.send_message("❌ Could not parse any requirements from the text.", ephemeral=False)
            await self.admin_cog.log_to_channel(interaction, "Set Requirements Failed", "Reason: Parsing error")
            return
            
        current_kvk = db_manager.get_current_kvk_name()
        if db_manager.save_requirements_batch(current_kvk, parsed_reqs):
            await interaction.response.send_message(f"✅ Successfully saved {len(parsed_reqs)} requirement brackets for **{current_kvk}**.", ephemeral=False)
            await self.admin_cog.log_to_channel(interaction, "Set Requirements (Text)", f"KvK: {current_kvk}\nBrackets: {len(parsed_reqs)}")
            # Update timestamp
            db_manager.set_last_updated(current_kvk)
        else:
            await interaction.response.send_message("❌ Database error while saving requirements.", ephemeral=False)

    def parse_requirements(self, text):
        requirements = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            try:
                # Extract Power Range
                min_power = 0
                max_power = 0
                
                # Check for "X - Y Power"
                range_match = re.search(r'(\d+)[Mm]?\s*-\s*(\d+)[Mm]?\s*Power', line, re.IGNORECASE)
                if range_match:
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
                    continue

                # Extract Goals
                kills_match = re.search(r'([\d\.,]+[kKmMbB]?)\s*Kills', line, re.IGNORECASE)
                deads_match = re.search(r'([\d\.,]+[kKmMbB]?)\s*deads', line, re.IGNORECASE)
                
                req_kp = 0
                req_deads = 0
                
                if kills_match:
                    val_str = kills_match.group(1).replace(',', '.')
                    multiplier = 1
                    if 'k' in val_str.lower():
                        multiplier = 1_000
                        val_str = re.sub(r'[kK]', '', val_str)
                    elif 'm' in val_str.lower():
                        multiplier = 1_000_000
                        val_str = re.sub(r'[mM]', '', val_str)
                    elif 'b' in val_str.lower():
                        multiplier = 1_000_000_000
                        val_str = re.sub(r'[bB]', '', val_str)
                    
                    try:
                        req_kp = int(float(val_str) * multiplier)
                    except ValueError:
                        req_kp = 0
                    
                if deads_match:
                    val_str = deads_match.group(1).replace(',', '.')
                    multiplier = 1
                    if 'k' in val_str.lower():
                        multiplier = 1_000
                        val_str = re.sub(r'[kK]', '', val_str)
                    elif 'm' in val_str.lower():
                        multiplier = 1_000_000
                        val_str = re.sub(r'[mM]', '', val_str)
                    elif 'b' in val_str.lower():
                        multiplier = 1_000_000_000
                        val_str = re.sub(r'[bB]', '', val_str)

                    try:
                        req_deads = int(float(val_str) * multiplier)
                    except ValueError:
                        req_deads = 0
                    
                if req_kp == 0 and req_deads == 0:
                    continue
                    
                requirements.append({
                    'min_power': min_power,
                    'max_power': max_power,
                    'required_kills': req_kp,
                    'required_deaths': req_deads
                })
                
            except Exception as e:
                logger.error(f"Error parsing line '{line}': {e}")
                continue
                
        return requirements

class WizardRequirementsModal(discord.ui.Modal, title="Wizard: Set Requirements"):
    requirements_text = discord.ui.TextInput(
        label="Paste Requirements Text",
        style=discord.TextStyle.paragraph,
        placeholder="100M - 150M Power\n100M Kills / 1M deads\n...",
        required=True,
        max_length=2000
    )

    def __init__(self, kvk_name, admin_cog):
        super().__init__()
        self.kvk_name = kvk_name
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        from .views import WizardConfirmationView
        text = self.requirements_text.value
        # Reuse parsing logic
        dummy_modal = RequirementsModal(self.admin_cog)
        parsed_reqs = dummy_modal.parse_requirements(text)
        
        if not parsed_reqs:
            await interaction.response.send_message("❌ Could not parse requirements. Please try again.", ephemeral=False)
            return

        if db_manager.save_requirements_batch(self.kvk_name, parsed_reqs):
            embed = discord.Embed(title="Step 3: Confirmation", description="Review your settings.", color=discord.Color.blue())
            embed.add_field(name="Selected Season", value=self.kvk_name, inline=False)
            embed.add_field(name="Requirements", value=f"✅ {len(parsed_reqs)} brackets parsed", inline=False)
            
            await interaction.response.edit_message(embed=embed, view=WizardConfirmationView(self.kvk_name, len(parsed_reqs), self.admin_cog))
        else:
            await interaction.response.send_message("❌ Database error.", ephemeral=False)

class GlobalRequirementsModal(discord.ui.Modal, title="Set Global Stats Requirements"):
    requirements_text = discord.ui.TextInput(
        label="Paste Requirements Text",
        style=discord.TextStyle.paragraph,
        placeholder="100M - 150M Power\n100M Kills / 1M deads\n...",
        required=True,
        max_length=2000
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        text = self.requirements_text.value
        # Reuse parsing logic
        dummy_modal = RequirementsModal(self.admin_cog)
        parsed_reqs = dummy_modal.parse_requirements(text)
        
        if not parsed_reqs:
            await interaction.response.send_message("❌ Could not parse requirements.", ephemeral=False)
            return

        import json
        reqs_json = json.dumps(parsed_reqs)
        
        if db_manager.set_global_requirements(reqs_json):
            await interaction.response.send_message(f"✅ Global requirements updated ({len(parsed_reqs)} brackets).", ephemeral=False)
            await self.admin_cog.log_to_channel(interaction, "Set Global Requirements", f"Brackets: {len(parsed_reqs)}")
        else:
            await interaction.response.send_message("❌ Database error.", ephemeral=False)
