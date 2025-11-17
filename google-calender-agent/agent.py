"""
Google Calendar管理AIエージェント
AgentCore Gateway + Identity統合
"""

import os
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

app = BedrockAgentCoreApp()
GATEWAY_URL = os.environ.get("GATEWAY_URL")

# ★グローバル変数でOAuth URLを保存
oauth_url_holder = {"url": None}

# ★Google Calendar APIアクセス用のツールにデコレーターを追加
@requires_access_token(
    provider_name="google-oauth-client",
    scopes=["https://www.googleapis.com/auth/calendar"],
    auth_flow="USER_FEDERATION",
    on_auth_url=lambda url: oauth_url_holder.update({"url": url}),  # URLを保存
    force_authentication=False
)
async def get_calendar_token(*, access_token: str):
    """Google Calendar APIへのアクセストークンを取得"""
    print(f"DEBUG: Google access token obtained: {access_token[:20]}...")
    return access_token

@app.entrypoint
def invoke(payload, context=None):
    """AgentCore Runtimeからのリクエストを処理"""

    print(f"DEBUG: payload = {payload}")
    
    # OAuth URLをリセット
    oauth_url_holder["url"] = None
    
    # ★contextからrequest_headersを取得
    authorization_header = ""
    if context and hasattr(context, 'request_headers'):
        request_headers = context.request_headers
        print(f"DEBUG: request_headers = {request_headers}")
        authorization_header = request_headers.get("Authorization", "")
    
    # ユーザーのメッセージを取得
    user_message = payload.get("prompt", "")
    if not user_message:
        return {"error": "メッセージが空です。"}
    
    print(f"DEBUG: Authorization = {authorization_header[:50] if authorization_header else 'None'}...")
    print(f"DEBUG: GATEWAY_URL = {GATEWAY_URL}")
    
    # ★まず、Google Calendar APIへのアクセストークンを取得試行
    import asyncio
    
    try:
        calendar_token = asyncio.run(get_calendar_token(access_token=""))
        print(f"DEBUG: Google Calendar access token obtained successfully")
    except Exception as token_error:
        print(f"DEBUG: Google OAuth consent required: {token_error}")
        
        # OAuth URLが生成されているかチェック
        if oauth_url_holder["url"]:
            print(f"DEBUG: OAuth URL generated: {oauth_url_holder['url']}")
            return {
                "response": [{
                    "text": "Google Calendarへのアクセスには、Googleアカウントでの認証が必要です。"
                }],
                "requires_google_auth": True,
                "google_auth_url": oauth_url_holder["url"]
            }
        else:
            # OAuth URL生成失敗
            return {
                "error": "Google認証URLの生成に失敗しました。",
                "detail": str(token_error)
            }
    
    try:
        # Gateway接続用のヘッダー
        headers = {}
        if authorization_header:
            headers["Authorization"] = authorization_header
        
        print(f"DEBUG: Connecting to Gateway...")
        
        # MCPClientを使ってGatewayに接続
        gateway_client = MCPClient(
            lambda: streamablehttp_client(
                GATEWAY_URL,
                headers=headers if headers else None
            )
        )
        
        with gateway_client:
            print(f"DEBUG: Gateway connection established")
            
            # ★ツールを取得
            tools = gateway_client.list_tools_sync()
            print(f"DEBUG: Retrieved {len(tools)} tools from Gateway")
            
            if len(tools) == 0:
                return {
                    "error": "Gatewayからツールを取得できませんでした。",
                    "detail": "Google Calendar APIのTargetが設定されているか確認してください。"
                }
            
            agent = Agent(
                model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                tools=tools,
                system_prompt="""あなたは親切なGoogle Calendar管理アシスタントです。
ユーザーの予定管理をサポートします。

利用可能なツール:
- Google Calendar APIを通じて予定の取得、作成、更新、削除が可能

応答は親しみやすく、簡潔に。日本語で応答してください。
""",
                callback_handler=None
            )
            
            print(f"DEBUG: Running agent with user message: {user_message}")
            result = agent(user_message)
            print(f"DEBUG: Agent completed successfully")
            
            return {"response": result.message["content"]}
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"ERROR: {error_detail}")
        return {
            "error": f"エラーが発生しました: {str(e)}",
            "detail": error_detail,
            "gateway_url": GATEWAY_URL
        }

