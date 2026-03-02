# ClawLearnFeed Feedback Processing Template

## Feedback Entry Format

**ID**: FB-{timestamp}
**Source**: {telegram|discord|manual}
**Timestamp**: {iso_timestamp}
**Message**: "{original_user_message}"

**Extracted Commands**:
{parsed_commands_list}

**Applied Changes**:
- Topic weights updated
- Relevance scores adjusted
- Source preferences modified

## Feedback Commands Reference

### Rating Commands
- `/rate N good` - Mark briefing item N as highly relevant
- `/rate N bad` - Mark briefing item N as not relevant
- `/rate N neutral` - Mark briefing item N as average

### Topic Preferences
- `/boost topic_name` - Increase preference for topic
- `/reduce topic_name` - Decrease preference for topic
- `/skip topic_name` - Significantly reduce topic content

### Source Preferences
- `/more rss` - Increase RSS feed content
- `/more youtube` - Increase YouTube content
- `/less x` - Reduce X/Twitter content

### Search & Query
- `/query "search terms"` - Search historical content
- `/trends` - Show content trend analysis

## Learning Algorithm

Topic weights are adjusted using:
```
new_weight = old_weight + (learning_rate × feedback_signal)
```

Where:
- `learning_rate` = 0.1 (configurable)
- `feedback_signal` = +1 (good), -1 (bad), 0 (neutral)

## Analytics

Weekly reports generated showing:
- Top performing topics
- Content source effectiveness
- User engagement metrics
- Relevance score trends
