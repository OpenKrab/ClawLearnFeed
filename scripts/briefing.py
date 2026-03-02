#!/usr/bin/env python3
"""
ClawLearnFeed - Daily Briefing Generator

Creates formatted daily digests from summarized content and sends to:
- Telegram (webhook)
- Discord (webhook)
- Console (preview/testing)

Supports feedback commands for self-improvement loop.
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import yaml
import requests

class BriefingGenerator:
    """Generate and send daily learning briefings"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.notifications = self.config.get('notifications', {})

        # Input directory from summarizer
        self.input_dir = "feeds/summarized"

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found, using defaults")
            return self.get_default_config()

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "notifications": {
                "telegram_webhook": None,
                "discord_webhook": None
            },
            "briefing": {
                "max_items": 5,
                "language": "thai",
                "include_feedback": True
            }
        }

    def load_relevant_summaries(self) -> List[Dict[str, Any]]:
        """Load relevant summaries from summarizer output"""
        summary_file = os.path.join(self.input_dir, "relevant_summaries.json")

        if not os.path.exists(summary_file):
            print(f"❌ Summary file not found: {summary_file}")
            print("💡 Run summarize.py --run first")
            return []

        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            items = data.get('items', [])
            print(f"📂 Loaded {len(items)} relevant summaries")
            return items

        except Exception as e:
            print(f"❌ Error loading summaries: {e}")
            return []

    def select_top_items(self, items: List[Dict[str, Any]], max_items: int = 5) -> List[Dict[str, Any]]:
        """Select top items for briefing based on relevance score"""
        # Sort by relevance score descending
        sorted_items = sorted(items, key=lambda x: x.get('relevance_score', 0), reverse=True)

        # Take top N items
        selected = sorted_items[:max_items]

        print(f"🎯 Selected top {len(selected)} items for briefing")

        # Group by source for variety
        return self.balance_sources(selected)

    def balance_sources(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Balance items across different sources for variety"""
        source_groups = {}
        for item in items:
            source = item.get('source', 'unknown')
            if source not in source_groups:
                source_groups[source] = []
            source_groups[source].append(item)

        # Take 1-2 items from each source to ensure variety
        balanced = []
        max_per_source = 2

        for source_items in source_groups.values():
            balanced.extend(source_items[:max_per_source])

        # If we have fewer than desired, fill with remaining high-scoring items
        if len(balanced) < len(items):
            remaining = [item for item in items if item not in balanced]
            remaining_sorted = sorted(remaining, key=lambda x: x.get('relevance_score', 0), reverse=True)
            needed = min(len(items) - len(balanced), len(remaining_sorted))
            balanced.extend(remaining_sorted[:needed])

        return balanced[:len(items)]  # Don't exceed original limit

    def generate_briefing_markdown(self, items: List[Dict[str, Any]]) -> str:
        """Generate formatted Markdown briefing"""
        language = self.config.get('briefing', {}).get('language', 'thai')
        today = date.today().strftime("%-d %B %Y")  # e.g., "2 มีนาคม 2026"

        if language == 'thai':
            header = f"🦞 ClawLearnFeed - Daily Digest ({today})"
            footer_feedback = "\n💡 Feedback: /rate 1 good | /rate 1 bad | /skip trading\n🔍 Search past: /query \"LLM agents Thailand\""
        else:
            header = f"🦞 ClawLearnFeed - Daily Digest ({today})"
            footer_feedback = "\n💡 Feedback: /rate 1 good | /rate 1 bad | /skip trading\n🔍 Search past: /query \"LLM agents Thailand\""

        briefing_lines = [header, ""]

        for i, item in enumerate(items, 1):
            title = item.get('title', 'No title')
            summary = item.get('summary', 'No summary')
            url = item.get('url', '')
            source = item.get('source', 'unknown')
            score = item.get('relevance_score', 0)

            # Source emoji mapping
            source_emojis = {
                'rss': '📰',
                'youtube': '📺',
                'x': '🐦',
                'x_placeholder': '🐦'
            }
            emoji = source_emojis.get(source, '📄')

            # Format item
            item_lines = [
                f"{emoji} **{title}**",
                f"  {summary}",
                f"  [อ่านเพิ่มเติม]({url})" if language == 'thai' else f"  [Read more]({url})",
                ""
            ]

            briefing_lines.extend(item_lines)

        # Add footer
        if self.config.get('briefing', {}).get('include_feedback', True):
            briefing_lines.append(footer_feedback)

        return "\n".join(briefing_lines)

    def generate_briefing_json(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate JSON format for programmatic use"""
        return {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'item_count': len(items),
                'language': self.config.get('briefing', {}).get('language', 'thai')
            },
            'items': items
        }

    def preview_briefing(self, format: str = 'markdown') -> str:
        """Generate preview of today's briefing without sending"""
        items = self.load_relevant_summaries()
        if not items:
            return "❌ No summaries available. Run summarize.py --run first."

        selected_items = self.select_top_items(items)

        if format == 'markdown':
            briefing = self.generate_briefing_markdown(selected_items)
            return f"📋 **BRIEFING PREVIEW**\n\n{briefing}"
        elif format == 'json':
            briefing_data = self.generate_briefing_json(selected_items)
            return json.dumps(briefing_data, indent=2, ensure_ascii=False)
        else:
            return "❌ Unsupported format"

    def send_briefing(self, preview_only: bool = False) -> bool:
        """Generate and send briefing to configured channels"""
        items = self.load_relevant_summaries()
        if not items:
            print("❌ No summaries available for briefing")
            return False

        selected_items = self.select_top_items(items)
        briefing_markdown = self.generate_briefing_markdown(selected_items)

        if preview_only:
            print("📋 **BRIEFING PREVIEW (Not Sent)**")
            print("=" * 50)
            print(briefing_markdown)
            print("=" * 50)
            return True

        # Send to configured channels
        success_count = 0

        # Telegram
        telegram_webhook = self.notifications.get('telegram_webhook')
        if telegram_webhook:
            if self.send_to_telegram(briefing_markdown, telegram_webhook):
                print("✅ Sent to Telegram")
                success_count += 1
            else:
                print("❌ Failed to send to Telegram")

        # Discord
        discord_webhook = self.notifications.get('discord_webhook')
        if discord_webhook:
            if self.send_to_discord(briefing_markdown, discord_webhook):
                print("✅ Sent to Discord")
                success_count += 1
            else:
                print("❌ Failed to send to Discord")

        if success_count == 0:
            print("⚠️ No notification channels configured")
            print("💡 Set telegram_webhook or discord_webhook in config.yaml")
            print("\n📋 **BRIEFING CONTENT**")
            print("=" * 50)
            print(briefing_markdown)
            print("=" * 50)

        return success_count > 0

    def send_to_telegram(self, message: str, webhook_url: str) -> bool:
        """Send briefing to Telegram webhook"""
        try:
            # Telegram webhook format
            payload = {
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }

            response = requests.post(webhook_url, json=payload, timeout=10)

            if response.status_code == 200:
                return True
            else:
                print(f"❌ Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error sending to Telegram: {e}")
            return False

    def send_to_discord(self, message: str, webhook_url: str) -> bool:
        """Send briefing to Discord webhook"""
        try:
            # Discord webhook format
            payload = {
                'content': message,
                'username': 'ClawLearnFeed',
                'avatar_url': 'https://raw.githubusercontent.com/openkrab/claw-learnfeed/main/assets/bot-avatar.png'
            }

            response = requests.post(webhook_url, json=payload, timeout=10)

            if response.status_code in [200, 204]:
                return True
            else:
                print(f"❌ Discord API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error sending to Discord: {e}")
            return False

    def test_webhook_connection(self, service: str = None) -> bool:
        """Test connection to notification webhooks"""
        success = True

        if service in [None, 'telegram']:
            telegram_webhook = self.notifications.get('telegram_webhook')
            if telegram_webhook:
                print("🧪 Testing Telegram webhook...")
                test_message = "🧪 ClawLearnFeed Test Message\n\nIf you see this, Telegram integration is working!"
                if self.send_to_telegram(test_message, telegram_webhook):
                    print("✅ Telegram webhook test successful")
                else:
                    print("❌ Telegram webhook test failed")
                    success = False
            else:
                print("⚠️ Telegram webhook not configured")

        if service in [None, 'discord']:
            discord_webhook = self.notifications.get('discord_webhook')
            if discord_webhook:
                print("🧪 Testing Discord webhook...")
                test_message = "🧪 **ClawLearnFeed Test Message**\n\nIf you see this, Discord integration is working!"
                if self.send_to_discord(test_message, discord_webhook):
                    print("✅ Discord webhook test successful")
                else:
                    print("❌ Discord webhook test failed")
                    success = False
            else:
                print("⚠️ Discord webhook not configured")

        return success

    def save_briefing_history(self, briefing_markdown: str, items: List[Dict[str, Any]]):
        """Save briefing to history for debugging and analysis"""
        history_dir = "feeds/history"
        os.makedirs(history_dir, exist_ok=True)

        today = date.today().isoformat()
        history_file = os.path.join(history_dir, f"briefing_{today}.json")

        history_data = {
            'date': today,
            'timestamp': datetime.now().isoformat(),
            'briefing_markdown': briefing_markdown,
            'items': items,
            'item_count': len(items)
        }

        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        print(f"📚 Saved briefing history to {history_file}")

def main():
    parser = argparse.ArgumentParser(description="ClawLearnFeed Daily Briefing Generator")
    parser.add_argument('--send', action='store_true', help='Generate and send briefing')
    parser.add_argument('--preview', action='store_true', help='Preview briefing without sending')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown',
                       help='Preview format')
    parser.add_argument('--test-webhook', action='store_true', help='Test webhook connections')
    parser.add_argument('--test-service', choices=['telegram', 'discord'],
                       help='Test specific service webhook')
    parser.add_argument('--max-items', type=int, default=5, help='Maximum items in briefing')
    parser.add_argument('--config', default='config.yaml', help='Config file path')

    args = parser.parse_args()

    generator = BriefingGenerator(args.config)

    # Override max items if specified
    generator.config.setdefault('briefing', {})['max_items'] = args.max_items

    if args.send:
        success = generator.send_briefing(preview_only=False)
        sys.exit(0 if success else 1)

    elif args.preview:
        preview = generator.preview_briefing(args.format)
        print(preview)

    elif args.test_webhook:
        success = generator.test_webhook_connection(args.test_service)
        sys.exit(0 if success else 1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
