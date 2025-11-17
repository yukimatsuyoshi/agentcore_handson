import streamlit as st
import requests
import json
from urllib.parse import urlencode
import base64

# 設定
COGNITO_DOMAIN = "https://us-west-2sjapgz7rx.auth.us-west-2.amazoncognito.com"
CLIENT_ID = "4bf9es7gubr0pl2haftkn16pmf"
CLIENT_SECRET = "t7alrfjbr5hq1rl6uv9l7eqm5lss5iiqsi91lpbj03q8j4n6dpm"
REDIRECT_URI = "http://localhost:8501"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:605664253368:runtime/google_calender_agent-DHAqfj9XsV"
REGION = "us-west-2"

st.title("Google Calendar AIエージェント")

# URLパラメータからcodeを取得
query_params = st.query_params
code = query_params.get("code")

# セッション状態の初期化
if "access_token" not in st.session_state:
    st.session_state.access_token = None

# ログイン処理
if code and not st.session_state.access_token:
    st.info("トークンを取得中...")
    
    # codeをaccess_tokenに交換
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    
    token_data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    # Basic認証用のヘッダー
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    try:
        response = requests.post(token_url, data=token_data, headers=headers)
        
        if response.status_code == 200:
            tokens = response.json()
    
            # ★access_tokenを使う（access_tokenにはclient_idクレームが含まれる）
            st.session_state.access_token = tokens["access_token"]
            
            # トークンをデコード...
            try:
                token_parts = st.session_state.access_token.split('.')
                payload = token_parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.urlsafe_b64decode(payload)
                token_claims = json.loads(decoded)
                
                st.write("🔍 トークンの中身:")
                st.json(token_claims)
                
                st.write(f"**client_id クレーム:** {token_claims.get('client_id')}")
                st.write(f"**aud クレーム:** {token_claims.get('aud', 'なし')}")
                
            except Exception as e:
                st.write(f"デコードエラー: {e}")
            
            st.success("✅ Googleアカウントでログインしました！")
            st.button("続ける", on_click=lambda: st.rerun())
        else:
            st.error(f"トークン取得エラー: {response.text}")
    except Exception as e:
        st.error(f"エラー: {e}")

# ログイン状態の確認
if not st.session_state.access_token:
    st.info("👇 まずはGoogleアカウントでログインしてください")
    
    # ログインボタン
    login_params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": REDIRECT_URI
    }
    login_url = f"{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(login_params)}"
    
    st.markdown(f"[🔐 Googleでログイン]({login_url})")
    st.stop()

# ログイン後のUI
st.success("✅ ログイン済み")

if st.button("ログアウト"):
    st.session_state.access_token = None
    st.rerun()

# チャットインターフェース
st.subheader("💬 カレンダー管理")

user_input = st.text_input("何をお手伝いしましょうか？", 
                           placeholder="例: 明日の予定を教えて")

if st.button("送信") and user_input:
    with st.spinner("AIエージェントが処理中..."):
        try:
            import urllib.parse
            encoded_arn = urllib.parse.quote(AGENT_ARN, safe='')
            
            endpoint = f"https://bedrock-agentcore.{REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            
            headers = {
                "Authorization": f"Bearer {st.session_state.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "prompt": user_input
            }
            
            response = requests.post(endpoint, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                st.write("🤖 エージェントの応答:")
                st.write(result.get("response", result))
            else:
                st.error(f"エラー: {response.text}")
            
        except Exception as e:
            st.error(f"エラー: {e}")