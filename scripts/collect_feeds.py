#!/usr/bin/env python3
"""
ClawLearnFeed - Feed Collection Module

Aggregates content from free sources:
- RSS feeds (XML parsing)
- YouTube RSS feeds
- X/Twitter keyword searches (via OpenClaw tools)

All processing is local and free - no paid APIs required.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import yaml
import requests
import feedparser
from urllib.parse import urljoin, urlparse

class FeedCollector:
    """Main feed collection class for ClawLearnFeed"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.output_dir = "feeds/collected"
        os.makedirs(self.output_dir, exist_ok=True)

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
            "topics": ["AI agents", "LLM", "machine learning"],
            "sources": {
                "rss_feeds": [
                    "https://aiweekly.co/rss",
                    "https://ai.googleblog.com/atom.xml",
                    "https://www.infoq.com/articles/rss"
                ],
                "youtube_channels": [
                    "UCbfYPyITQ-7l4upoX8nvctg"  # Two Minute Papers
                ],
                "x_keywords": ["AI", "machine learning"]
            },
            "max_items_per_feed": 5,
            "days_back": 1
        }

    def collect_all_feeds(self) -> List[Dict[str, Any]]:
        """Collect from all configured sources"""
        all_items = []

        print("🦞 Collecting RSS feeds...")
        rss_items = self.collect_rss_feeds()
        all_items.extend(rss_items)

        print("📺 Collecting YouTube feeds...")
        youtube_items = self.collect_youtube_feeds()
        all_items.extend(youtube_items)

        print("🐦 Collecting X/Twitter content...")
        x_items = self.collect_x_content()
        all_items.extend(x_items)

        # Filter by date (last 24 hours)
        cutoff_date = datetime.now() - timedelta(days=self.config.get('days_back', 1))
        recent_items = [
            item for item in all_items
            if datetime.fromisoformat(item['timestamp']) > cutoff_date
        ]

        print(f"📊 Collected {len(recent_items)} recent items from {len(all_items)} total")

        # Save collected items
        self.save_items(recent_items, "all_feeds.json")

        return recent_items

    def collect_rss_feeds(self) -> List[Dict[str, Any]]:
        """Collect content from RSS feeds"""
        items = []
        rss_feeds = self.config.get('sources', {}).get('rss_feeds', [])

        for feed_url in rss_feeds:
            try:
                print(f"  📡 Fetching {feed_url}")
                feed_items = self.parse_rss_feed(feed_url)
                items.extend(feed_items)

                # Rate limiting - small delay between feeds
                time.sleep(0.5)

            except Exception as e:
                print(f"  ❌ Error fetching {feed_url}: {e}")
                continue

        return items

    def parse_rss_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """Parse RSS/Atom feed and extract items"""
        try:
            response = requests.get(feed_url, timeout=10)
            response.raise_for_status()

            feed = feedparser.parse(response.content)

            items = []
            max_items = self.config.get('max_items_per_feed', 5)

            for entry in feed.entries[:max_items]:
                item = {
                    'id': f"rss_{hash(entry.link) % 1000000}",
                    'source': 'rss',
                    'source_url': feed_url,
                    'url': entry.link,
                    'title': entry.title if hasattr(entry, 'title') else 'No title',
                    'content': self.extract_content(entry),
                    'timestamp': self.parse_timestamp(entry),
                    'tags': self.extract_tags(entry),
                    'author': entry.author if hasattr(entry, 'author') else None
                }
                items.append(item)

            return items

        except Exception as e:
            print(f"Error parsing RSS feed {feed_url}: {e}")
            return []

    def extract_content(self, entry) -> str:
        """Extract content from RSS entry"""
        # Try different content fields
        if hasattr(entry, 'content') and entry.content:
            return entry.content[0].value if isinstance(entry.content, list) else entry.content
        elif hasattr(entry, 'summary'):
            return entry.summary
        elif hasattr(entry, 'description'):
            return entry.description
        else:
            return "No content available"

    def parse_timestamp(self, entry) -> str:
        """Parse publication timestamp"""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            dt = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            dt = datetime(*entry.updated_parsed[:6])
        else:
            dt = datetime.now()

        return dt.isoformat()

    def extract_tags(self, entry) -> List[str]:
        """Extract tags/categories from RSS entry"""
        tags = []

        # Check categories
        if hasattr(entry, 'categories'):
            tags.extend(entry.categories)

        # Check tags
        if hasattr(entry, 'tags'):
            for tag in entry.tags:
                if hasattr(tag, 'term'):
                    tags.append(tag.term)
                elif isinstance(tag, str):
                    tags.append(tag)

        return list(set(tags))  # Remove duplicates

    def collect_youtube_feeds(self) -> List[Dict[str, Any]]:
        """Collect content from YouTube RSS feeds (free, no API key needed)"""
        items = []
        channels = self.config.get('sources', {}).get('youtube_channels', [])

        for channel_id in channels:
            try:
                feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
                print(f"  📺 Fetching YouTube channel {channel_id}")

                channel_items = self.parse_rss_feed(feed_url)

                # Mark as YouTube content
                for item in channel_items:
                    item['source'] = 'youtube'
                    item['channel_id'] = channel_id

                items.extend(channel_items)
                time.sleep(1)  # YouTube rate limiting

            except Exception as e:
                print(f"  ❌ Error fetching YouTube channel {channel_id}: {e}")
                continue

        return items

    def collect_x_content(self) -> List[Dict[str, Any]]:
        """Collect content from X/Twitter using OpenClaw tools (free)"""
        items = []
        keywords = self.config.get('sources', {}).get('x_keywords', [])

        # Note: This would use OpenClaw's x_keyword_search tool
        # For now, we'll create placeholder items for testing
        print("  🐦 X/Twitter collection requires OpenClaw x_keyword_search tool")
        print("  💡 Run this within OpenClaw environment for full functionality")

        # Placeholder for demonstration
        for keyword in keywords:
            item = {
                'id': f"x_{hash(keyword) % 1000000}",
                'source': 'x_placeholder',
                'url': f"https://x.com/search?q={keyword}",
                'title': f"X/Twitter content about: {keyword}",
                'content': f"Placeholder content for X/Twitter search: {keyword}",
                'timestamp': datetime.now().isoformat(),
                'tags': [keyword],
                'keyword': keyword
            }
            items.append(item)

        return items

    def analyze_github_profile(self, username: str) -> List[str]:
        """Analyze GitHub profile to suggest topics"""
        try:
            # This would use OpenClaw's browse_page tool
            print(f"🔍 Analyzing GitHub profile: {username}")

            # Placeholder suggestions based on common interests
            suggestions = [
                "software development",
                "open source",
                "programming"
            ]

            # In real implementation, this would scrape GitHub profile
            # and analyze repos, bio, and activity
            print(f"💡 Suggested topics: {', '.join(suggestions)}")

            return suggestions

        except Exception as e:
            print(f"Error analyzing GitHub profile: {e}")
            return []

    def analyze_twitter_profile(self, username: str) -> List[str]:
        """Analyze X/Twitter profile to suggest topics"""
        try:
            print(f"🔍 Analyzing X/Twitter profile: {username}")

            # Placeholder - would use OpenClaw x_user_search tool
            suggestions = [
                "technology",
                "AI",
                "social media"
            ]

            print(f"💡 Suggested topics: {', '.join(suggestions)}")
            return suggestions

        except Exception as e:
            print(f"Error analyzing X/Twitter profile: {e}")
            return []

    def save_items(self, items: List[Dict[str, Any]], filename: str):
        """Save collected items to JSON file"""
        filepath = os.path.join(self.output_dir, filename)

        # Add metadata
        data = {
            'metadata': {
                'collected_at': datetime.now().isoformat(),
                'total_items': len(items),
                'sources': list(set(item['source'] for item in items))
            },
            'items': items
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved {len(items)} items to {filepath}")

    def check_feed_health(self) -> Dict[str, Any]:
        """Check health of all configured feeds"""
        health_report = {
            'total_feeds': 0,
            'healthy_feeds': 0,
            'failed_feeds': 0,
            'details': []
        }

        # Check RSS feeds
        rss_feeds = self.config.get('sources', {}).get('rss_feeds', [])
        health_report['total_feeds'] += len(rss_feeds)

        for feed_url in rss_feeds:
            try:
                response = requests.head(feed_url, timeout=5)
                is_healthy = response.status_code == 200
                health_report['details'].append({
                    'url': feed_url,
                    'type': 'rss',
                    'healthy': is_healthy,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds()
                })

                if is_healthy:
                    health_report['healthy_feeds'] += 1
                else:
                    health_report['failed_feeds'] += 1

            except Exception as e:
                health_report['failed_feeds'] += 1
                health_report['details'].append({
                    'url': feed_url,
                    'type': 'rss',
                    'healthy': False,
                    'error': str(e)
                })

        # Check YouTube channels
        youtube_channels = self.config.get('sources', {}).get('youtube_channels', [])
        health_report['total_feeds'] += len(youtube_channels)

        for channel_id in youtube_channels:
            feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
            try:
                response = requests.head(feed_url, timeout=5)
                is_healthy = response.status_code == 200
                health_report['details'].append({
                    'url': feed_url,
                    'type': 'youtube',
                    'channel_id': channel_id,
                    'healthy': is_healthy,
                    'status_code': response.status_code if hasattr(response, 'status_code') else None
                })

                if is_healthy:
                    health_report['healthy_feeds'] += 1
                else:
                    health_report['failed_feeds'] += 1

            except Exception as e:
                health_report['failed_feeds'] += 1
                health_report['details'].append({
                    'url': feed_url,
                    'type': 'youtube',
                    'channel_id': channel_id,
                    'healthy': False,
                    'error': str(e)
                })

        return health_report

    def test_functionality(self, source: str = None):
        """Test functionality of feed collection"""
        print("🧪 Testing ClawLearnFeed collection functionality...")

        if source == 'rss' or source is None:
            print("\n📡 Testing RSS feeds...")
            rss_items = self.collect_rss_feeds()
            print(f"  ✅ Collected {len(rss_items)} RSS items")

        if source == 'youtube' or source is None:
            print("\n📺 Testing YouTube feeds...")
            youtube_items = self.collect_youtube_feeds()
            print(f"  ✅ Collected {len(youtube_items)} YouTube items")

        if source == 'x' or source is None:
            print("\n🐦 Testing X/Twitter (placeholder)...")
            x_items = self.collect_x_content()
            print(f"  ✅ Collected {len(x_items)} X/Twitter items")

        print("\n🎯 Test completed!")

def main():
    parser = argparse.ArgumentParser(description="ClawLearnFeed Feed Collector")
    parser.add_argument('--run', action='store_true', help='Execute full collection cycle')
    parser.add_argument('--source', choices=['rss', 'youtube', 'x'], help='Test specific source')
    parser.add_argument('--analyze-github', help='Analyze GitHub profile for topics')
    parser.add_argument('--analyze-twitter', help='Analyze X/Twitter profile for topics')
    parser.add_argument('--health', action='store_true', help='Check feed health')
    parser.add_argument('--test', action='store_true', help='Run functionality tests')
    parser.add_argument('--config', default='config.yaml', help='Config file path')

    args = parser.parse_args()

    collector = FeedCollector(args.config)

    if args.run:
        items = collector.collect_all_feeds()
        print(f"✅ Collection complete: {len(items)} items collected")

    elif args.analyze_github:
        topics = collector.analyze_github_profile(args.analyze_github)
        print(f"📋 Suggested topics from GitHub: {topics}")

    elif args.analyze_twitter:
        topics = collector.analyze_twitter_profile(args.analyze_twitter)
        print(f"📋 Suggested topics from X/Twitter: {topics}")

    elif args.health:
        health = collector.check_feed_health()
        print(f"🏥 Feed Health Report:")
        print(f"  Total feeds: {health['total_feeds']}")
        print(f"  Healthy: {health['healthy_feeds']}")
        print(f"  Failed: {health['failed_feeds']}")

        for detail in health['details'][:5]:  # Show first 5
            status = "✅" if detail.get('healthy') else "❌"
            print(f"    {status} {detail['url']}")

    elif args.test:
        collector.test_functionality(args.source)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
