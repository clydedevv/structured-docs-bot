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
from telegram import Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, InlineQueryHandler, filters, ContextTypes
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
        self.cf_bypass_token = os.getenv('CLOUDFLARE_BYPASS_TOKEN')
        self.claude_model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
        
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
                    "User-Agent": "Mozilla/5.0 (compatible; NeutronDocsBot/1.0)",
                    "Origin": "https://docs.neutron.org",
                    "Referer": "https://docs.neutron.org/"
                }
                
                # Add Cloudflare bypass token if available
                if self.cf_bypass_token:
                    headers["CF-Access-Client-Id"] = self.cf_bypass_token
                
                logger.info(f"Calling MCP server with query: {query}")
                
                # Use httpx synchronously with retry logic
                with httpx.Client() as client:
                    response = client.post(
                        self.mcp_server_url,
                        json=payload,
                        headers=headers,
                        timeout=30.0
                    )
                    
                    # Retry once if we get a 500 error
                    if response.status_code == 500:
                        logger.warning("Got 500 error, retrying in 1 second...")
                        import time
                        time.sleep(1)
                        response = client.post(
                            self.mcp_server_url,
                            json=payload,
                            headers=headers,
                            timeout=30.0
                        )
                    
                    logger.info(f"MCP response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        logger.info(f"Raw MCP response: {response.text[:200]}...")
                        response_text = response.text.strip()
                        if response_text.startswith("event: message\ndata: "):
                            # Extract JSON from SSE format
                            json_part = response_text.replace("event: message\ndata: ", "").strip()
                            try:
                                result = json.loads(json_part)
                                logger.info("MCP response parsed from SSE successfully")
                            except Exception as json_error:
                                logger.error(f"JSON parsing error from SSE: {json_error}")
                                logger.error(f"Failed JSON part: {json_part[:500]}...")
                                return "Error parsing search results"
                        else:
                            try:
                                result = response.json()
                            except Exception as json_error:
                                logger.error(f"JSON parsing error: {json_error}")
                                logger.error(f"Raw response: {response.text[:500]}...")
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
                        logger.error(f"Response headers: {dict(response.headers)}")
                        logger.error(f"Response body: {response.text[:1000]}")
                        
                        if response.status_code == 403:
                            return "Access to documentation search is restricted. The MCP server is blocking our requests."
                        else:
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
                "first using the available tool, then provide a response based solely on the search results.\n\n"
                "IMPORTANT FORMATTING RULES FOR TELEGRAM:\n"
                "- Keep responses concise (max 2-3 paragraphs)\n"
                "- Use *bold* for emphasis (single asterisks only)\n"
                "- Use simple bullet points with • or -\n"
                "- NO markdown headers (no ##, ###, etc.)\n"
                "- NO complex markdown formatting\n"
                "- Use plain text with *bold* and bullet points only\n"
                "- Break up long text into digestible chunks\n"
                "- ALWAYS end with sources using actual clickable links from the search results:\n"
                "  Extract both the Title and Link from each search result\n"
                "  Format as: Learn more: [Title](URL) | [Title](URL)\n"
                "  Example: Learn more: [Opinionated Blockchains](https://docs.neutron.org/concepts/opinionated-blockchains) | [Integrated Architecture](https://docs.neutron.org/concepts/integrated-architecture)"
            )
            
            messages = [{"role": "user", "content": user_query}]
            
            response = self.anthropic_client.messages.create(
                model=self.claude_model,
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
                        model=self.claude_model,
                        max_tokens=1000,
                        system=system_prompt,
                        messages=messages
                    )
                    
                    for final_content in final_response.content:
                        if final_content.type == "text":
                            response_text += final_content.text
            
            if not response_text:
                logger.error("No response text generated by Claude")
                logger.error(f"Original response content: {[str(content) for content in response.content]}")
                return "I couldn't generate a response. Please try rephrasing your question."
            
            return response_text
            
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
    message = update.message
    user_query = message.text
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # In group chats, only respond if bot is mentioned or replied to
    if chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        is_mentioned = f"@{bot_username}" in user_query if bot_username else False
        is_reply_to_bot = (
            message.reply_to_message and 
            message.reply_to_message.from_user.id == context.bot.id
        )
        
        if not (is_mentioned or is_reply_to_bot):
            return  # Don't respond in groups unless mentioned or replied to
        
        # Remove bot mention from query
        if is_mentioned and bot_username:
            user_query = user_query.replace(f"@{bot_username}", "").strip()
    
    logger.info(f"Processing query from user {user_id} in {chat_type}: {user_query}")
    
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    
    try:
        response = bot_instance.process_query(user_query)
        
        # Truncate very long responses for Telegram
        if len(response) > 4000:
            response = response[:3900] + "...\n\n*Response truncated. Ask a more specific question for details.*"
        
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(
            "Sorry, I'm experiencing technical difficulties. Please try again later."
        )

async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries (@botname query)."""
    query = update.inline_query.query.strip()
    
    if not query:
        # Show help text when no query
        results = [
            InlineQueryResultArticle(
                id="help",
                title="Ask about Neutron documentation",
                description="Type your question after @neutronDocsBot",
                input_message_content=InputTextMessageContent(
                    message_text="Ask me about Neutron documentation! For example:\n• What is integrated architecture?\n• How do smart contracts work?\n• What are interchain queries?"
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=300)
        return
    
    user_id = update.effective_user.id
    logger.info(f"Processing inline query from user {user_id}: {query}")
    
    try:
        # Get response from bot
        response = bot_instance.process_query(query)
        
        # Truncate for inline results
        if len(response) > 1000:
            response = response[:900] + "...\n\n*Ask in private chat for full details.*"
        
        results = [
            InlineQueryResultArticle(
                id="answer",
                title=f"Answer: {query}",
                description=response[:100] + "..." if len(response) > 100 else response,
                input_message_content=InputTextMessageContent(
                    message_text=response,
                    parse_mode='Markdown'
                )
            )
        ]
        
        await update.inline_query.answer(results, cache_time=60)
        
    except Exception as e:
        logger.error(f"Error handling inline query: {e}")
        results = [
            InlineQueryResultArticle(
                id="error",
                title="Error processing query",
                description="Please try again or ask in private chat",
                input_message_content=InputTextMessageContent(
                    message_text="Sorry, I couldn't process that query. Please try asking in a private chat with me."
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=30)

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
        application.add_handler(InlineQueryHandler(handle_inline_query))
        application.add_error_handler(error_handler)
        
        logger.info("Bot is starting with polling...")
        
        # This should work without event loop issues
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
