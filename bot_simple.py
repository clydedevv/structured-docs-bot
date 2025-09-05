#!/usr/bin/env python3
"""
Simple Neutron Docs Telegram Bot - No async conflicts
"""

import json
import logging
import os
import sys
from typing import List, Dict, Any

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

class SimpleMCPBot:
    """Simple bot class without complex async handling."""
    
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        self.mcp_server_url = os.getenv('MCP_SERVER_URL', 'https://docs.neutron.org/mcp')
        
        if not self.telegram_token:
            raise ValueError("TELEGRAM_TOKEN environment variable is required")
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")
        
        self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)
        
        # Set up the SearchNeutronDocumentation tool
        self.mcp_tools = [{
            "name": "SearchNeutronDocumentation",
            "description": "Search across the Neutron Documentation knowledge base to find relevant information, code examples, API references, and guides.",
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
    
    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call an MCP tool and return the result - synchronous version."""
        try:
            if tool_name == "SearchNeutronDocumentation":
                query = arguments.get("query", "")
                
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
                
                # Use httpx synchronously
                with httpx.Client() as client:
                    response = client.post(
                        self.mcp_server_url,
                        json=payload,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    logger.info(f"MCP response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        response_text = response.text.strip()
                        if response_text.startswith("event: message\ndata: "):
                            # Extract JSON from SSE format
                            json_part = response_text.replace("event: message\ndata: ", "").strip()
                            try:
                                result = json.loads(json_part)
                                logger.info("MCP response parsed from SSE successfully")
                            except Exception as json_error:
                                logger.error(f"JSON parsing error from SSE: {json_error}")
                                return "Error parsing search results"
                        else:
                            try:
                                result = response.json()
                            except Exception as json_error:
                                logger.error(f"JSON parsing error: {json_error}")
                                return "Error parsing search results"
                        
                        if "result" in result:
                            mcp_result = result["result"]
                            if "content" in mcp_result:
                                content = mcp_result["content"]
                                if isinstance(content, list) and content:
                                    text_parts = []
                                    for item in content:
                                        if isinstance(item, dict) and "text" in item:
                                            text_parts.append(item["text"])
                                    return "\n".join(text_parts) if text_parts else "No results found"
                            return str(mcp_result)
                        else:
                            return "No search results found"
                    else:
                        logger.error(f"MCP server returned {response.status_code}")
                        return "Sorry, the documentation search service is currently unavailable."
                        
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            return "Sorry, there was an error searching the documentation."
    
    def process_query(self, user_query: str) -> str:
        """Process user query using Claude with MCP tools - synchronous version."""
        try:
            claude_tools = []
            for tool in self.mcp_tools:
                claude_tools.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"]
                })
            
            system_prompt = (
                "You are a Neutron documentation assistant. You must ONLY use the SearchNeutronDocumentation tool "
                "to answer questions. Do not provide answers from your training data. Always search the documentation "
                "first using the available tool, then provide a response based solely on the search results."
            )
            
            messages = [{"role": "user", "content": user_query}]
            
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                tools=claude_tools,
                system=system_prompt,
                messages=messages
            )
            
            response_text = ""
            
            for content in response.content:
                if content.type == "text":
                    response_text += content.text
                elif content.type == "tool_use":
                    tool_name = content.name
                    tool_input = content.input
                    
                    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
                    tool_result = self.call_mcp_tool(tool_name, tool_input)
                    
                    messages.append({
                        "role": "assistant",
                        "content": response.content
                    })
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": tool_result
                        }]
                    })
                    
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

# Global bot instance
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
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    try:
        response = bot_instance.process_query(user_query)
        await update.message.reply_text(response)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(
            "Sorry, I'm experiencing technical difficulties. Please try again later."
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors caused by Updates."""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Main function - completely synchronous."""
    global bot_instance
    
    logger.info("Starting Simple Neutron Docs Telegram Bot...")
    
    try:
        # Create bot instance
        bot_instance = SimpleMCPBot()
        
        # Create and run Telegram application
        application = Application.builder().token(bot_instance.telegram_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        logger.info("Bot is starting with polling...")
        
        # This should work without event loop issues
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
