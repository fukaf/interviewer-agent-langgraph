"""
Interview Log Viewer - Review interview sessions with detailed analysis
"""
import streamlit as st
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="Log Viewer", page_icon="📊", layout="wide")

st.title("📊 Interview Log Viewer")
st.markdown("Review and analyze interview session logs with detailed breakdowns")

# Get log directory
LOG_DIR = Path("logs")

def extract_username(session_id: str) -> str:
    """Extract username from session ID (format: interview_username-timestamp)"""
    try:
        # Remove 'interview_' prefix
        if session_id.startswith('interview_'):
            remaining = session_id[10:]  # Remove 'interview_'
            # Split by '-' and get the part before timestamp
            parts = remaining.split('-')
            if len(parts) >= 2:
                # Everything before the last dash (timestamp) is username
                username = '-'.join(parts[:-1])
                return username if username else 'unknown'
        return 'unknown'
    except:
        return 'unknown'

def get_log_sessions() -> List[Dict[str, Any]]:
    """Get all interview sessions with metadata from both JSON and TXT files"""
    sessions = {}
    
    if not LOG_DIR.exists():
        return []
    
    # First, collect all JSON files
    for file in LOG_DIR.glob("*.json"):
        session_id = file.stem
        
        # Try to load JSON for metadata
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            sessions[session_id] = {
                'session_id': session_id,
                'json_file': file,
                'txt_file': file.with_suffix('.txt'),
                'has_json': True,
                'has_txt': file.with_suffix('.txt').exists(),
                'start_time': data.get('start_time', 'Unknown'),
                'end_time': data.get('end_time', 'In Progress'),
                'total_tokens': data.get('total_tokens', 0),
                'llm_provider': data.get('llm_provider', 'Unknown'),
                'prompt_file': data.get('prompt_file', 'Unknown'),
                'topic_file': data.get('topic_file', 'Unknown'),
                'event_count': len(data.get('events', [])),
                'username': extract_username(session_id),
                'data': data
            }
        except Exception:
            # If JSON fails, still add it with basic info
            sessions[session_id] = {
                'session_id': session_id,
                'json_file': file,
                'txt_file': file.with_suffix('.txt'),
                'has_json': True,
                'has_txt': file.with_suffix('.txt').exists(),
                'start_time': 'Unknown',
                'end_time': 'Unknown',
                'total_tokens': 0,
                'llm_provider': 'Unknown',
                'event_count': 0,
                'username': extract_username(session_id),
                'data': None
            }
    
    # Second, collect TXT files that don't have corresponding JSON
    for file in LOG_DIR.glob("*.txt"):
        session_id = file.stem
        
        # Skip if we already have this session from JSON
        if session_id in sessions:
            continue
        
        # Extract basic metadata from filename and first lines of text file
        try:
            with open(file, 'r', encoding='utf-8') as f:
                first_lines = [f.readline() for _ in range(5)]
            
            # Try to extract start time from first line
            start_time = 'Unknown'
            for line in first_lines:
                if 'started' in line.lower() or 'initialized' in line.lower():
                    # Parse timestamp from log line: "2025-11-12 18:06:18 - ..."
                    parts = line.split(' - ')
                    if len(parts) > 0:
                        try:
                            dt = datetime.strptime(parts[0].strip(), '%Y-%m-%d %H:%M:%S')
                            start_time = dt.isoformat()
                        except:
                            pass
                    break
            
            # Count lines as a proxy for events
            with open(file, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f)
            
            sessions[session_id] = {
                'session_id': session_id,
                'json_file': None,
                'txt_file': file,
                'has_json': False,
                'has_txt': True,
                'start_time': start_time,
                'end_time': 'Unknown',
                'total_tokens': 0,
                'llm_provider': 'Unknown',
                'event_count': line_count,  # Use line count as proxy
                'username': extract_username(session_id),
                'data': None  # No JSON data available
            }
        except Exception:
            # Failed to read txt file, add minimal info
            sessions[session_id] = {
                'session_id': session_id,
                'json_file': None,
                'txt_file': file,
                'has_json': False,
                'has_txt': True,
                'start_time': 'Unknown',
                'end_time': 'Unknown',
                'total_tokens': 0,
                'llm_provider': 'Unknown',
                'event_count': 0,
                'username': extract_username(session_id),
                'data': None
            }
    
    # Sort by start time (newest first)
    sorted_sessions = sorted(
        sessions.values(),
        key=lambda x: x['start_time'] if x['start_time'] != 'Unknown' else '',
        reverse=True
    )
    
    return sorted_sessions

