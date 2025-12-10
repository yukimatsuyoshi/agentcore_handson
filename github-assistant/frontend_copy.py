# streamlit_app.py
import streamlit as st
import subprocess
import json
import time

st.set_page_config(
    page_title="GitHub Issues Assistant",
    page_icon="🐙",
    layout="wide"
)

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

if "owner" not in st.session_state:
    st.session_state.owner = ""

if "repo" not in st.session_state:
    st.session_state.repo = ""

# サイドバー：設定
with st.sidebar:
    st.title("⚙️ 設定")
    
    st.markdown("---")
    
    # GitHub設定
    st.subheader("🐙 GitHubリポジトリ")
    owner = st.text_input(
        "Owner（ユーザー名/組織名）",
        value=st.session_state.owner,
        placeholder="例: microsoft"
    )
    repo = st.text_input(
        "Repository（リポジトリ名）",
        value=st.session_state.repo,
        placeholder="例: vscode"
    )
    
    if st.button("設定を保存", type="primary", use_container_width=True):
        st.session_state.owner = owner
        st.session_state.repo = repo
        st.success("✅ 設定を保存しました")
        st.rerun()
    
    # 現在の設定を表示
    if st.session_state.owner and st.session_state.repo:
        st.info(f"📍 現在のリポジトリ:\n`{st.session_state.owner}/{st.session_state.repo}`")
    
    st.markdown("---")
    
    # AgentCore設定
    st.subheader("🤖 AgentCore設定")
    agent_name = st.text_input(
        "Agent名",
        value="github_assistant_agent",
        help="AgentCore Runtimeにデプロイしたエージェント名"
    )
    user_id = st.text_input(
        "User ID",
        value="test-user",
        help="M2M認証用のユーザーID"
    )
    
    st.markdown("---")
    
    # チャット履歴をクリア
    if st.button("🗑️ チャット履歴をクリア", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    
    # 使い方
    with st.expander("📖 使い方"):
        st.markdown("""
        ### 基本的な使い方
        
        1. **設定**：左サイドバーでOwnerとRepositoryを設定
        2. **質問**：チャット欄に質問を入力
        3. **実行**：エージェントがGitHub Issuesを操作
        
        ### 質問例
        
        - 「Issue一覧を取得して」
        - 「新しいIssueを作成。タイトル:バグ修正」
        - 「Issue #1の詳細を教えて」
        - 「Issue #2にコメントを追加」
        - 「openなIssueを全て取得」
        - 「Issue #3をクローズして」
        """)

# メインエリア
st.title("🐙 GitHub Issues Assistant")
st.markdown("AgentCore Gateway & Identityを使ったGitHub Issues管理アシスタント")

# リポジトリ未設定の警告
if not st.session_state.owner or not st.session_state.repo:
    st.warning("⚠️ 左サイドバーでGitHubリポジトリを設定してください")
    st.stop()

# チャット履歴を表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザー入力
if prompt := st.chat_input("メッセージを入力してください..."):
    # リポジトリ情報を自動的にプロンプトに追加
    enhanced_prompt = f"{st.session_state.owner}/{st.session_state.repo}リポジトリで、{prompt}"
    
    # ユーザーメッセージを追加
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })
    
    # ユーザーメッセージを表示
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # アシスタントの応答
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("エージェントが処理中..."):
            try:
                # AgentCore Runtimeを呼び出し
                result = subprocess.run(
                    [
                        "agentcore",
                        "invoke",
                        json.dumps({"prompt": enhanced_prompt}),
                        "--agent", agent_name,
                        "--user-id", user_id
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode == 0:
                    # 成功時の処理
                    try:
                        # JSON形式のレスポンスをパース
                        response_data = json.loads(result.stdout)
                        
                        # レスポンスからテキストを抽出
                        if isinstance(response_data, dict):
                            if "result" in response_data:
                                # result.message.content[0].text の形式
                                response_text = response_data["result"]["message"]["content"][0]["text"]
                            elif "Response" in response_data:
                                response_text = response_data["Response"]
                            else:
                                response_text = str(response_data)
                        else:
                            response_text = str(response_data)
                        
                        message_placeholder.markdown(response_text)
                        
                        # アシスタントの応答を履歴に追加
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_text
                        })
                    
                    except json.JSONDecodeError:
                        # JSONパースに失敗した場合、標準出力をそのまま表示
                        message_placeholder.markdown(result.stdout)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": result.stdout
                        })
                
                else:
                    # エラー時の処理
                    error_message = f"❌ エラーが発生しました\n\n```\n{result.stderr}\n```"
                    message_placeholder.error(error_message)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_message
                    })
            
            except subprocess.TimeoutExpired:
                error_message = "⏱️ タイムアウトしました。処理に時間がかかりすぎています。"
                message_placeholder.error(error_message)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message
                })
            
            except Exception as e:
                error_message = f"❌ 予期しないエラーが発生しました\n\n```\n{str(e)}\n```"
                message_placeholder.error(error_message)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message
                })

# フッター
st.markdown("---")
st.caption("Powered by AWS Bedrock AgentCore, Strands Agents, and Streamlit")