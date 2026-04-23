# Lira — Discord AI Companion Bot

A personal project exploring the OpenAI API by building and deploying a conversational AI bot on Discord.

## About

Lira is a Discord bot powered by OpenAI's GPT-5.1 model. The goal of this project was to recreate a ChatGPT-like conversational experience directly inside Discord, with persistent memory and conversation history.

## Features

- Conversational AI via OpenAI API (GPT-5.1)
- Persistent conversation history per user (JSON-based)
- Long-term memory system — global and user-specific
- Smart context window management (last 40 messages per user)
- Automatic message splitting for Discord's character limit
- 24/7 availability via Railway deployment
- Secure API key management via environment variables

## Tech Stack

- Python
- Discord.py
- OpenAI Python SDK
- Railway (deployment)
- JSON (data persistence)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Create a `.env` file with your keys:
```
OPENAI_API_KEY=your_openai_key
DISCORD_TOKEN=your_discord_token
```
4. Run locally: `python main.py`

## Deployment

This bot is deployed on Railway for continuous 24/7 operation. Environment variables are managed through Railway's built-in configuration.

## Author

Olga Alexandra Nowak — [LinkedIn](https://de.linkedin.com/in/olganowak) · [GitHub](https://github.com/olgaanowak)