def parse_text_log(log_text: str) -> Dict[str, Any]:
    """Parse text log file to extract structured information using bracket notation"""
    import re
    lines = log_text.split('\n')
    
    parsed_data = {
        'timeline_events': [],  # Unified timeline with all events
        'errors': [],
        'agents': set(),
        'total_tokens': 0,
        'llm_calls': 0,
        'start_time': None,
        'end_time': None
    }
    
    for line in lines:
        if not line.strip():
            continue
        
        # Parse timestamp and basic info
        parts = line.split(' - ')
        if len(parts) >= 4:
            timestamp = parts[0].strip()
            logger_name = parts[1].strip()
            level = parts[2].strip()
            message = ' - '.join(parts[3:])
            
            # Track start/end times
            if not parsed_data['start_time']:
                parsed_data['start_time'] = timestamp
            parsed_data['end_time'] = timestamp
            
            # Detect event type using brackets
            event_type = 'general'
            event_data = {}
            
            if '[agent_start]' in message:
                event_type = 'agent_start'
                agent_match = re.search(r'"agent":\s*"([^"]+)"', message)
                if agent_match:
                    agent_name = agent_match.group(1)
                    event_data['agent'] = agent_name
                    parsed_data['agents'].add(agent_name)
            
            elif '[agent_end]' in message:
                event_type = 'agent_end'
                agent_match = re.search(r'"agent":\s*"([^"]+)"', message)
                if agent_match:
                    event_data['agent'] = agent_match.group(1)
                # Extract question if present
                question_match = re.search(r'"question":\s*"([^"]+)"', message)
                if question_match:
                    event_data['question'] = question_match.group(1)
            
            elif '[llm_request]' in message:
                event_type = 'llm_request'
                parsed_data['llm_calls'] += 1
                
                agent_match = re.search(r'"agent":\s*"([^"]+)"', message)
                if agent_match:
                    event_data['agent'] = agent_match.group(1)
                
                length_match = re.search(r'"prompt_length":\s*(\d+)', message)
                if length_match:
                    event_data['prompt_length'] = int(length_match.group(1))
                
                # Extract prompt - handle escaped content
                prompt_match = re.search(r'"prompt":\s*"((?:[^"\\]|\\.)*)"', message)
                if prompt_match:
                    # Unescape the prompt content
                    prompt_text = prompt_match.group(1)
                    # Replace common escape sequences
                    prompt_text = prompt_text.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                    event_data['prompt'] = prompt_text
            
            elif '[llm_response]' in message:
                event_type = 'llm_response'
                
                agent_match = re.search(r'"agent":\s*"([^"]+)"', message)
                if agent_match:
                    event_data['agent'] = agent_match.group(1)
                
                tokens_match = re.search(r'"tokens":\s*(\d+)', message)
                if tokens_match:
                    tokens = int(tokens_match.group(1))
                    event_data['tokens'] = tokens
                    parsed_data['total_tokens'] += tokens
                
                length_match = re.search(r'"response_length":\s*(\d+)', message)
                if length_match:
                    event_data['response_length'] = int(length_match.group(1))
                
                # Extract response - handle JSON strings with escaped content
                # Find the "response": field and extract until the next top-level field or end
                response_match = re.search(r'"response":\s*"((?:[^"\\]|\\.)*)"', message)
                if response_match:
                    # Unescape the response content
                    response_text = response_match.group(1)
                    # Replace common escape sequences
                    response_text = response_text.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
                    event_data['response'] = response_text
            
            elif '[user_input]' in message:
                event_type = 'user_input'
                
                question_match = re.search(r'"question":\s*"([^"]+)"', message)
                if question_match:
                    event_data['question'] = question_match.group(1)
                
                answer_match = re.search(r'"answer":\s*"([^"]+)"', message)
                if answer_match:
                    event_data['answer'] = answer_match.group(1)
                
                length_match = re.search(r'"answer_length":\s*(\d+)', message)
                if length_match:
                    event_data['answer_length'] = int(length_match.group(1))
            
            elif '[security_check]' in message:
                event_type = 'security_check'
                passed_match = re.search(r'"passed":\s*(true|false)', message)
                if passed_match:
                    event_data['passed'] = passed_match.group(1) == 'true'
                
                feedback_match = re.search(r'"feedback":\s*"([^"]*)"', message)
                if feedback_match:
                    event_data['feedback'] = feedback_match.group(1)
            
            elif '[routing]' in message:
                event_type = 'routing'
                from_match = re.search(r'"from":\s*"([^"]+)"', message)
                to_match = re.search(r'"to":\s*"([^"]+)"', message)
                reason_match = re.search(r'"reason":\s*"([^"]+)"', message)
                if from_match:
                    event_data['from'] = from_match.group(1)
                if to_match:
                    event_data['to'] = to_match.group(1)
                if reason_match:
                    event_data['reason'] = reason_match.group(1)
            
            # Collect errors
            if level in ['ERROR', 'WARNING']:
                parsed_data['errors'].append({
                    'timestamp': timestamp,
                    'level': level,
                    'message': message
                })
            
            # Add to unified timeline
            parsed_data['timeline_events'].append({
                'timestamp': timestamp,
                'level': level,
                'event_type': event_type,
                'message': message,
                'data': event_data
            })
    
    return parsed_data

