import discord

class FortLeaderboardPaginationView(discord.ui.View):
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
            leaderboard_text += f"   🏰 Total: **{player['total_forts']}** | ⚔️ Joined: {player['forts_joined']} | 🚀 Launched: {player['forts_launched']}\n"
            
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
