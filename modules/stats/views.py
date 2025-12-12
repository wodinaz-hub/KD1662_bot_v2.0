"""
UI Components for stats module.
Contains all Discord UI classes: Modals, Views, Buttons, Selects.
"""
import discord
from database import database_manager as db_manager


class LinkAccountModal(discord.ui.Modal, title="Link Account"):
    player_id = discord.ui.TextInput(
        label="Player ID",
        placeholder="12345678",
        required=True,
        min_length=5,
        max_length=15
    )

    def __init__(self, account_type, stats_cog):
        super().__init__()
        self.account_type = account_type
        self.stats_cog = stats_cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            p_id = int(self.player_id.value)
        except ValueError:
            await interaction.response.send_message("❌ Player ID must be a number.", ephemeral=True)
            return

        discord_id = interaction.user.id
        success = db_manager.link_account(discord_id, p_id, self.account_type)

        if success:
            await interaction.response.send_message(
                f"✅ Game ID `{p_id}` successfully linked as **{self.account_type.capitalize()}**.", ephemeral=True)
            await self.stats_cog.log_to_channel(interaction, "Link Account", f"ID: {p_id}\nType: {self.account_type}")
        else:
            await interaction.response.send_message(
                "❌ An error occurred while linking the account. Please try again.", ephemeral=True)
            await self.stats_cog.log_to_channel(interaction, "Link Account Failed", f"ID: {p_id}\nType: {self.account_type}")


class LinkAccountView(discord.ui.View):
    def __init__(self, stats_cog):
        super().__init__(timeout=60)
        self.stats_cog = stats_cog

    @discord.ui.button(label="Link Main", style=discord.ButtonStyle.primary)
    async def link_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkAccountModal("main", self.stats_cog))

    @discord.ui.button(label="Link Alt", style=discord.ButtonStyle.secondary)
    async def link_alt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkAccountModal("alt", self.stats_cog))

    @discord.ui.button(label="Link Farm", style=discord.ButtonStyle.secondary)
    async def link_farm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LinkAccountModal("farm", self.stats_cog))


class UnlinkAccountSelect(discord.ui.Select):
    def __init__(self, accounts, stats_cog):
        options = [
            discord.SelectOption(
                label=f"{acc['account_type'].capitalize()}: {acc['player_id']}",
                value=str(acc['player_id']),
                description=f"Type: {acc['account_type']}"
            ) for acc in accounts
        ]
        super().__init__(placeholder="Select account to unlink...", options=options)
        self.stats_cog = stats_cog

    async def callback(self, interaction: discord.Interaction):
        player_id = int(self.values[0])
        if db_manager.unlink_account(interaction.user.id, player_id):
            await interaction.response.edit_message(content=f"✅ Account `{player_id}` unlinked.", view=None)
            await self.stats_cog.log_to_channel(interaction, "Unlink Account", f"ID: {player_id}")
        else:
            await interaction.response.edit_message(content="❌ Failed to unlink account.", view=None)
            await self.stats_cog.log_to_channel(interaction, "Unlink Account Failed", f"ID: {player_id}")


class UnlinkAccountView(discord.ui.View):
    def __init__(self, accounts, stats_cog):
        super().__init__(timeout=60)
        self.add_item(UnlinkAccountSelect(accounts, stats_cog))


class PeriodSelectView(discord.ui.View):
    """View with period selection dropdown and account buttons."""
    def __init__(self, accounts, current_kvk, periods, stats_cog):
        super().__init__(timeout=120)
        self.accounts = accounts
        self.current_kvk = current_kvk
        self.stats_cog = stats_cog
        self.selected_period = "all"
        
        # Add period dropdown
        unique_periods = list(set([p['period_key'] for p in periods]))
        period_options = [discord.SelectOption(label="📊 All Periods", value="all", description="Total stats across all periods", default=True)]
        
        for period_key in sorted(unique_periods):
            period_options.append(
                discord.SelectOption(
                    label=f"📅 {period_key}",
                    value=period_key,
                    description=f"Stats for period {period_key}"
                )
            )
        
        select = discord.ui.Select(placeholder="Select Period...", options=period_options, row=0)
        select.callback = self.period_callback
        self.add_item(select)
        
        # Add account buttons
        self._add_account_buttons()
    
    def _add_account_buttons(self):
        """Add account selection buttons."""
        main_accounts = [a for a in self.accounts if a['account_type'] == 'main']
        alt_accounts = [a for a in self.accounts if a['account_type'] == 'alt']
        farm_accounts = [a for a in self.accounts if a['account_type'] == 'farm']
        
        for acc in main_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Main: {acc['player_id']}", discord.ButtonStyle.primary))
        
        for acc in alt_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Alt: {acc['player_id']}", discord.ButtonStyle.secondary))
        
        for acc in farm_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Farm: {acc['player_id']}", discord.ButtonStyle.secondary))
        
        if len(self.accounts) > 1:
            self.add_item(TotalStatsButton())
    
    async def period_callback(self, interaction: discord.Interaction):
        """Handle period selection."""
        select = [child for child in self.children if isinstance(child, discord.ui.Select)][0]
        self.selected_period = select.values[0]
        self.period_key = self.selected_period
        
        # Recreate the view with updated default selection
        periods = []
        unique_periods = list(set([opt.value for opt in select.options if opt.value != "all"]))
        for period_key in unique_periods:
            periods.append({'period_key': period_key})
        
        new_view = PeriodSelectView(self.accounts, self.current_kvk, periods, self.stats_cog)
        new_view.selected_period = self.selected_period
        new_view.period_key = self.selected_period
        
        # Update the dropdown to show selected period
        new_select = [child for child in new_view.children if isinstance(child, discord.ui.Select)][0]
        for opt in new_select.options:
            opt.default = (opt.value == self.selected_period)
        
        period_name = "All Periods" if self.selected_period == "all" else self.selected_period
        await interaction.response.edit_message(content=f"📅 Period selected: **{period_name}**. Now choose an account:", view=new_view)