def display_parsed_text_view(log_text: str):
    """Display parsed text log with structured timeline view"""
    st.subheader("📋 Parsed Log View")
    
    parsed = parse_text_log(log_text)
    
    # Summary statistics
    st.markdown("### 📊 Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Events", len(parsed['timeline_events']))
    with col2:
        st.metric("LLM Calls", parsed['llm_calls'])
    with col3:
        st.metric("Total Tokens", parsed['total_tokens'])
    with col4:
        st.metric("Agents", len(parsed['agents']))
    
    # Time range
    if parsed['start_time'] and parsed['end_time']:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Start Time", parsed['start_time'])
        with col2:
            st.metric("End Time", parsed['end_time'])
    
    # Agents involved
    if parsed['agents']:
        st.markdown("**Agents Involved:**")
        agent_cols = st.columns(len(parsed['agents']))
        for idx, agent in enumerate(sorted(parsed['agents'])):
            with agent_cols[idx]:
                st.info(f"🤖 {agent}")
    
    st.divider()
    
    # Errors and Warnings (if any)
    if parsed['errors']:
        with st.expander(f"🚨 Errors & Warnings ({len(parsed['errors'])})", expanded=False):
            for error in parsed['errors']:
                if error['level'] == 'ERROR':
                    st.error(f"**{error['timestamp']}** - {error['message']}")
                else:
                    st.warning(f"**{error['timestamp']}** - {error['message']}")
        st.divider()
    
    # Event Timeline
    st.markdown("### 📅 Event Timeline")
    
    # Filter options
    col1, col2 = st.columns([1, 1])
    with col1:
        event_types = sorted(set(e['event_type'] for e in parsed['timeline_events']))
        selected_types = st.multiselect(
            "Filter by event type",
            options=event_types,
            default=event_types,
            key="parsed_event_type_filter"
        )
    with col2:
        levels = sorted(set(e['level'] for e in parsed['timeline_events']))
        selected_levels = st.multiselect(
            "Filter by log level",
            options=levels,
            default=levels,
            key="parsed_level_filter"
        )
    
    # Apply filters
    filtered_events = [
        e for e in parsed['timeline_events']
        if e['event_type'] in selected_types and e['level'] in selected_levels
    ]
    
    st.caption(f"Showing {len(filtered_events)} of {len(parsed['timeline_events'])} events")
    
    # Display events in timeline
    for event in filtered_events:
        display_timeline_event(event)

