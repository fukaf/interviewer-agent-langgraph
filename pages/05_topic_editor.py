"""
Topic CSV Editor - Edit interview topics with structured interface
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(page_title="Topic Editor", page_icon="📚", layout="wide")

st.title("📚 Topic CSV Editor")
st.markdown("Edit interview topics with a user-friendly interface. Save as a new file to avoid conflicts.")

# Default topics directory
TOPICS_DIR = Path("data")

def get_available_topic_files():
    """Get all CSV files in the current directory"""
    csv_files = list(TOPICS_DIR.glob("*.csv"))
    # Filter to only topic-related files
    topic_files = [f for f in csv_files if 'topic' in f.stem.lower() or f.stem == 'topics']
    # If no topic files found, include all CSV files
    if not topic_files:
        topic_files = csv_files
    return sorted(topic_files, key=lambda x: x.name)

def load_topics_csv(file_path: Path) -> pd.DataFrame:
    """Load topics CSV file"""
    try:
        df = pd.read_csv(file_path)
        return df
    except Exception as e:
        st.error(f"❌ Failed to load {file_path.name}: {str(e)}")
        return None

def save_topics_csv(df: pd.DataFrame, file_path: Path):
    """Save topics to CSV file"""
    try:
        df.to_csv(file_path, index=False)
        return True
    except Exception as e:
        st.error(f"❌ Failed to save: {str(e)}")
        return False

def validate_topics_dataframe(df: pd.DataFrame) -> dict:
    """Validate topics dataframe structure"""
    required_columns = ['theme', 'topic', 'example_questions']
    
    validation = {
        'is_valid': True,
        'issues': [],
        'warnings': []
    }
    
    # Check required columns
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        validation['is_valid'] = False
        validation['issues'].append(f"Missing required columns: {', '.join(missing_cols)}")
    
    # Check for empty required fields
    if 'theme' in df.columns and df['theme'].isna().any():
        validation['warnings'].append(f"{df['theme'].isna().sum()} rows have empty theme")
    
    if 'topic' in df.columns and df['topic'].isna().any():
        validation['warnings'].append(f"{df['topic'].isna().sum()} rows have empty topic")
    
    # Check for duplicate topics
    if 'topic' in df.columns:
        duplicates = df[df.duplicated(subset=['topic'], keep=False)]
        if not duplicates.empty:
            validation['warnings'].append(f"{len(duplicates)} duplicate topics found")
    
    return validation

# Sidebar for file selection
with st.sidebar:
    st.header("📁 File Selection")
    
    available_files = get_available_topic_files()
    
    if not available_files:
        st.warning("⚠️ No CSV files found in current directory")
        st.info("💡 You can create a new topics file below")
        selected_file = None
    else:
        # Create file options
        file_options = {f.name: f for f in available_files}
        file_names = list(file_options.keys())
        
        # Initialize session state
        if 'current_topics_file' not in st.session_state:
            st.session_state.current_topics_file = file_names[0] if file_names else None
        
        # File selector
        def on_file_change():
            selected = st.session_state.topics_file_selector
            if selected != st.session_state.current_topics_file:
                st.session_state.current_topics_file = selected
                # Clear edit state
                if 'edited_df' in st.session_state:
                    del st.session_state.edited_df
                # Update new file name to match selected file
                st.session_state.new_file_name = st.session_state.current_topics_file.replace('.csv', '')
                st.session_state.file_name_input = st.session_state.new_file_name
        selected_file_name = st.selectbox(
            "Select topic file to edit",
            options=file_names,
            index=file_names.index(st.session_state.current_topics_file) if st.session_state.current_topics_file in file_names else 0,
            key="topics_file_selector",
            on_change=on_file_change
        )
        
        selected_file = file_options[selected_file_name]
        
        # Show file info
        st.caption(f"📄 Current: `{selected_file.name}`")
        
        # File size
        file_size = selected_file.stat().st_size
        st.caption(f"📏 Size: {file_size:,} bytes")
    
    st.divider()
    
    # File name editor
    st.subheader("💾 Save As")
    
    if 'new_file_name' not in st.session_state:
        st.session_state.new_file_name = selected_file.stem if selected_file else "topics"
    
    new_file_name = st.text_input(
        "File name (without .csv)",
        value=st.session_state.new_file_name,
        key="file_name_input",
        help="Save as a new file to avoid conflicts",
        on_change=on_file_change
    )
    
    # Save button
    if st.button("💾 Save As New File", width="content", type="primary"):
        if 'edited_df' in st.session_state and st.session_state.edited_df is not None:
            new_file_path = TOPICS_DIR / f"{new_file_name}.csv"
            
            if new_file_path.exists() and new_file_path != selected_file:
                st.error(f"❌ File `{new_file_name}.csv` already exists!")
            elif not new_file_name.strip():
                st.error("❌ Please enter a valid file name!")
            else:
                if save_topics_csv(st.session_state.edited_df, new_file_path):
                    st.success(f"✅ Saved as `{new_file_name}.csv`")
                    st.session_state.current_topics_file = f"{new_file_name}.csv"
                    st.rerun()
        else:
            st.warning("⚠️ No changes to save. Edit the topics first.")
    
    st.divider()
    
    # Create new file
    st.subheader("➕ Create New")
    
    if st.button("📄 Create Empty Topics File", use_container_width=True):
        # Create empty dataframe with required columns
        empty_df = pd.DataFrame(columns=['theme', 'topic', 'example_questions'])
        st.session_state.edited_df = empty_df
        st.session_state.new_file_name = "new_topics"
        st.rerun()

# Main content
if selected_file or 'edited_df' in st.session_state:
    # Load or use existing dataframe
    if 'edited_df' not in st.session_state:
        df = load_topics_csv(selected_file)
        if df is not None:
            st.session_state.edited_df = df.copy()
    else:
        df = st.session_state.edited_df
    
    if df is not None:
        # Validation
        validation = validate_topics_dataframe(df)
        
        col_valid, col_stats = st.columns([1, 2])
        
        with col_valid:
            if validation['is_valid']:
                st.success("✅ Valid structure")
            else:
                st.error("❌ Issues found")
                for issue in validation['issues']:
                    st.caption(f"  • {issue}")
        
        with col_stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Topics", len(df))
            with col2:
                st.metric("Themes", df['theme'].nunique() if 'theme' in df.columns else 0)
            with col3:
                st.metric("Columns", len(df.columns))
        
        if validation['warnings']:
            with st.expander("⚠️ Warnings", expanded=False):
                for warning in validation['warnings']:
                    st.warning(warning)
        
        st.divider()
        
        # Tabs for different editing modes
        tab_table, tab_form, tab_preview, tab_raw = st.tabs(["📊 Table Editor", "📝 Form Editor", "👁️ Preview", "🔧 Raw CSV"])
        
        with tab_table:
            st.markdown("### 📊 Edit Topics (Table View)")
            st.caption("Edit cells directly in the table. Changes are saved in memory until you click 'Save As New File'.")
            
            # Data editor
            edited_df = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                column_config={
                    "theme": st.column_config.TextColumn(
                        "Theme",
                        help="Topic category (e.g., Docker, CI/CD)",
                        required=True,
                        width="medium"
                    ),
                    "topic": st.column_config.TextColumn(
                        "Topic",
                        help="Specific topic name",
                        required=True,
                        width="medium"
                    ),
                    "example_questions": st.column_config.TextColumn(
                        "Example Questions",
                        help="Pipe-separated list: Question 1|Question 2|Question 3",
                        width="large"
                    )
                },
                key="topics_data_editor"
            )
            
            # Update session state
            st.session_state.edited_df = edited_df
            
            st.divider()
            st.caption("💡 Tip: Add rows using the '+' button, delete rows with the checkbox + delete key")
            st.caption("📝 Format example questions as: `What is Docker?|How does it work?|What are containers?`")
        
        with tab_form:
            st.markdown("### 📝 Add New Topic (Form)")
            
            with st.form("add_topic_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    new_theme = st.text_input("Theme", placeholder="e.g., Docker")
                    new_topic = st.text_input("Topic", placeholder="e.g., Docker Basics")
                
                with col2:
                    # Get existing themes for suggestions
                    existing_themes = sorted(df['theme'].dropna().unique()) if 'theme' in df.columns else []
                    if existing_themes:
                        st.caption("Existing themes:")
                        st.caption(", ".join(existing_themes))
                
                new_questions = st.text_area(
                    "Example Questions (one per line or pipe-separated)",
                    height=100,
                    placeholder="What is Docker?\nHow does Docker work?\nWhat are the benefits?"
                )
                
                submitted = st.form_submit_button("➕ Add Topic", type="primary", use_container_width=True)
                
                if submitted:
                    if not new_theme or not new_topic:
                        st.error("❌ Theme and Topic are required!")
                    else:
                        # Parse questions
                        if '|' in new_questions:
                            questions_str = new_questions
                        else:
                            questions_list = [q.strip() for q in new_questions.split('\n') if q.strip()]
                            questions_str = '|'.join(questions_list)
                        
                        # Add new row
                        new_row = pd.DataFrame([{
                            'theme': new_theme,
                            'topic': new_topic,
                            'example_questions': questions_str
                        }])
                        
                        st.session_state.edited_df = pd.concat([st.session_state.edited_df, new_row], ignore_index=True)
                        st.success(f"✅ Added topic: {new_topic}")
                        st.rerun()
        
        with tab_preview:
            st.markdown("### 👁️ Preview by Theme")
            
            if 'theme' in df.columns:
                # Group by theme
                themes = sorted(df['theme'].dropna().unique())
                
                for theme in themes:
                    theme_topics = df[df['theme'] == theme]
                    
                    with st.expander(f"🎯 {theme} ({len(theme_topics)} topics)", expanded=False):
                        for idx, row in theme_topics.iterrows():
                            st.markdown(f"**{row['topic']}**")
                            
                            if 'example_questions' in row and pd.notna(row['example_questions']):
                                questions = str(row['example_questions']).split('|')
                                for q in questions:
                                    if q.strip():
                                        st.caption(f"  • {q.strip()}")
                            
                            st.divider()
            else:
                st.info("ℹ️ No theme column found")
        
        with tab_raw:
            st.markdown("### 🔧 Raw CSV View")
            
            # Show raw CSV
            csv_string = df.to_csv(index=False)
            
            st.text_area(
                "CSV Content",
                value=csv_string,
                height=400,
                help="Read-only view of the CSV format",
                disabled=True
            )
            
            # Download button
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_string,
                file_name=f"{st.session_state.new_file_name}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.divider()
            
            # Stats
            st.markdown("**📊 Statistics:**")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Rows", len(df))
            with col2:
                st.metric("Columns", len(df.columns))
            with col3:
                total_questions = 0
                if 'example_questions' in df.columns:
                    for questions in df['example_questions'].dropna():
                        total_questions += len(str(questions).split('|'))
                st.metric("Total Questions", total_questions)
            with col4:
                avg_questions = total_questions / len(df) if len(df) > 0 else 0
                st.metric("Avg Q/Topic", f"{avg_questions:.1f}")

else:
    # No file selected
    st.info("👈 Select a topic file from the sidebar or create a new one")
    
    st.markdown("""
    ## 📚 Topic CSV Editor
    
    This tool helps you create and edit interview topic files with a user-friendly interface.
    
    ### 📋 Required Structure:
    
    Your CSV file must have these columns:
    - **theme**: Category of topics (e.g., "Docker", "CI/CD", "Python")
    - **topic**: Specific topic name (e.g., "Docker Basics", "Container Networking")
    - **example_questions**: Pipe-separated list of questions (e.g., "What is Docker?|How does it work?")
    
    ### ✨ Features:
    
    - **📊 Table Editor**: Edit topics in a spreadsheet-like interface
    - **📝 Form Editor**: Add new topics using a structured form
    - **👁️ Preview**: See topics grouped by theme
    - **🔧 Raw CSV**: View and download the raw CSV format
    - **💾 Save As**: Create new files to avoid overwriting originals
    
    ### 🚀 Getting Started:
    
    1. Select an existing CSV file from the sidebar, or
    2. Click "Create Empty Topics File" to start fresh
    3. Edit topics using the table or form editor
    4. Save as a new file with a descriptive name
    5. Use the new file in the main interview application
    
    ### 💡 Tips:
    
    - **Avoid conflicts**: Always save as a new file when making changes
    - **Example questions**: Separate multiple questions with `|` character
    - **Themes**: Reuse theme names to group related topics
    - **Validation**: Check the validation status at the top of each view
    """)