class KingdomPeriodSelectView(discord.ui.View):
    """View with period selection dropdown for kingdom stats."""
    def __init__(self, current_kvk, periods, stats_cog):
        super().__init__(timeout=120)
        self.current_kvk = current_kvk
        self.stats_cog = stats_cog
        self.selected_period = "all"
        
        # Add period dropdown
        unique_periods = list(set([p['period_key'] for p in periods]))
        period_options = [discord.SelectOption(label="📊 All Periods", value="all", description="Total stats across all periods", default=True)]
        
        for period_key in sorted(unique_periods):
            period_options.append(
                discord.SelectOption(
                    label=f"📅 {period_key}",
                    value=period_key,
                    description=f"Stats for period {period_key}"
                )
            )
        
        select = discord.ui.Select(placeholder="Select Period...", options=period_options, row=0)
        select.callback = self.period_callback
        self.add_item(select)
    
    async def period_callback(self, interaction: discord.Interaction):
        """Handle period selection and show kingdom stats."""
        await interaction.response.defer()
        select = [child for child in self.children if isinstance(child, discord.ui.Select)][0]
        self.selected_period = select.values[0]
        
        # Show kingdom stats for selected period
        await self.stats_cog.kingdom_stats_logic(interaction, self.selected_period)


class MyStatsView(discord.ui.View):
    def __init__(self, accounts, current_kvk, stats_cog, period_key="all"):
        super().__init__(timeout=120)
        self.accounts = accounts
        self.current_kvk = current_kvk
        self.stats_cog = stats_cog
        self.period_key = period_key
        
        # Group accounts by type
        main_accounts = [a for a in accounts if a['account_type'] == 'main']
        alt_accounts = [a for a in accounts if a['account_type'] == 'alt']
        farm_accounts = [a for a in accounts if a['account_type'] == 'farm']
        
        # Add buttons by type with emojis
        for acc in main_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Main: {acc['player_id']}", discord.ButtonStyle.primary))
        
        for acc in alt_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Alt: {acc['player_id']}", discord.ButtonStyle.secondary))
        
        for acc in farm_accounts:
            self.add_item(AccountStatsButton(acc['player_id'], f"Farm: {acc['player_id']}", discord.ButtonStyle.secondary))
            
        # Add Total button if more than one account
        if len(self.accounts) > 1:
            self.add_item(TotalStatsButton())


class AccountStatsButton(discord.ui.Button):
    def __init__(self, player_id, label, style=discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style)
        self.player_id = player_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        period_key = getattr(view, 'period_key', 'all')
        await view.stats_cog.show_player_stats(interaction, self.player_id, view.current_kvk, period_key)


class TotalStatsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Total All Accounts", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        view = self.view
        await view.stats_cog.show_total_stats(interaction, view.accounts, view.current_kvk)


class StartView(discord.ui.View):
    def __init__(self, stats_cog):
        super().__init__(timeout=None)
        self.stats_cog = stats_cog

    @discord.ui.button(label="Link Account", style=discord.ButtonStyle.primary, emoji="🔗")
    async def link_account(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Select account type to link:", view=LinkAccountView(self.stats_cog), ephemeral=True)

    @discord.ui.button(label="My Stats", style=discord.ButtonStyle.success, emoji="📊")
    async def my_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.stats_cog.my_stats_logic(interaction)

    @discord.ui.button(label="Kingdom Stats", style=discord.ButtonStyle.secondary, emoji="🏰")
    async def kingdom_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.stats_cog.kingdom_stats_logic(interaction)

    @discord.ui.button(label="Help", style=discord.ButtonStyle.secondary, emoji="❓")
    async def help_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Help & Manual", description="Here is how to use the bot:", color=discord.Color.blue())
        embed.add_field(name="🔗 Link Account", value="Connect your game account to view stats.", inline=False)
        embed.add_field(name="📊 My Stats", value="Check your personal performance.", inline=False)
        embed.add_field(name="🏰 Kingdom Stats", value="View global kingdom statistics.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
