import discord
from database import database_manager as db_manager

class FortLeaderboardPaginationView(discord.ui.View):
    # ... existing code ...
    def __init__(self, data, title, kvk_name):
        super().__init__(timeout=180)
        self.data = data
        self.title = title
        self.kvk_name = kvk_name
        self.per_page = 10
        self.current_page = 0
        self.total_pages = (len(data) - 1) // self.per_page + 1
        self.update_buttons()

    def create_embed(self):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_data = self.data[start:end]

        embed = discord.Embed(
            title=f"{self.title}",
            description=f"Season: **{self.kvk_name}**",
            color=discord.Color.gold()
        )

        leaderboard_text = ""
        for i, player in enumerate(page_data, start + 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            
            player_name = player.get('player_name', 'Unknown')
            if len(player_name) > 20:
                player_name = player_name[:17] + "..."

            leaderboard_text += f"{medal} **{player_name}**\n"
            leaderboard_text += f"   🏰 Total: **{player['total_forts']}** | ⚔️ Joined: {player['forts_joined']} | ✅ Completed: {player['forts_launched']}\n"
            
            if i < start + len(page_data):
                leaderboard_text += "\n"

        if not leaderboard_text:
            leaderboard_text = "No data available"

        embed.add_field(name=f"Leaderboard (Page {self.current_page + 1}/{self.total_pages})", value=leaderboard_text, inline=False)
        embed.set_footer(text=f"Total players: {len(self.data)}")
        return embed

    def update_buttons(self):
        if len(self.children) >= 2:
            self.children[0].disabled = self.current_page == 0
            self.children[1].disabled = self.current_page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class FortStatsView(discord.ui.View):
    def __init__(self, player_id, player_name, current_season, current_period, fort_cog):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.player_name = player_name
        self.selected_season = current_season
        self.selected_period = current_period
        self.fort_cog = fort_cog
        self.update_components()

    def update_components(self):
        self.clear_items()
        
        # Season Select
        seasons = db_manager.get_fort_seasons()
        if seasons:
            season_options = [
                discord.SelectOption(
                    label=f"📁 {s}", 
                    value=s, 
                    default=(s == self.selected_season)
                ) for s in seasons[:25]
            ]
            season_select = discord.ui.Select(placeholder="Выберите сезон...", options=season_options, row=0)
            season_select.callback = self.season_callback
            self.add_item(season_select)
            
        # Period Select
        periods = db_manager.get_fort_periods(self.selected_season)
        period_options = [
            discord.SelectOption(
                label="📊 Итого за сезон (Total)", 
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
        
        period_select = discord.ui.Select(placeholder="Выберите период...", options=period_options, row=1)
        period_select.callback = self.period_callback
        self.add_item(period_select)

    async def season_callback(self, interaction: discord.Interaction):
        self.selected_season = interaction.data['values'][0]
        self.selected_period = "total"
        await self.update_message(interaction)

    async def period_callback(self, interaction: discord.Interaction):
        self.selected_period = interaction.data['values'][0]
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed, file = await self.fort_cog.get_my_forts_embed_and_file(
            self.player_id, self.player_name, self.selected_season, self.selected_period
        )
        self.update_components()
        
        if file:
            await interaction.response.edit_message(embed=embed, attachments=[file], view=self)
        else:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)
