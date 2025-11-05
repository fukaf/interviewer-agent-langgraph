import streamlit as st
from datetime import datetime
from multi_agent_system import create_interview_graph, load_topics_from_csv
from logger import InterviewLogger, set_logger, clear_logger, get_logger
import os

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

# サイドバー
with st.sidebar:
    st.header("面接設定")
    
    if not st.session_state.interview_started:
        # LLMプロバイダーの表示
        llm_provider = os.getenv("LLM_PROVIDER", "openai").upper()
        st.info(f"🤖 LLMプロバイダー: **{llm_provider}**")
        
        # トピックの読み込みとプレビュー
        topics_file = st.text_input("トピックCSVファイル", value="topics.csv")
        
        if os.path.exists(topics_file):
            topics = load_topics_from_csv(topics_file)
            st.success(f"✅ {len(topics)}件のトピックを読み込みました")
            
            # テーマ別にトピックを整理
            themes_dict = {}
            for topic in topics:
                theme = topic.get('theme', 'その他')
                if theme not in themes_dict:
                    themes_dict[theme] = []
                themes_dict[theme].append(topic)
            
            # ツリービューの表示
            with st.expander(f"📋 トピック構造 ({len(themes_dict)}テーマ)", expanded=False):
                for theme_idx, theme in enumerate(sorted(themes_dict.keys()), 1):
                    # 折りたたみ可能なテーマのチェックボックス
                    show_theme = st.checkbox(f"🎯 {theme} ({len(themes_dict[theme])}トピック)", key=f"theme_{theme_idx}", value=False)
                    
                    if show_theme:
                        for idx, topic in enumerate(themes_dict[theme], 1):
                            # インデント付きのトピック名
                            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;**{idx}. {topic.get('topic', 'N/A')}**")
                            
                            # さらにインデントされた例示質問
                            example_questions = topic.get('example_questions', [])
                            if example_questions:
                                for q_idx, question in enumerate(example_questions, 1):
                                    st.caption(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;• {question}")
                            
                            # トピック間のスペース
                            if idx < len(themes_dict[theme]):
                                st.write("")
                    
                    # テーマ間のスペース
                    if theme_idx < len(themes_dict):
                        st.write("")
        else:
            st.warning("⚠️ トピックファイルが見つかりません")
            topics = load_topics_from_csv(topics_file)
        
        max_iterations = st.slider("トピックごとの最大フォローアップ数", 1, 5, 2)
        max_judge_retries = st.slider("Judge Agentの最大再試行回数", 0, 5, 2, 
                                       help="無効な回答に対してJudge Agentが再試行を求める回数。0に設定すると次の質問に直接スキップします。")
        
        if st.button("面接を開始", type="primary"):
            with st.spinner("マルチエージェントシステムを初期化中..."):
                # 一意のセッションIDを生成
                st.session_state.session_id = f"interview_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # ロガーの初期化
                st.session_state.logger = InterviewLogger(st.session_state.session_id)
                set_logger(st.session_state.logger)
                st.session_state.logger.text_logger.info("Interview session initialized")
                
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
                                        if node_output.get("current_question"):
                                            st.session_state.feedback = node_output["current_question"]
                                            st.session_state.feedback_tokens = node_output.get("last_message_tokens", 0)
                                            # フィードバックをキャプチャしたらループを抜ける
                                            break
                        
                        if st.session_state.logger:
                            st.session_state.logger.text_logger.info("Graph stream completed successfully")
                        
                        # フィードバックが抽出されたか確認
                        if not st.session_state.get('feedback'):
                            # フォールバック: 最終状態から取得を試みる
                            if st.session_state.state.get("current_question") and st.session_state.state.get("current_agent") in ["Feedback Agent", "📝 Feedback Agent"]:
                                st.session_state.feedback = st.session_state.state["current_question"]
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
    
    # チャット入力
    if user_input := st.chat_input("こちらに回答を入力してください..."):
        
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
            
            # 新しい質問/フィードバックが生成された場合は表示
            if st.session_state.state.get("current_question"):
                agent_name = st.session_state.state.get("current_agent", "Agent")
                tokens = st.session_state.state.get("last_message_tokens", 0)
                
                if st.session_state.state.get("interview_complete"):
                    # Feedback agent - フィードバックページに表示するために保存
                    st.session_state.feedback = st.session_state.state["current_question"]
                    st.session_state.feedback_tokens = tokens
                    st.session_state.interview_ended = True
                    
                    # 面接完了のログ
                    if st.session_state.logger:
                        total_questions = len([m for m in st.session_state.messages if m["role"] == "assistant"])
                        st.session_state.logger.log_interview_complete(
                            st.session_state.state["current_topic_index"],
                            total_questions
                        )
                else:
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
    ## 従業員知識評価面接へようこそ！ 👋
    
    このアプリケーションは、企業知識に関する詳細な面接を実施する**マルチエージェントシステム**を使用しています。
    
    ### マルチエージェントシステム:
    - 🎯 **Topic Agent**: 事前定義されたトピックから質問を生成
    - 🔒 **Security Agent**: 回答の品質と関連性を検証
    - ⚖️ **Judge Agent**: 不明瞭な回答にフィードバックを提供
    - 📊 **Topic Guide**: 知識の深さを評価
    - 🔍 **Probing Agent**: フォローアップ質問を実施
    - 📝 **Feedback Agent**: 包括的な評価を提供
    
    ### 使い方:
    1. **トピックCSVをアップロード**（またはデフォルトを使用）テーマと例示質問を含む
    2. **面接を開始** - エージェントが会話をガイド
    3. **質問に回答** - どのエージェントが応答しているか、トークン使用量を確認
    4. **フィードバックを受け取る** - テーマ別の包括的な評価
    
    ### 機能:
    - ✅ 各メッセージのエージェント識別
    - ✅ リアルタイムトークン使用量追跡
    - ✅ トピック全体の進捗追跡
    - ✅ インテリジェントなフォローアップ質問
    - ✅ テーマ別フィードバック
    
    **始める準備はできましたか？** サイドバーで面接を設定し、「面接を開始」をクリックしてください！
    """)
