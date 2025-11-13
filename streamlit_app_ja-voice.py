import streamlit as st
from datetime import datetime
from pathlib import Path
from core import create_interview_graph
from core.utils import load_topics_from_csv
from interview_logging.interview_logger import InterviewLogger, set_logger, clear_logger, get_logger
from management.prompt_manager import PromptManager, get_prompt_manager
import os
import pandas as pd
from streamlit_extras.bottom_container import bottom


# Streamlit UI
st.set_page_config(page_title="AI面接エージェント", page_icon="💼", layout="wide")

st.title("💼 従業員知識評価面接")
st.markdown("企業トピックに関する従業員の知識を評価するマルチエージェントシステム")

# セッション状態の初期化
if 'interview_started' not in st.session_state:
    st.session_state.interview_started = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'interview_ended' not in st.session_state:
    st.session_state.interview_ended = False
if 'state' not in st.session_state:
    st.session_state.state = None
if 'graph' not in st.session_state:
    st.session_state.graph = None
if 'logger' not in st.session_state:
    st.session_state.logger = None
if 'last_processed_input' not in st.session_state:
    st.session_state.last_processed_input = None
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'feedback' not in st.session_state:
    st.session_state.feedback = None
if 'feedback_tokens' not in st.session_state:
    st.session_state.feedback_tokens = 0
if 'execution_logs' not in st.session_state:
    st.session_state.execution_logs = []  # 各応答の実行ログを保存

# 音声入力の状態初期化
if 'voice_recording' not in st.session_state:
    st.session_state.voice_recording = False
if 'voice_transcription' not in st.session_state:
    st.session_state.voice_transcription = ""
if 'voice_temp_text' not in st.session_state:
    st.session_state.voice_temp_text = ""
if 'pending_voice_input' not in st.session_state:
    st.session_state.pending_voice_input = None

