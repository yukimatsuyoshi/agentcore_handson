import streamlit as st
import subprocess
import json

st.set_page_config(page_title="GitHub Issues Assistant", page_icon="🐙")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "owner" not in st.session_state:
    st.session_state.owner = ""
if "repo" not in st.session_state:
    st.session_state.repo = ""
if "agent_name" not in st.session_state:
    st.session_state.agent_name = "github_assistant_agent"
if "user_id" not in st.session_state:
    st.session_state.user_id = "test-user"

# サイドバー設定
with st.sidebar:
    st.title("⚙️ 設定")
    owner = st.text_input("Owner", value=st.session_state.owner, placeholder="例: microsoft")
    repo = st.text_input("Repository", value=st.session_state.repo, placeholder="例: vscode")
    agent_name = st.text_input("Agent名", value=st.session_state.agent_name)
    user_id = st.text_input("User ID", value=st.session_state.user_id)

    if st.button("設定", type="primary"):
        st.session_state.owner = owner
        st.session_state.repo = repo
        st.session_state.agent_name = agent_name
        st.session_state.user_id = user_id
        st.success("✅ 設定を保存しました")
        st.rerun()

    if st.session_state.owner and st.session_state.repo:
        st.info(f"📍 {st.session_state.owner}/{st.session_state.repo}")

    if st.button("🗑️ チャット履歴をクリア"):
        st.session_state.messages = []
        st.rerun()

# メインエリア
st.title("🐙 GitHub Issues Assistant")

if not st.session_state.owner or not st.session_state.repo:
    st.warning("⚠️ 左サイドバーでGitHubリポジトリを設定してください")
    st.stop()

# チャット履歴表示
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ユーザー入力
if prompt := st.chat_input("メッセージを入力してください..."):
    enhanced_prompt = f"{st.session_state.owner}/{st.session_state.repo}リポジトリで、{prompt}"

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("処理中..."):
            try:
                result = subprocess.run(
                    ["agentcore", "invoke", json.dumps({"prompt": enhanced_prompt}),
                     "--agent", st.session_state.agent_name, "--user-id", st.session_state.user_id],
                    capture_output=True, text=True, timeout=60
                )

                if result.returncode == 0:
                    try:
                        response_data = json.loads(result.stdout)
                        response_text = response_data["result"]["message"]["content"][0]["text"]
                    except:
                        response_text = result.stdout

                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                else:
                    error_msg = f"❌ エラー\n```\n{result.stderr}\n```"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except subprocess.TimeoutExpired:
                error_msg = "⏱️ タイムアウトしました"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})

            except Exception as e:
                error_msg = f"❌ エラー\n```\n{str(e)}\n```"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