if __name__ == "__main__":
    app.run()

# """
# Google Calendar管理AIエージェント
# AgentCore Gateway + Identity統合

# このエージェントは以下を実現します:
# - Inbound Auth: Cognito経由のGoogle認証(USER_FEDERATION)
# - Outbound Auth: Gateway経由でGoogle Calendar APIにアクセス
# - 1回のGoogle認証で両方カバー
# """

# import os
# from bedrock_agentcore.runtime import BedrockAgentCoreApp
# from strands import Agent
# from strands.tools.mcp import MCPClient
# from mcp.client.streamable_http import streamablehttp_client

# # AgentCore Runtime Appを初期化
# app = BedrockAgentCoreApp()

# # 環境変数からGateway URLを取得
# GATEWAY_URL = os.environ.get("GATEWAY_URL")

# @app.entrypoint
# def invoke(payload):
#     """
#     AgentCore Runtimeからのリクエストを処理
    
#     Args:
#         payload: {
#             "prompt": str,  # ユーザーのメッセージ
#             "headers": {
#                 "Authorization": "Bearer <access_token>"
#             }
#         }
    
#     Returns:
#         {
#             "response": str,  # エージェントの応答
#             "session_id": str  # セッションID(オプション)
#         }
#     """
    
#     # Inbound Authから取得したアクセストークン
#     # CognitoのJWTトークンがGatewayへの認証に使用される
#     authorization_header = payload.get("headers", {}).get("Authorization", "")
#     if not authorization_header:
#         return {
#             "error": "認証トークンが見つかりません。Googleアカウントでログインしてください。"
#         }
    
#     # ユーザーのメッセージを取得
#     user_message = payload.get("prompt", "")
#     if not user_message:
#         return {
#             "error": "メッセージが空です。"
#         }
    
#     try:
#         # MCPClientを使ってGatewayに接続
#         # GatewayはInbound Authトークンを検証し、Outbound AuthでGoogle Calendar APIにアクセス
#         gateway_client = MCPClient(
#             lambda: streamablehttp_client(
#                 GATEWAY_URL,
#                 headers={"Authorization": authorization_header}
#             )
#         )
        
#         with gateway_client:
#             # Gatewayから利用可能なツール(Google Calendar API)を取得
#             tools = gateway_client.list_tools_sync()
            
#             # Strands Agentを作成
#             agent = Agent(
#                 model="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
#                 tools=tools,
#                 system_prompt="""あなたは親切なGoogle Calendar管理アシスタントです。
# ユーザーの予定管理をサポートします。

# 利用可能なツール:
# - Google Calendar APIを通じて予定の取得、作成、更新、削除が可能

# 対応できるリクエスト例:
# - 「明日の予定は?」→ 明日の予定一覧を表示
# - 「来週のミーティングを教えて」→ 来週のミーティング予定を検索
# - 「3月15日14時にMTGを作成して」→ 新しい予定を作成
# - 「明日の午後のMTGをキャンセルして」→ 該当する予定を削除

# 日付・時刻の解釈:
# - 「明日」→ 翌日
# - 「来週」→ 次の週
# - 時刻指定がない場合は9:00をデフォルトとする
# - 終了時刻が指定されていない場合は開始時刻+1時間とする

# 応答は親しみやすく、簡潔に。日本語で応答してください。
# """,
#                 callback_handler=None
#             )
            
#             # エージェントを実行
#             result = agent(user_message)
            
#             # レスポンスを返す
#             return {
#                 "response": result.message["content"]
#             }
    
#     except Exception as e:
#         # エラーハンドリング
#         return {
#             "error": f"エラーが発生しました: {str(e)}",
#             "detail": "Gatewayへの接続またはGoogle Calendar APIへのアクセスに失敗しました。"
#         }


# if __name__ == "__main__":
#     """
#     ローカル実行用のエントリーポイント
#     """
#     app.run()