# サイドバー
with st.sidebar:
    st.header("面接設定")
    
    # ユーザー名入力
    st.subheader("👤 ユーザー情報")
    username = st.text_input(
        "ユーザー名",
        value=st.session_state.get('username', ''),
        placeholder="例: tanaka_taro",
        help="ログファイルの識別に使用されます",
        key="username_input"
    )
    
    # セッション状態にユーザー名を保存
    if username:
        st.session_state.username = username
    
    st.divider()
    
    # プロンプトファイル選択
    st.subheader("📝 プロンプト設定")
    
    pm = get_prompt_manager()
    available_prompts = PromptManager.list_available_prompts()
    
    if available_prompts:
        # 現在のファイルパスを取得
        current_file = str(pm.config_path)
        
        # ファイル名のリストを作成
        prompt_options = {p['file']: p for p in available_prompts}
        prompt_files = list(prompt_options.keys())
        
        # 現在選択されているファイルのインデックスを取得
        current_filename = Path(current_file).name
        try:
            current_index = prompt_files.index(current_filename)
        except ValueError:
            current_index = 0
        
        # セレクトボックスでファイル選択
        selected_file = st.selectbox(
            "プロンプトファイルを選択",
            options=prompt_files,
            index=current_index,
            key="prompt_file_selector"
        )
        
        # 選択されたプロンプトの情報を表示
        selected_info = prompt_options[selected_file]
        
        # メモを表示
        if selected_info['memo']:
            st.info(f"**📌 説明**\n\n{selected_info['memo']}")
        
        # ファイルが変更された場合、プロンプトをリロード
        if selected_file != current_filename:
            try:
                pm.load_from_file(selected_info['path'])
                st.success(f"✅ プロンプトを **{selected_file}** に切り替えました")
                st.rerun()  # 新しいプロンプトを反映するために再読み込み
            except Exception as e:
                st.error(f"❌ プロンプトの読み込みに失敗しました: {str(e)}")
    else:
        st.warning("⚠️ プロンプトフォルダにYAMLファイルが見つかりません")
    
    st.divider()
    
    if not st.session_state.interview_started:
        # LLMプロバイダーの表示
        llm_provider = os.getenv("LLM_PROVIDER", "openai").upper()
        st.info(f"🤖 LLMプロバイダー: **{llm_provider}**")
        
        # トピックファイルの選択
        data_dir = Path("data")
        if data_dir.exists():
            available_files = sorted([f.name for f in data_dir.glob("*.csv")])
            if available_files:
                topics_file_name = st.selectbox(
                    "トピックCSVファイルを選択",
                    options=available_files,
                    key="topics_file_selector"
                )
                topics_file = str(data_dir / topics_file_name)
            else:
                st.warning("⚠️ data/ フォルダにCSVファイルが見つかりません")
                topics_file = "data/topics.csv"
        else:
            st.warning("⚠️ data/ フォルダが見つかりません")
            topics_file = "data/topics.csv"
        
        if os.path.exists(topics_file):
            topics = load_topics_from_csv(topics_file)
            st.success(f"✅ {len(topics)}件のトピックを読み込みました")
        else:
            st.warning("⚠️ トピックファイルが見つかりません")
            topics = load_topics_from_csv(topics_file)
        
        max_iterations = st.number_input("トピックごとの最大フォローアップ数", min_value=1, max_value=10, value=2, step=1)
        max_judge_retries = st.number_input("Judge Agentの最大再試行回数", min_value=0, max_value=10, value=2, step=1,
                                            help="無効な回答に対してJudge Agentが再試行を求める回数。0に設定すると次の質問に直接スキップします。")
        
        if st.button("面接を開始", type="primary"):
            # ユーザー名が入力されているか確認
            if not st.session_state.get('username'):
                st.error("⚠️ ユーザー名を入力してください")
                st.stop()
            
            with st.spinner("マルチエージェントシステムを初期化中..."):
                # ユーザー名をプレフィックスとして一意のセッションIDを生成
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                username_prefix = st.session_state.username.replace(' ', '_').replace('/', '_').replace('\\', '_')
                st.session_state.session_id = f"{username_prefix}-{timestamp}"
                
                # ロガーの初期化
                st.session_state.logger = InterviewLogger(st.session_state.session_id)
                set_logger(st.session_state.logger)
                st.session_state.logger.text_logger.info("Interview session initialized")
                
                # Log configuration files being used
                st.session_state.logger.set_prompt_file(str(pm.config_path))
                st.session_state.logger.set_topic_file(topics_file)
                
                # 状態の初期化
                st.session_state.state = {
                    "topics": topics,
                    "current_topic_index": 0,
                    "current_topic": {},
                    "topic_iteration_count": 0,
                    "max_iterations_per_topic": max_iterations,
                    "judge_retry_count": 0,
                    "max_judge_retries": max_judge_retries,
                    "current_question": "",
                    "user_answer": "",
                    "security_passed": False,
                    "security_feedback": "",
                    "topic_depth_sufficient": False,
                    "topic_feedback": "",
                    "interview_complete": False,
                    "conversation_history": [],
                    "final_feedback": "",
                    "current_agent": "",
                    "total_tokens": 0,
                    "last_message_tokens": 0,
                    "waiting_for_user_input": False  # 中断メカニズムに置き換えられます
                }
                
                # 中断用のチェックポインター付きグラフを作成
                st.session_state.graph = create_interview_graph()
                
                # チェックポイント永続化用のスレッド設定
                config = {"configurable": {"thread_id": st.session_state.session_id}}
                
                # グラフの実行を開始 - HITL（中断）に到達するまで実行
                # グラフフロー: START → topic_agent → human_input_node (INTERRUPT)
                for chunk in st.session_state.graph.stream(st.session_state.state, config):
                    # 各ノードの出力を処理
                    for node_name, node_output in chunk.items():
                        st.session_state.state.update(node_output)
                
                # この時点で、グラフはhuman_input_nodeで中断されています
                # 最初の質問が生成されています
                
                # 最初の質問をメッセージに追加
                if st.session_state.state.get("current_question"):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": st.session_state.state["current_question"],
                        "agent": st.session_state.state.get("current_agent", "Topic Agent"),
                        "tokens": st.session_state.state.get("last_message_tokens", 0)
                    })
                
                st.session_state.interview_started = True
                st.rerun()
    
    else:
        st.success("✅ 面接進行中")
        
        # ユーザー情報の表示
        if st.session_state.get('username'):
            st.info(f"👤 ユーザー: **{st.session_state.username}**")
        
        # 進捗状況の表示
        if st.session_state.state:
            current_idx = st.session_state.state["current_topic_index"]
            total_topics = len(st.session_state.state["topics"])
            st.progress((current_idx + 1) / total_topics)
            st.write(f"トピック {current_idx + 1} / {total_topics}")
            
            if st.session_state.state.get("current_topic"):
                st.info(f"**現在のトピック:**\n{st.session_state.state['current_topic'].get('topic', 'N/A')}")
            
            # トークン使用量
            total_tokens = st.session_state.state.get("total_tokens", 0)
            st.metric("使用トークン合計", total_tokens)
        
        st.divider()
        
        # 面接終了ボタンは、まだ終了していない&フィードバック生成中でない場合のみ表示
        if not st.session_state.interview_ended and not st.session_state.get('generating_feedback', False):
            if st.button("面接を終了してフィードバックを取得", type="secondary", key="end_interview_btn"):
                # 処理前に状態を再確認（競合状態を防ぐ）
                if st.session_state.interview_ended or st.session_state.get('generating_feedback', False) or st.session_state.get('feedback'):
                    st.rerun()
                    
                st.session_state.generating_feedback = True
                
                try:
                    with st.spinner("包括的なフィードバックを生成中..."):
                        # デバッグ用のログ
                        if st.session_state.logger:
                            st.session_state.logger.text_logger.info("Button clicked: End Interview & Get Feedback")
                        
                        # チェックポイント用のスレッド設定
                        config = {"configurable": {"thread_id": st.session_state.session_id}}
                        
                        # グラフが中断可能な状態かチェック
                        try:
                            snapshot = st.session_state.graph.get_state(config)
                            # 次のノードリストが空の場合、グラフは既に完了しています
                            if not snapshot.next:
                                if st.session_state.logger:
                                    st.session_state.logger.text_logger.warning("Graph already at END state, cannot resume")
                                st.session_state.generating_feedback = False
                                st.rerun()
                        except Exception as e:
                            if st.session_state.logger:
                                st.session_state.logger.text_logger.error(f"Error checking graph state: {e}")
                        
                        # 重要: グラフ状態にinterview_completeフラグを設定
                        # 最適化: security → topic_guideを経由せず、
                        # interview_complete=Trueでtopic_guideから来たように状態を更新
                        # これによりtopic_guideのルーティングがすぐにフラグを確認してfeedback_agentに進みます
                        
                        # まず、重要なフィールドを保持するために現在の状態を取得
                        current_snapshot = st.session_state.graph.get_state(config)
                        current_values = current_snapshot.values
                        
                        # topic_guideノードとして動作し、interview_completeフラグで状態を更新
                        st.session_state.graph.update_state(
                            config,
                            {
                                "interview_complete": True,
                                "topic_depth_sufficient": False,  # interview_completeが優先されるので関係ありません
                                "user_answer": current_values.get("user_answer", ""),  # 既存の回答を保持
                            },
                            as_node="topic_guide"  # topic_guideが評価を終えたかのように動作
                        )
                        
                        # topic_guideから再開 - feedback_agentに直接ルーティング
                        for chunk in st.session_state.graph.stream(None, config):
                            for node_name, node_output in chunk.items():
                                if isinstance(node_output, dict):
                                    st.session_state.state.update(node_output)
                                    
                                    # feedback_agentに到達したかチェック
                                    if node_output.get("current_agent") == "Feedback Agent" or node_name == "feedback_agent":
                                        # すぐにフィードバックを抽出
                                        if node_output.get("final_feedback"):
                                            st.session_state.feedback = node_output["final_feedback"]
                                            st.session_state.feedback_tokens = node_output.get("last_message_tokens", 0)
                                            # フィードバックをキャプチャしたらループを抜ける
                                            break
                        
                        if st.session_state.logger:
                            st.session_state.logger.text_logger.info("Graph stream completed successfully")
                        
                        # フィードバックが抽出されたか確認
                        if not st.session_state.get('feedback'):
                            # フォールバック: 最終状態から取得を試みる
                            if st.session_state.state.get("final_feedback"):
                                st.session_state.feedback = st.session_state.state["final_feedback"]
                                st.session_state.feedback_tokens = st.session_state.state.get("last_message_tokens", 0)
                            else:
                                st.session_state.feedback = "フィードバック生成に失敗しました。ログを確認してください。"
                                st.session_state.feedback_tokens = 0
                        
                        # 面接完了のログ
                        if st.session_state.logger and st.session_state.get('feedback'):
                            total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                            st.session_state.logger.log_interview_complete(
                                st.session_state.state["current_topic_index"],
                                total_questions
                            )
                        
                        # フィードバックが正常に生成された場合のみ終了とマーク
                        if st.session_state.get('feedback'):
                            st.session_state.interview_ended = True
                        
                finally:
                    # エラーが発生してもフラグを常にクリア
                    st.session_state.generating_feedback = False
                    
                st.rerun()
        elif st.session_state.get('generating_feedback', False):
            st.info("⏳ フィードバックを生成中です。しばらくお待ちください...")
        
        if st.button("面接をリセット", type="primary"):
            # リセット前にロガーを保存してクリア
            if st.session_state.logger:
                st.session_state.logger.save()
                clear_logger()
            
            st.session_state.interview_started = False
            st.session_state.session_id = None
            st.session_state.messages = []
            st.session_state.interview_ended = False
            st.session_state.state = None
            st.session_state.graph = None
            st.session_state.logger = None
            if 'feedback' in st.session_state:
                del st.session_state.feedback
            st.rerun()

