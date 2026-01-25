# KD1662 Bot v2.1

Discord bot for managing Kingdom vs Kingdom (KvK) statistics and rankings for Rise of Kingdoms.

## ✨ Features

- 📊 **Statistics Tracking**: Track player and kingdom statistics across multiple KvK periods
- 🔗 **Account Linking**: Link Discord users to game accounts (main, alt, farm)
- 📈 **Progress Visualization**: Animated GIFs and stat cards showing player progress
- 🏆 **DKP System**: Dragon Kill Points calculation and leaderboard
- 📋 **Requirements Management**: Set and track kill/death requirements by power tier
- 📸 **Snapshot System**: Import start/end snapshots for period-based statistics
- 🎯 **Kingdom Stats**: Aggregated kingdom-wide statistics and rankings
- 🏰 **Fort Statistics**: Track fort participation (joined/launched) with auto-scanning and manual upload
- 🔐 **Role-based Admin**: Secure admin commands with role verification

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Discord Server with Administrator permissions

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/KD1662_bot_v2.0.git
cd KD1662_bot_v2.0
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env and add your DISCORD_TOKEN and ADMIN_ROLE_IDS
```

4. **Run the bot:**
```bash
python main.py
```

## 📖 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
DISCORD_TOKEN=your_bot_token_here
ADMIN_ROLE_IDS=role_id_1,role_id_2
LOG_CHANNEL_ID=channel_id_for_logs
```

### Database

The bot uses SQLite database stored in `data/kvk_data.db`. It's created automatically on first run.
 
 ### Deployment & Backups (Railway/Docker)
 
 **Important for Railway/Render Users:**
 To ensure your database persists across deployments (restarts), you **MUST** use a Volume.
 
 1. **Add a Volume** in Railway service settings.
 2. Mount the volume to a path, e.g., `/app/data`.
 3. Set the environment variable `DATA_PATH=/app/data` in Railway.
 
 **Backup Features:**
 - **Automatic Backups**: The bot sends a backup of the database to the `LOG_CHANNEL_ID` every 24 hours.
 - **Manual Backup**: Use `/admin_backup` to download the database immediately.

## 🎮 Commands

### User Commands

- `/start` - Display welcome message and bot information
- `/link_account` - Link your Discord account to a game account
- `/unlink_account` - Unlink a game account
- `/my_stats` - View your statistics (main, alt, farm, or combined)
- `/kingdom_stats` - View kingdom-wide statistics
- `/fort_stats` - View your fort participation statistics

### Admin Commands

- `/set_kvk` - Set the current active KvK season
- `/upload_snapshot` - Upload start/end snapshot Excel file
- `/upload_stats` - Upload player statistics Excel file
- `/set_requirements` - Set kill/death requirements by power tier
- `/calculate_period` - Calculate statistics for a period
- `/finish_kvk` - Archive current KvK and prepare for new season
- `/dkp_leaderboard` - Display DKP rankings
- `/export_leaderboard` - Export leaderboard to Excel
- `/check_compliance` - Check player compliance with requirements
- `/admin_backup` - Download a backup of the database
- `/fort_downloads` - Scan channel history for fort stats files
- `!fort_upload` - (Prefix command) Upload fort stats file manually

## 📁 Project Structure

```
KD1662_bot_v2.0/
├── main.py                 # Bot entry point
├── database/
│   └── database_manager.py # Database operations
├── modules/
│   ├── admin.py           # Admin commands
│   ├── forts/             # Fort stats module
│   │   └── cog.py         # Fort commands
│   └── stats/             # Stats module
│       ├── cog.py         # Stats commands
│       ├── views.py       # UI components
│       └── helpers.py     # Helper functions
├── core/
│   └── graphics.py        # Image generation
├── data/                  # SQLite database
├── configs/               # Configuration files
└── temp_uploads/          # Temporary file uploads
```

## 🛠️ Technical Details

### Performance Optimizations (v2.1)

- **Database Indexes**: 7 indexes for 10-100x faster queries
- **Batch Queries**: Single query for multiple accounts (+300% speed)
- **Transaction Support**: Atomic operations with rollback
- **Data Validation**: Import warnings to prevent data loss

### Database Schema

- `kvk_stats` - Player statistics by period
- `kvk_snapshots` - Start/end snapshots
- `kvk_requirements` - Kill/death requirements by power
- `linked_accounts` - Discord-to-game account mappings
- `kvk_settings` - Bot configuration
- `admin_logs` - Admin action logging
- `fort_stats` - Fort participation data

## 📊 Excel File Formats

### Snapshot Upload

Required columns:
- Player ID
- Player Name (optional)
- Power
- Kill Points
- Deaths

### Stats Upload

Required columns:
- Player ID
- T4 Kills
- T5 Kills
- Deaths

### Requirements Upload

Required columns:
- Min Power
- Max Power
- Required Kills (T4+T5)
- Required Deaths

### Fort Stats Upload

Required columns:
- Governor ID (or ID)
- Governor Name (or Name)
- Joined (or Participated)
- Launched (or Captain/Leader)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Database: SQLite3
- Data processing: pandas
- Visualization: matplotlib, Pillow

## 📮 Support

For issues and questions:
- Open an issue on GitHub
- Contact the maintainer

## 🔄 Changelog

### v2.2.0 (2026-01-25)
- 🏰 **Fort Stats Module**: Added comprehensive fort tracking.
- 📥 **Smart Import**: `!fort_upload` and `/fort_downloads` with 7-day history scan.
- 🔄 **KvK Independence**: Fort stats now work without an active KvK season.
- 🛠️ **Database Refactor**: Implemented context managers for better reliability.
- ⚡ **Performance**: Optimized file parsing and database transactions.

### v2.1.0 (2025-12-12)
- ✨ Added database indexes for 10-100x performance improvement
- 🐛 Fixed critical kingdom power aggregation bug
- ⚡ Implemented batch queries for multi-account stats
- 🛡️ Added transaction support with automatic rollback
- 🔒 Added data validation and import warnings
- 🆕 Added helper functions for snapshots and rankings
- 🧹 Code cleanup and optimization

### v2.0.0
- Initial modular architecture
- Complete rewrite with Discord slash commands
- Multi-account support (main, alt, farm)
- Progress visualization with GIFs
- DKP system implementation

---

**Made with ❤️ for Rise of Kingdoms players**
