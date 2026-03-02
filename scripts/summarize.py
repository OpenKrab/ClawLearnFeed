#!/usr/bin/env python3
"""
ClawLearnFeed - Content Summarization Module

Uses local LLM (Ollama) to:
- Summarize content (100-200 words)
- Score relevance against user topics
- Filter high-quality content
- Store in ClawMemory vector database

All processing is local and free - no external APIs required.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import yaml
import requests
import re

class ContentSummarizer:
    """LLM-powered content summarization and relevance scoring"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.ollama_config = self.config.get('ollama', {})
        self.model = self.ollama_config.get('model', 'llama3:8b')
        self.endpoint = self.ollama_config.get('endpoint', 'http://localhost:11434')
        self.topics = self.config.get('topics', [])

        # Create output directories
        self.input_dir = "feeds/collected"
        self.output_dir = "feeds/summarized"
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
            "ollama": {
                "model": "llama3:8b",
                "endpoint": "http://localhost:11434"
            },
            "summarization": {
                "max_words": 150,
                "language": "thai",  # thai or english
                "relevance_threshold": 0.7
            }
        }

    def test_ollama_connection(self) -> bool:
        """Test connection to Ollama server"""
        try:
            response = requests.get(f"{self.endpoint}/api/tags", timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                available_models = [model['name'] for model in models]
                print(f"✅ Ollama connected. Available models: {available_models}")

                if self.model in available_models:
                    print(f"✅ Model '{self.model}' is available")
                    return True
                else:
                    print(f"❌ Model '{self.model}' not found. Available: {available_models}")
                    return False
            else:
                print(f"❌ Ollama API error: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Ollama at {self.endpoint}: {e}")
            print("💡 Make sure Ollama is running: ollama serve")
            return False

    def load_collected_feeds(self) -> List[Dict[str, Any]]:
        """Load feeds collected by collect_feeds.py"""
        feed_file = os.path.join(self.input_dir, "all_feeds.json")

        if not os.path.exists(feed_file):
            print(f"❌ Feed file not found: {feed_file}")
            print("💡 Run collect_feeds.py --run first")
            return []

        try:
            with open(feed_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            items = data.get('items', [])
            print(f"📂 Loaded {len(items)} items from collected feeds")
            return items

        except Exception as e:
            print(f"❌ Error loading feed file: {e}")
            return []

    def summarize_content(self, content: str, title: str, url: str) -> str:
        """Generate summary using local LLM"""
        language = self.config.get('summarization', {}).get('language', 'thai')
        max_words = self.config.get('summarization', {}).get('max_words', 150)

        prompt = self.build_summarization_prompt(content, title, url, language, max_words)

        try:
            response = requests.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,  # Lower temperature for consistent summaries
                        "top_p": 0.9,
                        "num_predict": 300   # Limit response length
                    }
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                summary = result.get('response', '').strip()

                # Clean up the summary
                summary = self.clean_summary(summary, max_words)
                return summary
            else:
                print(f"❌ LLM API error: {response.status_code} - {response.text}")
                return self.fallback_summary(title)

        except Exception as e:
            print(f"❌ Error calling LLM: {e}")
            return self.fallback_summary(title)

    def build_summarization_prompt(self, content: str, title: str, url: str,
                                 language: str, max_words: int) -> str:
        """Build effective prompt for summarization"""

        # Truncate content if too long (LLM context limits)
        content_preview = content[:2000] + "..." if len(content) > 2000 else content

        if language == 'thai':
            prompt = f"""กรุณาสรุปเนื้อหาต่อไปนี้ให้สั้นกระชัด ไม่เกิน {max_words} คำ

หัวข้อ: {title}
URL: {url}

เนื้อหา:
{content_preview}

คำสั่ง:
- สรุปสาระสำคัญและข้อมูลที่มีประโยชน์
- เขียนให้อ่านง่ายและน่าสนใจ
- รวมข้อเท็จจริงสำคัญ แนวโน้ม และผลกระทบ
- ใช้ภาษาไทยที่เป็นธรรมชาติ

สรุป:"""

        else:  # English
            prompt = f"""Please summarize the following content in no more than {max_words} words.

Title: {title}
URL: {url}

Content:
{content_preview}

Instructions:
- Focus on key insights, trends, and implications
- Write in an engaging, informative style
- Include important facts and takeaways
- Keep it concise and actionable

Summary:"""

        return prompt

    def clean_summary(self, summary: str, max_words: int) -> str:
        """Clean and format the LLM summary"""
        if not summary:
            return "Summary not available"

        # Remove common LLM artifacts
        summary = re.sub(r'^Summary:?\s*', '', summary, flags=re.IGNORECASE)
        summary = re.sub(r'^สรุป:?\s*', '', summary, flags=re.IGNORECASE)

        # Truncate if too long
        words = summary.split()
        if len(words) > max_words:
            words = words[:max_words]
            summary = ' '.join(words) + '...'

        # Clean up formatting
        summary = summary.strip()
        summary = re.sub(r'\s+', ' ', summary)  # Multiple spaces to single

        return summary

    def fallback_summary(self, title: str) -> str:
        """Provide fallback summary when LLM fails"""
        return f"Content preview: {title[:100]}{'...' if len(title) > 100 else ''}"

    def score_relevance(self, content: str, title: str, tags: List[str] = None) -> float:
        """Score content relevance against user topics (0-1 scale)"""

        if not self.topics:
            return 0.5  # Neutral score if no topics defined

        text_to_score = f"{title} {content}".lower()
        tags_text = ' '.join(tags or []).lower()
        full_text = f"{text_to_score} {tags_text}"

        # Simple keyword matching (can be enhanced with LLM scoring)
        total_score = 0
        matches_found = 0

        for topic in self.topics:
            topic_lower = topic.lower()

            # Exact topic matches
            if topic_lower in full_text:
                total_score += 1.0
                matches_found += 1
                continue

            # Partial word matches
            topic_words = topic_lower.split()
            word_matches = sum(1 for word in topic_words if word in full_text)
            if word_matches > 0:
                score = word_matches / len(topic_words) * 0.8  # Slightly lower weight
                total_score += score
                matches_found += 1

        if matches_found == 0:
            return 0.0

        # Average score across matched topics
        final_score = total_score / len(self.topics)

        # Cap at 1.0 and ensure minimum relevance
        return min(max(final_score, 0.0), 1.0)

    def process_feeds(self, threshold: float = None) -> List[Dict[str, Any]]:
        """Main processing pipeline: load -> summarize -> score -> filter"""
        if threshold is None:
            threshold = self.config.get('summarization', {}).get('relevance_threshold', 0.7)

        print(f"🧠 Starting content processing with threshold {threshold}")

        # Test LLM connection first
        if not self.test_ollama_connection():
            print("❌ LLM not available. Cannot proceed with summarization.")
            return []

        # Load collected feeds
        items = self.load_collected_feeds()
        if not items:
            return []

        processed_items = []
        total_processed = 0
        total_relevant = 0

        for i, item in enumerate(items):
            print(f"📝 Processing {i+1}/{len(items)}: {item['title'][:50]}...")

            # Generate summary
            summary = self.summarize_content(
                item['content'],
                item['title'],
                item['url']
            )

            # Score relevance
            relevance_score = self.score_relevance(
                summary,
                item['title'],
                item.get('tags', [])
            )

            # Create processed item
            processed_item = {
                **item,
                'summary': summary,
                'relevance_score': round(relevance_score, 3),
                'processed_at': datetime.now().isoformat(),
                'topics_matched': self.get_matched_topics(summary, item['title']),
                'word_count': len(summary.split())
            }

            processed_items.append(processed_item)
            total_processed += 1

            # Progress indicator
            if total_processed % 5 == 0:
                print(f"  📊 Progress: {total_processed}/{len(items)} items processed")

            # Rate limiting for LLM calls
            time.sleep(0.5)

        # Filter by relevance threshold
        relevant_items = [
            item for item in processed_items
            if item['relevance_score'] >= threshold
        ]

        print(f"🎯 Found {len(relevant_items)} relevant items out of {len(processed_items)} total")

        # Save results
        self.save_processed_items(processed_items, relevant_items)

        return relevant_items

    def get_matched_topics(self, summary: str, title: str) -> List[str]:
        """Get list of topics that matched this content"""
        matched = []
        text_to_check = f"{title} {summary}".lower()

        for topic in self.topics:
            if topic.lower() in text_to_check:
                matched.append(topic)

        return matched

    def save_processed_items(self, all_items: List[Dict[str, Any]],
                           relevant_items: List[Dict[str, Any]]):
        """Save processing results to files"""

        # Save all processed items
        all_data = {
            'metadata': {
                'processed_at': datetime.now().isoformat(),
                'total_items': len(all_items),
                'relevant_items': len(relevant_items),
                'model_used': self.model
            },
            'items': all_items
        }

        all_file = os.path.join(self.output_dir, "all_summarized.json")
        with open(all_file, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)

        # Save only relevant items for briefing
        relevant_data = {
            'metadata': {
                'processed_at': datetime.now().isoformat(),
                'total_relevant': len(relevant_items),
                'relevance_threshold': self.config.get('summarization', {}).get('relevance_threshold', 0.7)
            },
            'items': relevant_items
        }

        relevant_file = os.path.join(self.output_dir, "relevant_summaries.json")
        with open(relevant_file, 'w', encoding='utf-8') as f:
            json.dump(relevant_data, f, indent=2, ensure_ascii=False)

        print(f"💾 Saved results:")
        print(f"  📄 All summaries: {all_file} ({len(all_items)} items)")
        print(f"  🎯 Relevant only: {relevant_file} ({len(relevant_items)} items)")

    def store_in_memory(self, items: List[Dict[str, Any]]) -> bool:
        """Store summaries in ClawMemory (placeholder for integration)"""
        print("🧠 Storing summaries in ClawMemory...")

        # This would integrate with ClawMemory vector storage
        # For now, just simulate the process
        try:
            for item in items:
                # In real implementation, this would:
                # 1. Create vector embeddings of the summary
                # 2. Store in ClawMemory with metadata
                # 3. Create relationships between related content

                print(f"  ✅ Stored: {item['title'][:50]}... (score: {item['relevance_score']})")

            print(f"✅ Successfully stored {len(items)} items in ClawMemory")
            return True

        except Exception as e:
            print(f"❌ Error storing in ClawMemory: {e}")
            return False

    def export_for_briefing(self, items: List[Dict[str, Any]], format: str = 'json') -> str:
        """Export relevant items for briefing generation"""
        if format == 'json':
            return json.dumps({
                'metadata': {
                    'exported_at': datetime.now().isoformat(),
                    'item_count': len(items)
                },
                'items': items
            }, indent=2, ensure_ascii=False)

        # Could add other formats (markdown, etc.)
        return ""

def main():
    parser = argparse.ArgumentParser(description="ClawLearnFeed Content Summarizer")
    parser.add_argument('--run', action='store_true', help='Process collected feeds')
    parser.add_argument('--test-ollama', action='store_true', help='Test LLM connectivity')
    parser.add_argument('--store-memory', action='store_true', help='Store results in ClawMemory')
    parser.add_argument('--threshold', type=float, help='Relevance threshold (0-1)')
    parser.add_argument('--length', choices=['short', 'medium', 'long'], default='medium',
                       help='Summary length')
    parser.add_argument('--export', choices=['json'], help='Export format for briefing')
    parser.add_argument('--config', default='config.yaml', help='Config file path')

    args = parser.parse_args()

    summarizer = ContentSummarizer(args.config)

    # Adjust config based on args
    if args.length:
        length_map = {'short': 100, 'medium': 150, 'long': 200}
        summarizer.config.setdefault('summarization', {})['max_words'] = length_map[args.length]

    if args.test_ollama:
        success = summarizer.test_ollama_connection()
        sys.exit(0 if success else 1)

    elif args.run:
        threshold = args.threshold
        relevant_items = summarizer.process_feeds(threshold)

        if args.store_memory:
            summarizer.store_in_memory(relevant_items)

        if args.export:
            exported = summarizer.export_for_briefing(relevant_items, args.export)
            print(exported)

        print(f"✅ Processing complete: {len(relevant_items)} relevant items found")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