# メインチャットインターフェース
if st.session_state.interview_started and not st.session_state.interview_ended:
    # チャットメッセージの表示
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            # アシスタントメッセージのエージェントとトークン情報を表示
            if message["role"] == "assistant" and "agent" in message:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f"{message['agent']}")
                with col2:
                    st.caption(f"🪙 {message.get('tokens', 0)} tokens")
            
            st.markdown(message["content"])
            
            # 実行ログのあるアシスタントメッセージのデバッグエキスパンダーを表示
            if message["role"] == "assistant" and "execution_log" in message:
                execution_log = message["execution_log"]
                
                with st.expander("🔍 デバッグ: Agent Flow", expanded=False):
                    for i, log in enumerate(execution_log, 1):
                        node = log["node"]
                        agent = log["agent"]
                        details = log["details"]
                        
                        # Security Agent
                        if node == "security_agent":
                            status = "✅ 合格" if details.get("passed") else "❌ 不合格"
                            next_step = "→ Topic Guide" if details.get("passed") else "→ Judge"
                            st.markdown(f"**{i}. 🔒 Security** {status} {next_step}")
                            if not details.get("passed"):
                                st.caption(f"   理由: {details.get('feedback', 'N/A')}")
                        
                        # Judge Agent
                        elif node == "judge":
                            action = "再試行" if details.get('action') == 'requesting retry' else "諦める"
                            next_step = "→ HITL" if details.get('action') == 'requesting retry' else "→ Topic Guide"
                            st.markdown(f"**{i}. ⚖️ Judge** {action} ({details.get('retry_count', 0)}/{details.get('max_retries', 0)}) {next_step}")
                        
                        # Topic Guide
                        elif node == "topic_guide":
                            depth = "✅ 十分" if details.get("depth_sufficient") else "❌ 不足"
                            if details.get("depth_sufficient"):
                                next_step = "→ 次のトピック" if details.get('iteration', 0) < details.get('max_iterations', 0) else "→ Feedback"
                            else:
                                next_step = "→ Probing"
                            st.markdown(f"**{i}. 📊 Topic Guide** {depth} {next_step}")
                            if details.get("feedback"):
                                st.caption(f"   {details.get('feedback', '')}")
                        
                        # Probing Agent
                        elif node == "probing_agent":
                            st.markdown(f"**{i}. 🔍 Probing** フォローアップ → HITL")
                            st.caption(f"   トピック: {details.get('topic', 'N/A')}")
                        
                        # Topic Agent
                        elif node == "topic_agent":
                            st.markdown(f"**{i}. 🎯 Topic Agent** 新しい質問 → HITL")
                            st.caption(f"   トピック: {details.get('topic', 'N/A')}")
                        
                        # Next Topic
                        elif node == "next_topic":
                            st.markdown(f"**{i}. ➡️ 次のトピック** → Topic Agent")
                        
                        # Human Input Node
                        elif node == "human_input_node":
                            st.markdown(f"**{i}. 👤 HITL** 中断 → Security")
                    
                    # コンパクトな状態サマリー
                    st.caption(f"状態: トピック {message.get('topic_index', 0)} | イテレーション {message.get('topic_iteration', 0)} | Judge再試行 {message.get('judge_retries', 0)}")
    
    

    # 音声入力UI
    # Check if there's pending voice input to process
    if st.session_state.get('pending_voice_input'):
        user_input = st.session_state.pending_voice_input
        st.session_state.pending_voice_input = None
    else:
        user_input = None
        
    with bottom():
        voice_col1, voice_col2, voice_col3 = st.columns([1, 4, 1])
        
        with voice_col1:
            if st.session_state.voice_recording:
                if st.button("🛑 停止", key="stop_voice_btn", use_container_width=True, type="secondary"):
                    # Stop recording
                    from voice.voice_input import get_voice_recorder
                    recorder = get_voice_recorder()
                    final_text = recorder.stop_recording()
                    st.session_state.voice_recording = False
                    st.session_state.voice_transcription = final_text
                    st.session_state.voice_temp_text = ""
                    st.session_state.chat_input = final_text
                    st.session_state.duration = round(recorder.duration * 1e-7, 2)
                    
                    st.rerun()
            else:
                if st.button("🎤 音声", key="start_voice_btn", use_container_width=True):
                    # Start recording
                    from voice.voice_input import get_voice_recorder
                    recorder = get_voice_recorder()
                    
                    if recorder.start_recording():
                        st.session_state.voice_recording = True
                        st.session_state.voice_transcription = ""
                        st.session_state.voice_temp_text = ""
                        st.rerun()
                    else:
                        st.error("音声認識を開始できませんでした")
        
        with voice_col2:
            if st.session_state.voice_recording:
                # Show recording status and live transcription
                # st.markdown("🔴 **録音中...**")
                # if st.session_state.voice_transcription or st.session_state.voice_temp_text:
                #     current_text = st.session_state.voice_transcription
                #     if st.session_state.voice_temp_text:
                #         current_text = f"{current_text} {st.session_state.voice_temp_text}".strip()
                #     st.caption(f"認識中: {current_text}")
                from voice.voice_input import get_voice_recorder
                
                recorder = get_voice_recorder()
                
                # Get current text from thread-safe storage (same singleton instance!)
                temp_text = recorder.get_current_text()
                               
                # Show recording status
                st.markdown("🔴 **録音中...**")
                
                # Show live transcription if any text is available
                if temp_text:
                    st.caption(f"認識中: {temp_text}")
                    
                    # Store in session state for display continuity
                    st.session_state.voice_temp_text = temp_text
                
                # Auto-refresh every 300ms to show live updates
                import time
                time.sleep(0.3)
                st.rerun()
                
            elif st.session_state.voice_transcription:
                # print(f"Recording duration: {recorder.duration} seconds")
                st.caption(f"録音時間: {st.session_state.duration} 秒")
        
        with voice_col3:
            if st.session_state.voice_transcription and not st.session_state.voice_recording:
                if st.button("✓ 使用", key="use_voice_btn", use_container_width=True, type="primary"):
                    # Use the transcription (edited if modified)
                    user_input = st.session_state.get("voice_edit", st.session_state.voice_transcription)
                    st.session_state.voice_transcription = ""
                    st.session_state.voice_temp_text = ""
                    
                    # Process the voice input (same as chat_input processing below)
                    # We'll set a flag and let it be processed below
                    st.session_state.pending_voice_input = user_input
                    st.rerun()
    

    
    
    # チャット入力
    user_input = st.chat_input("こちらに回答を入力してください...", key="chat_input")
    
    
    # Process user input (from either voice or text)
    if user_input:
        
        # 同じ入力の重複処理を防ぐ
        if st.session_state.last_processed_input == user_input:
            # この入力は既に処理済み、サイレントにスキップ
            st.stop()
        
        # 既に処理中かチェック
        if st.session_state.processing:
            # 別の入力を既に処理中、サイレントにスキップ
            st.stop()
        
        # 最初に処理中フラグを設定
        st.session_state.processing = True
        st.session_state.last_processed_input = user_input
        
        # ユーザーメッセージをチャットに追加
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # ユーザーの回答で状態を更新
        st.session_state.state["user_answer"] = user_input
        
        # チェックポイント永続化用のスレッド設定
        config = {"configurable": {"thread_id": st.session_state.session_id}}
        
        st.session_state.graph.update_state(
            config,
            {"user_answer": user_input},
            as_node="human_input_node"  # human_input_nodeが生成したかのように更新
        )
        
        # ユーザー入力でグラフを中断から再開
        # グラフは続行: human_input_node → security_agent → ...
        # 次の中断（再びhuman_input_node）またはEND（feedback_agent）に到達するまで
        
        # デバッグ用の実行フローを追跡
        execution_log = []
        
        with st.spinner("エージェント処理中..."):
            # Noneとconfigでinvokeを呼び出し中断から再開
            # これはLangGraphに「中断した場所から続ける」と伝えます
            for chunk in st.session_state.graph.stream(None, config):
                # 各ノードの出力を処理
                for node_name, node_output in chunk.items():
                    # node_outputは辞書であるべきですが、エッジケースを処理
                    if not isinstance(node_output, dict):
                        continue
                    
                    st.session_state.state.update(node_output)
                    
                    # 実行の詳細をログ
                    log_entry = {
                        "node": node_name,
                        "agent": node_output.get("current_agent", ""),
                        "details": {}
                    }
                    
                    # Security agentの詳細
                    if node_name == "security_agent":
                        log_entry["details"] = {
                            "passed": node_output.get("security_passed"),
                            "feedback": node_output.get("security_feedback", ""),
                            "answer_length": len(st.session_state.state.get("user_answer", "")),
                        }
                    
                    # Judge agentの詳細
                    elif node_name == "judge":
                        log_entry["details"] = {
                            "retry_count": node_output.get("judge_retry_count", 0),
                            "max_retries": st.session_state.state.get("max_judge_retries", 0),
                            "action": "requesting retry" if node_output.get("waiting_for_user_input") else "giving up"
                        }
                    
                    # Topic guideの詳細
                    elif node_name == "topic_guide":
                        log_entry["details"] = {
                            "depth_sufficient": node_output.get("topic_depth_sufficient"),
                            "iteration": st.session_state.state.get("topic_iteration_count", 0),
                            "max_iterations": st.session_state.state.get("max_iterations_per_topic", 0),
                            "feedback": node_output.get("topic_feedback", ""),
                        }
                    
                    # Topic/Probing agentの詳細
                    elif node_name in ["topic_agent", "probing_agent"]:
                        log_entry["details"] = {
                            "question_generated": bool(node_output.get("current_question")),
                            "topic": st.session_state.state.get("current_topic", {}).get("topic", ""),
                            "theme": st.session_state.state.get("current_topic", {}).get("theme", ""),
                        }
                    
                    execution_log.append(log_entry)
            
            # グラフは以下のいずれかに到達:
            # 1. 次の中断（human_input_node） - 新しい質問の準備完了
            # 2. END（feedback_agent） - 面接完了
            
            # 面接完了時はfinal_feedbackを確認
            if st.session_state.state.get("interview_complete") and st.session_state.state.get("final_feedback"):
                # Feedback agent - フィードバックページに表示するために保存
                st.session_state.feedback = st.session_state.state["final_feedback"]
                st.session_state.feedback_tokens = st.session_state.state.get("last_message_tokens", 0)
                st.session_state.interview_ended = True
                
                # 面接完了のログ
                if st.session_state.logger:
                    total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                    st.session_state.logger.log_interview_complete(
                        st.session_state.state["current_topic_index"],
                        total_questions
                    )
            # 新しい質問が生成された場合は表示
            elif st.session_state.state.get("current_question"):
                agent_name = st.session_state.state.get("current_agent", "Agent")
                tokens = st.session_state.state.get("last_message_tokens", 0)
                # チャットに質問を表示（judge/probing/topic agent）
                agent_message = {
                    "role": "assistant",
                    "content": st.session_state.state["current_question"],
                    "agent": agent_name,
                    "tokens": tokens,
                    "execution_log": execution_log,  # メッセージと共に実行ログを保存
                    "topic_index": st.session_state.state.get("current_topic_index", 0),
                    "topic_iteration": st.session_state.state.get("topic_iteration_count", 0),
                    "judge_retries": st.session_state.state.get("judge_retry_count", 0)
                }
                st.session_state.messages.append(agent_message)
                
                with st.chat_message("assistant"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.caption(f"{agent_name}")
                    with col2:
                        st.caption(f"🪙 {tokens} tokens")
                    st.markdown(st.session_state.state["current_question"])
        
        # 処理中フラグをリセット
        st.session_state.processing = False
        st.rerun()

elif st.session_state.interview_ended:
    st.header("📊 面接フィードバック")
    
    # グラフのfeedback_agentによって生成されたフィードバックを表示
    if 'feedback' in st.session_state:
        # フィードバックのトークン使用量を表示
        st.caption(f"📝 Feedback Agent | 🪙 {st.session_state.get('feedback_tokens', 0)} tokens")
        st.markdown(st.session_state.feedback)
        
        st.divider()
        
        # サマリー統計
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("カバーしたトピック", st.session_state.state["current_topic_index"])
        with col2:
            st.metric("合計トークン", st.session_state.state.get("total_tokens", 0))
        with col3:
            st.metric("メッセージ数", len(st.session_state.messages))
        
        st.divider()
        
        # ログダウンロードセクション
        st.subheader("📥 面接ログをダウンロード")
    else:
        # フィードバックが正しく生成されなかった
        st.error("⚠️ フィードバックが正しく生成されませんでした。詳細はログを確認してください。")
        st.info("面接は終了しましたが、Feedback Agentが出力を生成しませんでした。")
        
        # フォールバックとして会話履歴から抽出を試みる
        if st.session_state.state and "conversation_history" in st.session_state.state:
            for entry in reversed(st.session_state.state["conversation_history"]):
                if entry.get("agent") == "feedback_agent" and "feedback" in entry:
                    st.session_state.feedback = entry["feedback"]
                    st.session_state.feedback_tokens = entry.get("tokens", 0)
                    st.success("✅ 会話履歴からフィードバックを復元しました！")
                    st.markdown(st.session_state.feedback)
                    break
        
        if st.session_state.logger:
            # ダウンロードを提供する前にログを保存
            st.session_state.logger.save()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # 会話テキストをダウンロード
                conversation_text = st.session_state.logger.export_conversation_text()
                st.download_button(
                    label="📄 会話をダウンロード",
                    data=conversation_text,
                    file_name=f"conversation_{st.session_state.session_id}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # 完全なJSONログをダウンロード
                import json
                json_data = json.dumps(st.session_state.logger.log_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label="📊 完全ログをダウンロード (JSON)",
                    data=json_data,
                    file_name=f"interview_{st.session_state.session_id}.json",
                    mime="application/json"
                )
            
            with col3:
                # ログファイルの場所を表示
                st.info(f"ログの保存先:\n`{st.session_state.logger.log_dir}`")
    
    if st.button("新しい面接を開始", type="primary"):
        # ロガーを保存してクリア
        if st.session_state.logger:
            st.session_state.logger.save()
            clear_logger()
        
        st.session_state.interview_started = False
        st.session_state.session_id = None
        st.session_state.messages = []
        st.session_state.interview_ended = False
        st.session_state.state = None
        st.session_state.graph = None
        st.session_state.logger = None
        if 'feedback' in st.session_state:
            del st.session_state.feedback
        if 'feedback_tokens' in st.session_state:
            del st.session_state.feedback_tokens
        st.rerun()

else:
    # ウェルカム画面
    st.markdown("""
    ## 💼 従業員知識評価面接システム
    
    マルチエージェントによる対話型面接システムです。技術知識を段階的に評価し、詳細なフィードバックを提供します。
    """)
    
    st.divider()
    
    # 2カラムレイアウト
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 📖 ページ構成
        
        #### **🏠 メインページ（このページ）**
        サイドバーで設定を行い、面接を実施します：
        - **ユーザー名**: ログファイルの識別用（必須）- 後でLog Viewerでフィルタリングする際に使用
        - **プロンプト設定**: エージェントの動作を定義するYAMLファイルを選択（Graph Prompt Editorで作成したファイルを選択可能）
        - **トピックファイル**: 面接で使用するCSVファイルを選択（Topic Editorで作成したファイルを選択可能）
        - **フォローアップ数**: トピックごとに何回まで深掘りするか（1-10回）
        - **再試行回数**: 不適切な回答に対して何回まで再回答を求めるか（0-10回）
        - **音声入力対応**: 🎤ボタンでリアルタイム音声認識による回答が可能
        
        #### **📝 02_Graph Prompt Editor**
        エージェントのプロンプトをカスタマイズ：
        - **6つのエージェント**のプロンプトを個別に編集（Topic, Security, Judge, Topic Guide, Probing, Feedback）
        - **テキストエリア**で直接編集し、変更内容をプレビュー
        - **メモ機能**でプロンプトファイルの目的・変更履歴を記録
        - **別名保存**で元のファイルを保護しながら新バージョンを作成
        - **即座に反映**: 保存後、メインページのプロンプト選択で利用可能
        
        #### **📊 03_Graph Structure**
        面接フローをビジュアルで理解：
        - **Mermaidダイアグラム**でエージェントの実行順序を可視化
        - **条件分岐**の仕組みを図で確認（例：Security失敗→Judge、Topic Guide不足→Probing）
        - **Human-in-the-Loop（HITL）**の位置を把握
        - **システム全体の流れ**を理解してからカスタマイズ作業に着手
        """)
    
    with col2:
        st.markdown("""
        #### **🔍 04_Log Viewer**
        過去の面接ログを詳細分析：
        - **ユーザー名フィルタ**: 複数ユーザーの面接から特定ユーザーのみ抽出
        - **セッション選択**: 日時とトピック数で識別
        - **会話タイムライン**: 質問・回答を時系列で表示し、どのエージェントが発言したか確認
        - **エージェント判定**: Security/Judge/Topic Guideの判定理由と詳細を確認
        - **統計情報**: トークン使用量、所要時間、トピック進捗などを可視化
        - **ログダウンロード**: テキスト形式またはJSON形式で保存可能
        
        #### **📋 05_Topic Editor**
        面接トピックを柔軟に管理：
        - **4つの編集モード**を切り替え可能（Table/Form/Preview/Raw CSV）
        - **Table Editor**: スプレッドシート風にまとめて編集・行の追加削除
        - **Form Editor**: 1件ずつ丁寧に追加（テーマ、トピック、例示質問）
        - **Preview Mode**: テーマ別にグループ化して構造を確認
        - **Raw CSV Editor**: 直接CSVテキストを編集（大量データのコピペに便利）
        - **バリデーション**: 必須項目チェック、重複検出で品質を保証
        - **別名保存**: 元のtopics.csvを上書きせず、新ファイルとして保存
        
        ---
        
        ### 🤖 エージェント構成
        
        - **🎯 Topic Agent**: トピックに基づく質問を生成
        - **🔒 Security Agent**: 回答の品質・関連性を検証（短すぎる/無関係な回答を検出）
        - **⚖️ Judge Agent**: 不十分な回答に改善を要求（最大再試行回数まで）
        - **📊 Topic Guide**: 知識の深さを評価し、十分でなければProbing Agentへ
        - **🔍 Probing Agent**: より深い理解を確認するフォローアップ質問を生成
        - **📝 Feedback Agent**: 全体を通しての詳細な評価とアドバイスを提供
        """)
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### 🚀 使い方
        
        1. **サイドバーで設定**
        - ユーザー名を入力（例：tanaka_taro）
        - プロンプトファイルを選択（デフォルト推奨）
        - トピックCSVファイルを選択
        
        2. **「面接を開始」をクリック**
        - Topic Agentが最初の質問を生成
        - テキストまたは音声で回答
        
        3. **対話を続ける**
        - Security AgentとJudge Agentが回答を検証
        - Topic Guideが知識の深さを評価
        - Probing Agentがフォローアップ質問を実施
        
        4. **フィードバックを取得**
        - 全トピック終了後、または途中終了ボタンで終了
        - Feedback Agentがテーマ別の総合評価を生成
        - ログファイルをダウンロード可能
        
        **👇 下のトピック一覧で面接内容を確認してから開始してください！**
        """)
    
    # トピックファイルのプレビューを表示
    with col2:
        st.subheader("📋 トピック一覧プレビュー")
        
        data_dir = Path("data")
        if data_dir.exists():
            available_files = sorted([f.name for f in data_dir.glob("*.csv")])
            if available_files:
                # サイドバーで選択されたファイルを取得（セッション状態から）
                selected_file = st.session_state.get('topics_file_selector')
                
                # セッション状態にない場合はデフォルトを使用
                if not selected_file:
                    selected_file = "topics.csv" if "topics.csv" in available_files else available_files[0]
                
                topics_preview_file = str(data_dir / selected_file)
                
                if os.path.exists(topics_preview_file):
                    # CSVをDataFrameとして読み込み
                    try:
                        df = pd.read_csv(topics_preview_file)
                        st.caption(f"表示中: `{selected_file}` ({len(df)} トピック)")
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    except Exception as e:
                        st.error(f"⚠️ ファイルの読み込みに失敗しました: {str(e)}")
                else:
                    st.warning(f"⚠️ ファイルが見つかりません: `{selected_file}`")
            else:
                st.warning("⚠️ data/ フォルダにCSVファイルが見つかりません")
        else:
            st.warning("⚠️ data/ フォルダが見つかりません")

