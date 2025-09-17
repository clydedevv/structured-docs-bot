# Structured Money Docs Telegram Bot

A Telegram bot that provides access to Structured Money's documentation via a hosted Model Context Protocol (MCP) server. The bot uses Anthropic's Claude LLM to process natural language queries and retrieve relevant information from the official Structured Money documentation.

## Features

- 🤖 Natural language queries about Structured Money documentation
- 🔍 Integration with Structured Money docs via MCP server
- 📚 Access to comprehensive Structured Money knowledge base
- ⚡ Powered by Claude 3.5 Sonnet for intelligent responses
- 🚀 Easy deployment to Heroku or other hosting platforms

## Prerequisites

Before setting up the bot, you'll need:

1. **Telegram Bot Token**: Create a new bot via [@BotFather](https://t.me/BotFather) on Telegram
2. **Anthropic API Key**: Get your API key from [Anthropic Console](https://console.anthropic.com/)
3. **Python 3.10+**: Ensure you have Python 3.10 or higher installed

## Quick Setup

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd structured-bot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example environment file:
```bash
cp env.example .env
```

Edit `.env` and add your credentials:
```env
TELEGRAM_TOKEN=your_telegram_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
MCP_SERVER_URL=https://docs.structured.money/mcp
```

### 4. Run Locally

```bash
python bot_simple.py
```

The bot will start polling for messages. Test it by:
1. Finding your bot on Telegram (search for the bot name you created)
2. Send `/start` to get the welcome message
3. Ask questions like "What is the protocol architecture?" or "How do smart contracts work?"

## Deployment

### Heroku Deployment

1. **Create Heroku App**:
   ```bash
   heroku create your-app-name
   ```

2. **Set Environment Variables**:
   ```bash
   heroku config:set TELEGRAM_TOKEN=your_telegram_bot_token_here
   heroku config:set ANTHROPIC_API_KEY=your_anthropic_api_key_here
   heroku config:set MCP_SERVER_URL=https://docs.structured.money/mcp
   ```

3. **Deploy**:
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push heroku main
   ```

4. **Scale Worker**:
   ```bash
   heroku ps:scale worker=1
   ```

### Alternative Deployments

#### Render.com
1. Connect your GitHub repository
2. Create a new Web Service
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `python bot_simple.py`
5. Add environment variables in the dashboard

#### VPS/Server
1. Clone the repository on your server
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your credentials
4. Run with a process manager like `systemd` or `supervisor`

## Project Structure

```
structured-bot/
├── bot_simple.py       # Main bot implementation
├── requirements.txt    # Python dependencies
├── env.example        # Environment variables template
├── .env               # Your actual environment variables (git-ignored)
├── .gitignore         # Git ignore rules
├── Procfile           # Heroku process configuration
└── README.md          # This file
```

## How It Works

1. **User Interaction**: Users send messages to the Telegram bot
2. **Query Processing**: The query is sent to Claude 3.5 Sonnet with available MCP tools
3. **Documentation Search**: Claude calls the SearchStructuredMoneyDocumentation tool via MCP to find relevant information
4. **Response**: The bot sends back Claude's response with relevant documentation, code examples, and direct links

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_TOKEN` | Bot token from @BotFather | Yes |
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Yes |
| `MCP_SERVER_URL` | MCP server URL (default: https://docs.structured.money/mcp) | No |

## Commands

- `/start` - Welcome message and bot introduction
- Any text message - Processes as a documentation query

## Example Queries

Try asking the bot:
- "What is the Structured Money protocol?"
- "How do smart contracts work?"
- "What are the API endpoints?"
- "How do I integrate with the protocol?"
- "What is the architecture overview?"
- "How do I get started with development?"

## Troubleshooting

### Bot Not Responding
1. Check that your `TELEGRAM_TOKEN` is correct
2. Verify the bot is running (check logs)
3. Ensure your Heroku dyno is scaled to 1 worker

### API Errors
1. Verify your `ANTHROPIC_API_KEY` is valid and has credits
2. Check the MCP server is accessible at the configured URL
3. Review the logs for specific error messages

### Local Development Issues
1. Ensure Python 3.10+ is installed: `python --version`
2. Install dependencies: `pip install -r requirements.txt`
3. Check your `.env` file exists and has the correct format

### Deployment Issues
- **Heroku**: Check `heroku logs --tail` for error messages
- **Render**: Check the deployment logs in the dashboard
- **VPS**: Check system logs and ensure the process is running

## Logging

The bot logs important events to the console:
- Startup and MCP connection status
- User queries and processing
- Errors and exceptions

In production, logs are available through your hosting platform's logging system.

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test locally
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues related to:
- **Bot functionality**: Open an issue in this repository
- **Structured Money documentation**: Visit [docs.structured.money](https://docs.structured.money)
- **General support**: Check official Structured Money channels

---

**Note**: This is an MVP implementation for general Structured Money documentation access. Future versions may include multi-turn conversations, enhanced error handling, and additional features.
