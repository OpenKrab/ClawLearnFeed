#!/usr/bin/env python3
"""
ClawLearnFeed - Feedback Processing Module

Processes user feedback from daily briefings to improve content relevance:
- Parses feedback commands (/rate, /skip, /query)
- Updates topic weights and preferences
- Logs learning patterns for analysis
- Adjusts future content filtering

Integrates with ClawSelfImprove for persistent learning.
"""

import argparse
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import yaml

class FeedbackProcessor:
    """Process user feedback and update learning preferences"""

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self.load_config(config_path)
        self.feedback_dir = ".learnings"
        self.topics_file = os.path.join(self.feedback_dir, "TOPICS.md")
        self.feedback_file = os.path.join(self.feedback_dir, "FEEDBACK.md")

        # Create directories
        os.makedirs(self.feedback_dir, exist_ok=True)

        # Load current topic weights
        self.topic_weights = self.load_topic_weights()

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
            "feedback": {
                "learning_rate": 0.1,
                "min_weight": 0.1,
                "max_weight": 2.0,
                "decay_factor": 0.95
            }
        }

    def load_topic_weights(self) -> Dict[str, float]:
        """Load current topic weights from file"""
        if os.path.exists(self.topics_file):
            try:
                with open(self.topics_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse weights from markdown
                weights = {}
                lines = content.split('\n')
                for line in lines:
                    if '|' in line and 'weight' in line.lower():
                        # Skip header
                        continue
                    parts = line.split('|')
                    if len(parts) >= 3:
                        topic = parts[1].strip()
                        try:
                            weight = float(parts[2].strip())
                            weights[topic] = weight
                        except (ValueError, IndexError):
                            continue

                if weights:
                    print(f"📊 Loaded {len(weights)} topic weights")
                    return weights

            except Exception as e:
                print(f"❌ Error loading topic weights: {e}")

        # Default weights
        topics = self.config.get('topics', [])
        default_weights = {topic: 1.0 for topic in topics}
        print(f"📊 Using default topic weights: {len(default_weights)} topics")
        return default_weights

    def save_topic_weights(self):
        """Save current topic weights to file"""
        # Generate markdown table
        lines = [
            "# Topic Weights",
            "",
            f"Updated: {datetime.now().isoformat()}",
            "",
            "| Topic | Weight | Last Updated |",
            "|-------|--------|--------------|"
        ]

        for topic, weight in sorted(self.topic_weights.items()):
            lines.append(f"| {topic} | {weight:.2f} | {datetime.now().strftime('%Y-%m-%d')} |")

        lines.extend([
            "",
            "## Weight Guidelines",
            "- **> 1.5**: Highly preferred topics",
            "- **1.0-1.5**: Normal preference",
            "- **0.5-1.0**: Less preferred",
            "- **< 0.5**: Minimally preferred",
            "",
            "## Recent Changes",
            "- Weights updated based on user feedback",
            "- Higher weights = more content from this topic",
            "- Lower weights = less content from this topic"
        ])

        with open(self.topics_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        print(f"💾 Saved topic weights to {self.topics_file}")

    def process_feedback_message(self, message: str) -> Dict[str, Any]:
        """Parse feedback message and extract commands"""
        feedback_data = {
            'timestamp': datetime.now().isoformat(),
            'original_message': message,
            'commands': [],
            'errors': []
        }

        # Common feedback patterns
        patterns = {
            'rate_good': r'/rate\s+(\d+)\s+good',
            'rate_bad': r'/rate\s+(\d+)\s+bad',
            'skip_topic': r'/skip\s+(.+)',
            'query': r'/query\s+"([^"]+)"',
            'feedback': r'ชอบ|ไม่ชอบ|สนใจ|ไม่สนใจ|interesting|not interesting|good|bad'
        }

        # Extract structured commands
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                if pattern_name.startswith('rate'):
                    item_num = int(match)
                    rating = 'good' if 'good' in pattern_name else 'bad'
                    feedback_data['commands'].append({
                        'type': 'rate_item',
                        'item_number': item_num,
                        'rating': rating
                    })
                elif pattern_name == 'skip_topic':
                    feedback_data['commands'].append({
                        'type': 'skip_topic',
                        'topic': match.strip()
                    })
                elif pattern_name == 'query':
                    feedback_data['commands'].append({
                        'type': 'query',
                        'query': match
                    })

        # Extract natural language feedback
        if any(word in message.lower() for word in ['ชอบ', 'ไม่ชอบ', 'สนใจ', 'ไม่สนใจ', 'interesting', 'boring']):
            feedback_data['commands'].append({
                'type': 'natural_feedback',
                'text': message
            })

        return feedback_data

    def apply_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Apply feedback to update topic weights and preferences"""
        learning_rate = self.config.get('feedback', {}).get('learning_rate', 0.1)

        changes_made = False

        for command in feedback_data.get('commands', []):
            cmd_type = command.get('type')

            if cmd_type == 'rate_item':
                # For item ratings, we need to know which item was rated
                # This would be enhanced with actual briefing context
                item_num = command.get('item_number')
                rating = command.get('rating')

                # Placeholder: adjust general preferences
                if rating == 'good':
                    # Boost related topics
                    self.adjust_topic_weights('boost', learning_rate)
                else:
                    # Reduce related topics
                    self.adjust_topic_weights('reduce', learning_rate)

                changes_made = True

            elif cmd_type == 'skip_topic':
                topic = command.get('topic')
                # Reduce weight for skipped topic
                if topic in self.topic_weights:
                    old_weight = self.topic_weights[topic]
                    new_weight = max(
                        self.config.get('feedback', {}).get('min_weight', 0.1),
                        old_weight * (1 - learning_rate)
                    )
                    self.topic_weights[topic] = new_weight
                    print(f"⬇️ Reduced weight for '{topic}': {old_weight:.2f} → {new_weight:.2f}")
                    changes_made = True

            elif cmd_type == 'natural_feedback':
                # Process natural language feedback
                text = command.get('text', '').lower()

                # Simple sentiment analysis
                positive_words = ['ชอบ', 'สนใจ', 'interesting', 'good', 'like']
                negative_words = ['ไม่ชอบ', 'ไม่สนใจ', 'boring', 'bad', 'dislike']

                positive_count = sum(1 for word in positive_words if word in text)
                negative_count = sum(1 for word in negative_words if word in text)

                if positive_count > negative_count:
                    self.adjust_topic_weights('boost', learning_rate * 0.5)
                    changes_made = True
                elif negative_count > positive_count:
                    self.adjust_topic_weights('reduce', learning_rate * 0.5)
                    changes_made = True

        if changes_made:
            self.save_topic_weights()
            self.log_feedback(feedback_data)

        return changes_made

    def adjust_topic_weights(self, direction: str, learning_rate: float):
        """Adjust all topic weights in a direction"""
        min_weight = self.config.get('feedback', {}).get('min_weight', 0.1)
        max_weight = self.config.get('feedback', {}).get('max_weight', 2.0)

        for topic in self.topic_weights:
            old_weight = self.topic_weights[topic]

            if direction == 'boost':
                new_weight = min(max_weight, old_weight * (1 + learning_rate))
            elif direction == 'reduce':
                new_weight = max(min_weight, old_weight * (1 - learning_rate))
            else:
                continue

            if abs(new_weight - old_weight) > 0.01:  # Only log significant changes
                self.topic_weights[topic] = new_weight
                print(f"{'⬆️' if direction == 'boost' else '⬇️'} {topic}: {old_weight:.2f} → {new_weight:.2f}")

    def log_feedback(self, feedback_data: Dict[str, Any]):
        """Log feedback to learning file"""
        # Load existing feedback
        existing_feedback = []
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Parse existing entries (simplified)
                    existing_feedback = content.split('\n## ')[1:] if content else []
            except Exception as e:
                print(f"Warning: Could not load existing feedback: {e}")

        # Create new entry
        entry_id = f"FB-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        commands_summary = [cmd.get('type', 'unknown') for cmd in feedback_data.get('commands', [])]

        entry = f"""## {entry_id}

**Timestamp**: {feedback_data['timestamp']}
**Commands**: {', '.join(commands_summary)}
**Message**: {feedback_data['original_message'][:200]}...

**Applied Changes**: Topic weights updated based on feedback
"""

        # Append to file
        with open(self.feedback_file, 'a', encoding='utf-8') as f:
            f.write(entry + '\n\n')

        print(f"📝 Logged feedback to {self.feedback_file}")

    def decay_weights(self):
        """Apply time decay to topic weights (old preferences fade)"""
        decay_factor = self.config.get('feedback', {}).get('decay_factor', 0.95)

        decayed_count = 0
        for topic in self.topic_weights:
            old_weight = self.topic_weights[topic]
            new_weight = old_weight * decay_factor

            # Don't decay below minimum
            min_weight = self.config.get('feedback', {}).get('min_weight', 0.1)
            new_weight = max(new_weight, min_weight)

            if new_weight != old_weight:
                self.topic_weights[topic] = new_weight
                decayed_count += 1

        if decayed_count > 0:
            self.save_topic_weights()
            print(f"⏰ Decayed {decayed_count} topic weights (factor: {decay_factor})")

    def get_feedback_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get recent feedback history"""
        if not os.path.exists(self.feedback_file):
            return []

        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse entries (simplified)
            entries = []
            sections = content.split('\n## ')[1:]

            for section in sections:
                lines = section.strip().split('\n')
                if len(lines) >= 2:
                    entry_id = lines[0].strip()

                    # Extract timestamp
                    timestamp_line = next((line for line in lines if 'Timestamp' in line), '')
                    timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', timestamp_line)

                    if timestamp_match:
                        timestamp = datetime.fromisoformat(timestamp_match.group(1))

                        # Check if within date range
                        if datetime.now() - timestamp <= timedelta(days=days):
                            entries.append({
                                'id': entry_id,
                                'timestamp': timestamp.isoformat(),
                                'content': section[:300] + '...' if len(section) > 300 else section
                            })

            return sorted(entries, key=lambda x: x['timestamp'], reverse=True)

        except Exception as e:
            print(f"Error reading feedback history: {e}")
            return []

    def generate_analytics_report(self) -> str:
        """Generate analytics report on feedback patterns"""
        history = self.get_feedback_history(days=30)

        if not history:
            return "No feedback history available"

        # Simple analytics
        total_feedback = len(history)
        avg_per_week = total_feedback / 4.0  # Approximate

        # Topic weight distribution
        high_weight = sum(1 for w in self.topic_weights.values() if w > 1.5)
        low_weight = sum(1 for w in self.topic_weights.values() if w < 0.8)

        report = f"""# Feedback Analytics Report

Generated: {datetime.now().isoformat()}

## Summary
- **Total Feedback Entries**: {total_feedback}
- **Average per Week**: {avg_per_week:.1f}
- **Topics Monitored**: {len(self.topic_weights)}
- **High Preference Topics**: {high_weight}
- **Low Preference Topics**: {low_weight}

## Topic Weights
{chr(10).join(f"- {topic}: {weight:.2f}" for topic, weight in sorted(self.topic_weights.items(), key=lambda x: x[1], reverse=True))}

## Recent Activity
{chr(10).join(f"- {entry['timestamp'][:10]}: {entry['id']}" for entry in history[:5])}
"""

        return report

def main():
    parser = argparse.ArgumentParser(description="ClawLearnFeed Feedback Processor")
    parser.add_argument('--process', action='store_true', help='Process pending feedback')
    parser.add_argument('--message', help='Process specific feedback message')
    parser.add_argument('--history', action='store_true', help='Show feedback history')
    parser.add_argument('--decay', action='store_true', help='Apply time decay to weights')
    parser.add_argument('--analytics', action='store_true', help='Generate analytics report')
    parser.add_argument('--update-weights', action='store_true', help='Update and save topic weights')
    parser.add_argument('--config', default='config.yaml', help='Config file path')

    args = parser.parse_args()

    processor = FeedbackProcessor(args.config)

    if args.message:
        print(f"📝 Processing feedback: {args.message}")
        feedback_data = processor.process_feedback_message(args.message)
        print(f"🔍 Extracted commands: {len(feedback_data.get('commands', []))}")

        if processor.apply_feedback(feedback_data):
            print("✅ Applied feedback changes")
        else:
            print("⚠️ No changes applied")

    elif args.process:
        print("🔄 Processing all pending feedback...")
        # In a real implementation, this would check for pending feedback
        # from briefing responses, database, etc.
        print("✅ Feedback processing complete")

    elif args.history:
        history = processor.get_feedback_history()
        print(f"📚 Feedback History ({len(history)} entries):")
        for entry in history[:10]:  # Show last 10
            print(f"  {entry['timestamp'][:10]}: {entry['id']}")

    elif args.decay:
        processor.decay_weights()
        print("✅ Applied weight decay")

    elif args.analytics:
        report = processor.generate_analytics_report()
        print(report)

    elif args.update_weights:
        processor.save_topic_weights()
        print("✅ Updated topic weights")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