def display_timeline_event(event: Dict[str, Any]):
    """Display a single timeline event with appropriate formatting"""
    timestamp = event['timestamp']
    event_type = event['event_type']
    level = event['level']
    data = event['data']
    
    # Event type icons and colors
    event_icons = {
        'agent_start': '🟢',
        'agent_end': '🔵',
        'llm_request': '📤',
        'llm_response': '📥',
        'user_input': '👤',
        'security_check': '🔒',
        'routing': '🔀',
        'general': '📝'
    }
    
    icon = event_icons.get(event_type, '📝')
    
    # Create expander title
    title_parts = [icon, event_type.upper().replace('_', ' ')]
    if 'agent' in data:
        title_parts.append(f"- {data['agent']}")
    title_parts.append(f"- {timestamp}")
    
    with st.expander(' '.join(title_parts), expanded=False):
        # Display based on event type
        if event_type == 'agent_start':
            st.markdown(f"**Agent:** `{data.get('agent', 'unknown')}`")
            st.caption("Agent execution started")
        
        elif event_type == 'agent_end':
            st.markdown(f"**Agent:** `{data.get('agent', 'unknown')}`")
            if 'question' in data:
                st.markdown("**Generated Question:**")
                st.markdown(data['question'])
            st.caption("Agent execution completed")
        
        elif event_type == 'llm_request':
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Agent", data.get('agent', 'unknown'))
            with col2:
                st.metric("Prompt Length", f"{data.get('prompt_length', 0)} chars")
            
            if 'prompt' in data and data['prompt']:
                st.markdown("**Prompt:**")
                st.markdown(data['prompt'])
        
        elif event_type == 'llm_response':
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Agent", data.get('agent', 'unknown'))
            with col2:
                st.metric("Tokens", data.get('tokens', 0))
            with col3:
                st.metric("Length", f"{data.get('response_length', 0)} chars")
            
            if 'response' in data and data['response']:
                st.markdown("**Response:**")
                response_text = data['response']
                
                # Try to parse as JSON for better display
                try:
                    # Check if response contains JSON (starts with { or [, or has ```json)
                    if response_text.strip().startswith('{') or response_text.strip().startswith('['):
                        parsed_json = json.loads(response_text)
                        st.json(parsed_json)
                    elif '```json' in response_text.lower():
                        # Extract JSON from markdown code block
                        import re
                        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
                        if json_match:
                            parsed_json = json.loads(json_match.group(1))
                            st.json(parsed_json)
                            # Show full text if there's content outside JSON
                            if response_text.replace(json_match.group(0), '').strip():
                                st.markdown("**Full Response:**")
                                st.markdown(response_text)
                        else:
                            raise ValueError("Not valid JSON")
                    else:
                        raise ValueError("Not JSON")
                except:
                    # Not JSON, display as markdown
                    st.markdown(response_text)
        
        elif event_type == 'user_input':
            if 'question' in data:
                st.markdown("**Question:**")
                st.markdown(data['question'])
            
            if 'answer' in data:
                st.markdown("**User Answer:**")
                st.markdown(data['answer'])
                if 'answer_length' in data:
                    st.caption(f"Length: {data['answer_length']} characters")
        
        elif event_type == 'security_check':
            passed = data.get('passed', False)
            if passed:
                st.success("✅ Security check passed")
            else:
                st.error("❌ Security check failed")
            
            if 'feedback' in data and data['feedback']:
                st.markdown("**Feedback:**")
                st.markdown(data['feedback'])
        
        elif event_type == 'routing':
            st.markdown(f"**From:** `{data.get('from', 'unknown')}`")
            st.markdown(f"**To:** `{data.get('to', 'unknown')}`")
            if 'reason' in data:
                st.markdown(f"**Reason:** {data['reason']}")
        
        else:
            # General event - show raw message
            st.code(event['message'], language='text')

def parse_timestamp(ts_str: str) -> str:
    """Parse ISO timestamp to friendly format"""
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts_str

