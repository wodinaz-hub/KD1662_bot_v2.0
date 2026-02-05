import discord
from database import database_manager as db_manager

class FortLeaderboardPaginationView(discord.ui.View):
    def __init__(self, data, title, kvk_name, period_key="total"):
        super().__init__(timeout=600)
        self.all_data = data  # Store original unfiltered data
        self.title = title
        self.kvk_name = kvk_name
        self.period_key = period_key
        self.per_page = 10
        self.current_page = 0
        self.selected_type = "all"  # 'all', 'main', 'farm', 'alt'
        self.max_pages = 25
        
        # Get last updated time
        self.last_updated = db_manager.get_fort_last_updated(kvk_name, period_key)
        
        # Load player types once
        self.player_types = db_manager.get_all_player_types()
        
        # Apply initial filter
        self._apply_filter()
        self.update_components()

    def _apply_filter(self):
        """Filters data based on selected account type."""
        if self.selected_type == "all":
            self.data = self.all_data
        else:
            self.data = [
                p for p in self.all_data
                if self.player_types.get(p['player_id'], 'main') == self.selected_type
            ]
        self.total_pages = max(1, (len(self.data) - 1) // self.per_page + 1)
        self.current_page = min(self.current_page, self.total_pages - 1)

    async def on_timeout(self):
        """Disable buttons on timeout."""
        for child in self.children:
            child.disabled = True

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        type_labels = {"all": "All", "main": "Main", "farm": "Farm", "alt": "Alt"}
        type_label = type_labels.get(self.selected_type, "All")

        embed = discord.Embed(
            title=f"{self.title}",
            description=f"Season: **{self.kvk_name}** | Filter: **{type_label}**",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for i, player in enumerate(page_data, start + 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            
            player_name = player.get('player_name', 'Unknown')
            if len(player_name) > 20:
                player_name = player_name[:17] + "..."

            leaderboard_text += f"{medal} **{player_name}**\n"
            leaderboard_text += f"   🏰 Total: **{player['total_forts']}**\n"
            leaderboard_text += f"   ⚔️ Joined: {player['forts_joined']} | ✅ Completed: {player['forts_launched']}\n"
            
            if i < start + len(page_data):
                leaderboard_text += "\n"

        if not leaderboard_text:
            leaderboard_text = "No data available for this filter"

        embed.add_field(name=f"Leaderboard (Page {self.current_page + 1}/{self.total_pages})", value=leaderboard_text, inline=False)
        
        footer_text = f"Total players: {len(self.data)}"
        if self.last_updated:
            try:
                from datetime import datetime
                dt = discord.utils.parse_time(self.last_updated) or datetime.fromisoformat(self.last_updated)
                footer_text += f" | Last Updated: {dt.strftime('%d/%m/%Y %H:%M')}"
            except:
                footer_text += f" | Last Updated: {self.last_updated}"
                
        embed.set_footer(text=footer_text)
        return embed

    def update_components(self):
        self.clear_items()
        
        # Row 0: Account Type Filter Buttons
        for type_key, label, emoji in [("all", "All", "📊"), ("main", "Main", "👤"), ("farm", "Farm", "🌾"), ("alt", "Alt", "🎭")]:
            style = discord.ButtonStyle.primary if self.selected_type == type_key else discord.ButtonStyle.secondary
            btn = discord.ui.Button(label=label, style=style, emoji=emoji, row=0, custom_id=f"type_{type_key}")
            btn.callback = self._create_type_callback(type_key)
            self.add_item(btn)
        
        # Row 1: Navigation
        prev_btn = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, row=1, disabled=(self.current_page == 0))
        prev_btn.callback = self._prev_callback
        self.add_item(prev_btn)
        
        next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, row=1, disabled=(self.current_page == self.total_pages - 1))
        next_btn.callback = self._next_callback
        self.add_item(next_btn)

    def _create_type_callback(self, type_key):
        async def callback(interaction: discord.Interaction):
            self.selected_type = type_key
            self.current_page = 0
            self._apply_filter()
            self.update_components()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        return callback

    async def _prev_callback(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    async def _next_callback(self, interaction: discord.Interaction):
        self.current_page += 1
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class FortStatsView(discord.ui.View):
    def __init__(self, player_id, player_name, current_season, current_period, fort_cog, accounts=None):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.player_name = player_name
        self.selected_season = current_season
        self.selected_period = current_period
        self.fort_cog = fort_cog
        self.accounts = accounts or []
        self.update_components()

    def update_components(self):
        self.clear_items()
        
        # 1. Accounts Selection (Row 0)
        if len(self.accounts) > 1:
            if len(self.accounts) <= 5:
                # Use Buttons for few accounts (quick switch)
                for acc in self.accounts:
                    label = f"{acc['account_type'].capitalize()} ({acc['player_name']})"
                    style = discord.ButtonStyle.primary if acc['player_id'] == self.player_id else discord.ButtonStyle.secondary
                    
                    button = discord.ui.Button(label=label, style=style, custom_id=f"acc_{acc['player_id']}", row=0)
                    button.callback = self.create_account_callback(acc['player_id'], acc['player_name'])
                    self.add_item(button)
                    
                # Add Combined Button for small list
                style = discord.ButtonStyle.primary if self.player_id == -1 else discord.ButtonStyle.success
                btn = discord.ui.Button(label="Total (All)", style=style, row=0, emoji="👥")
                btn.callback = self.create_account_callback(-1, "Combined")
                self.add_item(btn)
            else:
                # Use Select Menu for many accounts (prevents overflow)
                options = []
                # Add "All Accounts" option first
                if len(self.accounts) > 1:
                    is_selected = (self.player_id == -1)
                    options.append(discord.SelectOption(
                        label="Combined (All Accounts)",
                        value="-1",
                        default=is_selected,
                        emoji="👥",
                        description="View aggregated stats"
                    ))
                
                for acc in self.accounts:
                    is_selected = (acc['player_id'] == self.player_id)
                    label = f"{acc['account_type'].capitalize()}: {acc['player_name']}"
                    options.append(discord.SelectOption(
                        label=label, 
                        value=str(acc['player_id']), 
                        default=is_selected,
                        emoji="👤"
                    ))
                
                acc_select = discord.ui.Select(placeholder="Select Account...", options=options[:25], row=0)
                acc_select.callback = self.account_select_callback
                self.add_item(acc_select)

        # 2. Season Select (Row 1)
        seasons = db_manager.get_fort_seasons()
        if seasons:
            season_options = [
                discord.SelectOption(
                    label=f"📁 {s}", 
                    value=s, 
                    default=(s == self.selected_season)
                ) for s in seasons[:25]
            ]
            season_select = discord.ui.Select(placeholder="Select season...", options=season_options, row=1)
            season_select.callback = self.season_callback
            self.add_item(season_select)
            
        # 3. Period Select (Row 2)
        periods = db_manager.get_fort_periods(self.selected_season)
        period_options = [
            discord.SelectOption(
                label="📊 Season Total", 
                value="total", 
                default=(self.selected_period == "total")
            )
        ]
        for p in periods[:24]:
            period_options.append(
                discord.SelectOption(
                    label=f"📅 {p['period_label']}", 
                    value=p['period_key'], 
                    default=(p['period_key'] == self.selected_period)
                )
            )
        
        period_select = discord.ui.Select(placeholder="Select period...", options=period_options, row=2)
        period_select.callback = self.period_callback
        self.add_item(period_select)

    def create_account_callback(self, pid, pname):
        async def callback(interaction: discord.Interaction):
            self.player_id = pid
            self.player_name = pname
            await self.update_message(interaction)
        return callback

    async def account_select_callback(self, interaction: discord.Interaction):
        # Callback for the account select dropdown
        selected_pid = int(interaction.data['values'][0])
        
        if selected_pid == -1:
            self.player_id = -1
            self.player_name = "Combined"
            await self.update_message(interaction)
            return

        # Find player name
        acc = next((a for a in self.accounts if a['player_id'] == selected_pid), None)
        if acc:
            self.player_id = acc['player_id']
            self.player_name = acc['player_name']
            await self.update_message(interaction)

    async def season_callback(self, interaction: discord.Interaction):
        self.selected_season = interaction.data['values'][0]
        self.selected_period = "total"
        await self.update_message(interaction)

    async def period_callback(self, interaction: discord.Interaction):
        self.selected_period = interaction.data['values'][0]
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        if self.player_id == -1:
             embed, file = await self.fort_cog.get_combined_forts_embed_and_file(
                self.accounts, self.selected_season, self.selected_period
             )
        else:
             embed, file = await self.fort_cog.get_my_forts_embed_and_file(
                self.player_id, self.player_name, self.selected_season, self.selected_period
             )
        self.update_components()
        
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)
