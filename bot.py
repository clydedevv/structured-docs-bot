#!/usr/bin/env python3
"""
Neutron Docs Telegram Bot

A Telegram bot that provides access to Neutron's documentation via MCP server.
Users can ask natural language questions and get relevant information from the
official Neutron documentation.
"""

import asyncio
import json
import logging
import os
import sys
from typing import List, Dict, Any, Optional

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MCPTelegramBot:
    """Main bot class handling MCP integration and Telegram interactions."""
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.mcp_server_url = os.getenv('MCP_SERVER_URL', 'https://docs.neutron.org/mcp')
        
        if not self.telegram_token:
            raise ValueError("TELEGRAM_TOKEN environment variable is required")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        self.mcp_tools: List[Dict[str, Any]] = []
    
    async def connect_to_mcp(self) -> bool:
        """Connect to MCP server and discover available tools."""
        try:
            logger.info(f"Connecting to MCP server at {self.mcp_server_url}")
            
            # Set up the SearchNeutronDocumentation tool based on your description
            # The MCP server should handle the actual search implementation
            self.mcp_tools = [{
                "name": "SearchNeutronDocumentation",
                "description": "Search across the Neutron Documentation knowledge base to find relevant information, code examples, API references, and guides. Use this tool when you need to answer questions about Neutron Documentation, find specific documentation, understand how features work, or locate implementation details. The search returns contextual content with titles and direct links to the documentation pages.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for Neutron documentation"
                        }
                    },
                    "required": ["query"]
                }
            }]
            
            logger.info(f"Configured {len(self.mcp_tools)} MCP tools")
            return True
                    
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool and return the result."""
        try:
            if tool_name == "SearchNeutronDocumentation":
                query = arguments.get("query", "")
                
                # Make HTTP request to MCP server using proper JSON-RPC format
                async with httpx.AsyncClient() as client:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {
                            "name": "SearchNeutronDocumentation",
                            "arguments": {
                                "query": query
                            }
                        }
                    }
                    
                    headers = {
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "User-Agent": "NeutronDocsBot/1.0"
                    }
                    
                    logger.info(f"Calling MCP server with query: {query}")
                    
                    response = await client.post(
                        self.mcp_server_url,
                        json=payload,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    logger.info(f"MCP response status: {response.status_code}")
                    logger.info(f"MCP response headers: {dict(response.headers)}")
                    logger.info(f"MCP response text: {response.text}")
                    
                    if response.status_code == 200:
                        if not response.text.strip():
                            logger.error("Empty response from MCP server")
                            return "No search results found"
                        
                        # Handle Server-Sent Events format
                        response_text = response.text.strip()
                        if response_text.startswith("event: message\ndata: "):
                            # Extract JSON from SSE format
                            json_part = response_text.replace("event: message\ndata: ", "").strip()
                            try:
                                result = json.loads(json_part)
                                logger.info(f"MCP response parsed from SSE: {result}")
                            except Exception as json_error:
                                logger.error(f"JSON parsing error from SSE: {json_error}")
                                logger.error(f"Extracted JSON part: {json_part}")
                                return "Error parsing search results"
                        else:
                            try:
                                result = response.json()
                                logger.info(f"MCP response parsed: {result}")
                            except Exception as json_error:
                                logger.error(f"JSON parsing error: {json_error}")
                                logger.error(f"Raw response: {response.text}")
                                return "Error parsing search results"
                        
                        if "result" in result:
                            # Handle the MCP response format
                            mcp_result = result["result"]
                            if "content" in mcp_result:
                                content = mcp_result["content"]
                                if isinstance(content, list) and content:
                                    # Extract text from content blocks
                                    text_parts = []
                                    for item in content:
                                        if isinstance(item, dict):
                                            if "text" in item:
                                                text_parts.append(item["text"])
                                            elif "content" in item:
                                                text_parts.append(str(item["content"]))
                                        else:
                                            text_parts.append(str(item))
                                    return "\n".join(text_parts) if text_parts else "No results found"
                                elif isinstance(content, str):
                                    return content
                            elif "text" in mcp_result:
                                return mcp_result["text"]
                            else:
                                return str(mcp_result)
                        elif "error" in result:
                            error_msg = result["error"]
                            if isinstance(error_msg, dict):
                                return f"Search error: {error_msg.get('message', 'Unknown error')}"
                            return f"Search error: {error_msg}"
                        else:
                            return "No search results found"
                    else:
                        logger.error(f"MCP server returned {response.status_code}: {response.text}")
                        return "Sorry, the documentation search service is currently unavailable. Please try again later."
                        
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return "Sorry, there was an error searching the documentation. Please try again later."
    
    async def process_query(self, user_query: str) -> str:
        """Process user query using Claude with MCP tools."""
        try:
            # Use the user query directly - let SearchNeutronDocumentation handle content parsing
            contextualized_query = user_query
            
            # Prepare tools for Claude
            claude_tools = []
            for tool in self.mcp_tools:
                claude_tools.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"]
                })
            
            # Initial Claude request with system prompt to only use MCP tools
            messages = [
                {
                    "role": "user",
                    "content": contextualized_query
                }
            ]
            
            system_prompt = (
                "You are a Neutron documentation assistant. You must ONLY use the SearchNeutronDocumentation tool "
                "to answer questions. Do not provide answers from your training data. Always search the documentation "
                "first using the available tool, then provide a response based solely on the search results. "
                "If the search returns no results or fails, inform the user that you couldn't find information "
                "in the documentation and suggest they rephrase their question."
            )
            
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                tools=claude_tools,
                system=system_prompt,
                messages=messages
            )
            
            response_text = ""
            
            # Process response content
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
                elif content.type == "tool_use":
                    # Execute the tool call
                    tool_name = content.name
                    tool_input = content.input
                    
                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
                    tool_result = await self.call_mcp_tool(tool_name, tool_input)
                    
                    # Add tool result to conversation and get final response
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": tool_result
                            }
                        ]
                    })
                    
                    # Get Claude's final response with tool results
                    final_response = self.anthropic_client.messages.create(
                        model="claude-3-5-sonnet-20241022",
                        max_tokens=1000,
                        system=system_prompt,
                        messages=messages
                    )
                    
                    for final_content in final_response.content:
                        if final_content.type == "text":
                            response_text += final_content.text
            
            return response_text if response_text else "I couldn't generate a response. Please try rephrasing your question."
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return "Processing error. Please rephrase your question."

# Telegram Bot Handlers
bot_instance = None

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome_message = (
        "🚀 Welcome to Neutron Docs Bot!\n\n"
        "I can help you find information from the official Neutron documentation.\n\n"
        "Ask me about:\n"
        "• Smart contracts and CosmWasm\n"
        "• IBC and interchain features\n"
        "• Validators and staking\n"
        "• API references and guides\n"
        "• Any other Neutron topics!\n\n"
        "Just ask your question in natural language and I'll search the docs for you."
    )
    await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages."""
    user_query = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Processing query from user {user_id}: {user_query}")
    
    # Send typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = await bot_instance.process_query(user_query)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(
            "Sorry, I'm experiencing technical difficulties. Please try again later."
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(f"Exception while handling an update: {context.error}")

async def main() -> None:
    """Main function to run the bot."""
    global bot_instance
    logger.info("Starting Neutron Docs Telegram Bot...")
    
    # Create bot instance
    bot_instance = MCPTelegramBot()
    
    # Connect to MCP server
    if not await bot_instance.connect_to_mcp():
        logger.error("Failed to connect to MCP server. Exiting.")
        sys.exit(1)
    
    # Create Telegram application
    application = Application.builder().token(bot_instance.telegram_token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    logger.info("Bot is starting with polling...")
    
    # Run the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