def display_event(event: Dict[str, Any], index: int):
    """Display a single event with nice formatting"""
    event_type = event.get('event_type', 'unknown')
    timestamp = parse_timestamp(event.get('timestamp', 'Unknown'))
    data = event.get('data', {})
    
    # Color coding by event type
    colors = {
        'agent_start': '🟢',
        'agent_end': '🔵',
        'llm_request': '📤',
        'llm_response': '📥',
        'user_input': '👤',
        'security_check': '🔒',
        'error': '🔴'
    }
    
    icon = colors.get(event_type, '⚪')
    
    with st.expander(f"{icon} **{event_type.upper()}** - {timestamp}", expanded=False):
        if event_type == 'agent_start':
            st.markdown(f"**Agent:** `{data.get('agent', 'unknown')}`")
            if 'state' in data:
                state = data['state']
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Topic Index", state.get('current_topic_index', 0))
                with col2:
                    st.metric("Iteration", state.get('topic_iteration_count', 0))
                with col3:
                    st.metric("Complete", "✅" if state.get('interview_complete') else "⏳")
        
        elif event_type == 'agent_end':
            st.markdown(f"**Agent:** `{data.get('agent', 'unknown')}`")
            if 'output' in data:
                st.json(data['output'])
        
        elif event_type == 'llm_request':
            agent = data.get('agent', 'unknown')
            prompt_length = data.get('prompt_length', 0)
            
            st.markdown(f"**Agent:** `{agent}`")
            st.markdown(f"**Prompt Length:** {prompt_length} characters")
            
            # Show prompt directly with markdown
            if 'prompt' in data and data['prompt']:
                st.markdown("**Prompt:**")
                st.markdown(data['prompt'])
        
        elif event_type == 'llm_response':
            agent = data.get('agent', 'unknown')
            response = data.get('response', '')
            tokens = data.get('tokens', 0)
            response_length = data.get('response_length', 0)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Agent", agent)
            with col2:
                st.metric("Tokens", tokens)
            with col3:
                st.metric("Length", response_length)
            
            st.markdown("**Response:**")
            
            # Try to parse as JSON for better display
            try:
                # Check if response contains JSON
                if response.strip().startswith('{') or response.strip().startswith('['):
                    parsed_json = json.loads(response)
                    st.json(parsed_json)
                elif '```json' in response.lower():
                    # Extract JSON from markdown code block
                    import re
                    json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
                    if json_match:
                        parsed_json = json.loads(json_match.group(1))
                        st.json(parsed_json)
                        # Show full text if there's content outside JSON
                        if response.replace(json_match.group(0), '').strip():
                            st.markdown("**Full Response:**")
                            st.markdown(response)
                    else:
                        raise ValueError("Not valid JSON")
                else:
                    raise ValueError("Not JSON")
            except:
                # Not JSON, display as markdown
                st.markdown(response)
            
            # Show metadata if available
            if 'metadata' in data:
                with st.expander("Response Metadata", expanded=False):
                    st.json(data['metadata'])
        
        elif event_type == 'user_input':
            # Show the question that was asked
            if 'question' in data:
                st.markdown("**Question:**")
                st.markdown(data['question'])
                st.divider()
            
            st.markdown("**User Answer:**")
            st.markdown(data.get('answer', 'N/A'))
            
            if 'answer_length' in data:
                st.caption(f"Length: {data['answer_length']} characters")
        
        elif event_type == 'security_check':
            passed = data.get('passed', False)
            if passed:
                st.success("✅ Security check passed")
            else:
                st.error("❌ Security check failed")
            
            if 'feedback' in data and data['feedback']:
                st.markdown("**Feedback:**")
                st.markdown(data['feedback'])
        
        elif event_type == 'error':
            st.error(f"**Error Type:** {data.get('error_type', 'Unknown')}")
            st.markdown(f"**Message:** {data.get('error_message', 'N/A')}")
        
        else:
            # Generic display for unknown events
            st.json(data)

def display_conversation_flow(events: List[Dict[str, Any]]):
    """Display conversation as a timeline"""
    st.subheader("💬 Conversation Timeline")
    
    questions = []
    agents = []
    answers = []
    
    for event in events:
        event_type = event.get('event_type', '')
        data = event.get('data', {})
        
        if event_type == 'agent_end' and 'output' in data:
            output = data['output']
            if 'question' in output:
                questions.append(output['question'])
                # Extract agent name from the event
                agents.append(data.get('agent', 'unknown'))
        
        if event_type == 'user_input':
            answers.append(data.get('answer', ''))
    
    # Check if we have any conversation data
    if not questions and not answers:
        st.info("ℹ️ No conversation recorded in this session")
        return
    
    # Handle mismatched lengths
    max_len = max(len(questions), len(answers))
    
    if len(questions) != len(answers):
        st.warning(f"⚠️ Conversation incomplete: {len(questions)} questions, {len(answers)} answers")
    
    # Display Q&A pairs (using max length, fill missing with placeholders)
    for i in range(max_len):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if i < len(questions):
                # Add agent name if available
                agent_label = f" [{agents[i]}]" if i < len(agents) else ""
                st.markdown(f"**Q{i+1}:{agent_label}** {questions[i]}")
            else:
                st.markdown(f"**Q{i+1}:** *(No question recorded)*")
        
        with col2:
            if i < len(answers):
                st.markdown(f"**A{i+1}:** {answers[i]}")
            else:
                st.markdown(f"**A{i+1}:** *(No answer recorded)*")
        
        st.divider()

def display_statistics(data: Dict[str, Any]):
    """Display session statistics"""
    st.subheader("📈 Session Statistics")
    
    events = data.get('events', [])
    
    # Count event types
    event_counts = {}
    for event in events:
        event_type = event.get('event_type', 'unknown')
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Events", len(events))
    with col2:
        st.metric("Total Tokens", data.get('total_tokens', 0))
    with col3:
        st.metric("LLM Provider", data.get('llm_provider', 'Unknown'))
    with col4:
        duration = "Unknown"
        if data.get('start_time') and data.get('end_time'):
            try:
                start = datetime.fromisoformat(data['start_time'])
                end = datetime.fromisoformat(data['end_time'])
                duration = str(end - start).split('.')[0]  # Remove microseconds
            except:
                pass
        st.metric("Duration", duration)
    
    # Event type breakdown
    st.markdown("**Event Breakdown:**")
    cols = st.columns(len(event_counts))
    for idx, (event_type, count) in enumerate(event_counts.items()):
        with cols[idx]:
            st.metric(event_type.replace('_', ' ').title(), count)

# Sidebar for log selection
with st.sidebar:
    st.header("📁 Select Log Session")
    
    sessions = get_log_sessions()
    
    if not sessions:
        st.warning("⚠️ No log files found in logs/ folder")
        st.stop()
    
    # Extract all unique usernames
    all_usernames = sorted(set(s['username'] for s in sessions))
    
    # Username filter
    st.subheader("👤 Filter by User")
    selected_username = st.selectbox(
        "Select user",
        options=["All Users"] + all_usernames,
        key="username_filter"
    )
    
    # Filter sessions by username
    if selected_username != "All Users":
        filtered_sessions = [s for s in sessions if s['username'] == selected_username]
    else:
        filtered_sessions = sessions
    
    if not filtered_sessions:
        st.warning(f"⚠️ No sessions found for user: {selected_username}")
        st.stop()
    
    st.caption(f"Showing {len(filtered_sessions)} of {len(sessions)} sessions")
    st.divider()
    
    # Create options for selectbox
    session_options = {}
    for session in filtered_sessions:
        start_time = parse_timestamp(session['start_time']) if session['start_time'] != 'Unknown' else 'Unknown'
        
        # Add indicator for text-only sessions
        if not session['has_json']:
            label = f"📄 {start_time} ({session['event_count']} lines) [TEXT ONLY]"
        else:
            label = f"{start_time} ({session['event_count']} events)"
        
        session_options[label] = session
    
    selected_label = st.selectbox(
        "Choose a session",
        options=list(session_options.keys()),
        key="session_selector"
    )
    
    selected_session = session_options[selected_label]
    
    st.divider()
    
    # Show session info
    st.subheader("ℹ️ Session Info")
    st.markdown(f"**👤 User:** `{selected_session['username']}`")
    st.markdown(f"**Session ID:** `{selected_session['session_id']}`")
    st.markdown(f"**Start:** {parse_timestamp(selected_session['start_time'])}")
    st.markdown(f"**End:** {parse_timestamp(selected_session['end_time']) if selected_session['end_time'] != 'In Progress' else '⏳ In Progress'}")
    
    # Show configuration files if available
    if selected_session['has_json'] and selected_session['data']:
        prompt_file = selected_session['data'].get('prompt_file')
        topic_file = selected_session['data'].get('topic_file')
        
        if prompt_file:
            st.markdown(f"**📝 Prompt File:** `{prompt_file}`")
        if topic_file:
            st.markdown(f"**📋 Topic File:** `{topic_file}`")
    
    # Show file availability
    col1, col2 = st.columns(2)
    with col1:
        if selected_session['has_json']:
            st.success("✅ JSON Available")
        else:
            st.warning("⚠️ No JSON")
    with col2:
        if selected_session['has_txt']:
            st.success("✅ TXT Available")
        else:
            st.warning("⚠️ No TXT")
    
    # Only show these if JSON is available
    if selected_session['has_json']:
        st.markdown(f"**Provider:** {selected_session['llm_provider']}")
        st.markdown(f"**Events:** {selected_session['event_count']}")
        st.markdown(f"**Tokens:** {selected_session['total_tokens']}")
    else:
        st.info("ℹ️ Limited metadata - JSON file not saved")
    
    st.divider()
    
    # View mode selection
    st.subheader("👁️ View Mode")
    
    # Adjust available modes based on file availability
    if selected_session['has_json']:
        available_modes = ["Summary", "Conversation", "Events", "Raw JSON", "Raw Text"]
    else:
        available_modes = ["Parsed View", "Raw Text"]
        st.caption("⚠️ Limited views (no JSON)")
    
    view_mode = st.radio(
        "Display style",
        options=available_modes,
        key="view_mode"
    )

# Main content area
if not selected_session['has_json'] and view_mode not in ["Raw Text", "Parsed View"]:
    st.error("❌ This session only has text logs. JSON data was not saved.")
    st.info("💡 Tip: The interview may have been interrupted before completion. Use 'Parsed View' or 'Raw Text' to see the logs.")
    st.stop()

if selected_session['data'] is None and selected_session['has_json']:
    st.error("❌ Unable to load JSON data for this session")
    if selected_session['has_txt']:
        st.info("💡 Try using 'Parsed View' or 'Raw Text' instead")
    st.stop()

data = selected_session.get('data', {})

# Display based on view mode
if view_mode == "Parsed View":
    # Available for text-only sessions
    txt_file = selected_session['txt_file']
    
    if txt_file and txt_file.exists():
        with open(txt_file, 'r', encoding='utf-8') as f:
            log_text = f.read()
        
        display_parsed_text_view(log_text)
    else:
        st.error("❌ Text log file not found")

elif view_mode == "Summary":
    display_statistics(data)
    st.divider()
    display_conversation_flow(data.get('events', []))

elif view_mode == "Conversation":
    display_conversation_flow(data.get('events', []))

elif view_mode == "Events":
    st.subheader("📋 Event Log")
    
    # Filter options
    col1, col2 = st.columns([3, 1])
    with col1:
        event_types = set(e.get('event_type', 'unknown') for e in data.get('events', []))
        selected_types = st.multiselect(
            "Filter by event type",
            options=sorted(event_types),
            default=sorted(event_types),
            key="event_filter"
        )
    
    # Display filtered events
    events = data.get('events', [])
    filtered_events = [e for e in events if e.get('event_type') in selected_types]
    
    st.caption(f"Showing {len(filtered_events)} of {len(events)} events")
    
    for idx, event in enumerate(filtered_events):
        display_event(event, idx)

elif view_mode == "Raw JSON":
    st.subheader("📄 Raw JSON Data")
    
    # Download button
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    st.download_button(
        label="⬇️ Download JSON",
        data=json_str,
        file_name=f"{selected_session['session_id']}.json",
        mime="application/json"
    )
    
    st.json(data)

elif view_mode == "Raw Text":
    st.subheader("📄 Raw Text Log")
    
    txt_file = selected_session['txt_file']
    
    if txt_file and txt_file.exists():
        with open(txt_file, 'r', encoding='utf-8') as f:
            log_text = f.read()
        
        # Show file info
        line_count = log_text.count('\n')
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Lines", line_count)
        with col2:
            st.metric("File Size", f"{len(log_text)} chars")
        with col3:
            st.metric("Source", "TEXT ONLY" if not selected_session['has_json'] else "With JSON")
        
        # Download button
        st.download_button(
            label="⬇️ Download Text Log",
            data=log_text,
            file_name=f"{selected_session['session_id']}.txt",
            mime="text/plain"
        )
        
        # Enhanced search functionality
        col_search, col_level = st.columns([3, 1])
        with col_search:
            search_term = st.text_input("🔍 Search in log", key="search_text")
        with col_level:
            log_level = st.selectbox(
                "Filter by level",
                options=["All", "INFO", "DEBUG", "WARNING", "ERROR"],
                key="log_level_filter"
            )
        
        # Filter by log level
        lines = log_text.split('\n')
        if log_level != "All":
            lines = [line for line in lines if f" - {log_level} - " in line]
        
        # Then filter by search term
        if search_term:
            matching_lines = [line for line in lines if search_term.lower() in line.lower()]
            st.caption(f"Found {len(matching_lines)} matching lines")
            
            if matching_lines:
                # Group by event type if possible
                if not selected_session['has_json']:
                    st.info("💡 Text-only session - showing raw log lines")
                
                st.code('\n'.join(matching_lines), language='text')
            else:
                st.warning("No matching lines found")
        else:
            if lines:
                st.caption(f"Showing {len(lines)} lines")
                st.code('\n'.join(lines), language='text')
            else:
                st.warning("No log content to display")
    else:
        st.warning("⚠️ Text log file not found")
        if selected_session['has_json']:
            st.info("💡 This session has JSON data. Try other view modes.")
