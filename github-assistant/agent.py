"""
GitHub Issues 管理 + Slack 通知 Agent
"""
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from config import (
    GATEWAY_ENDPOINT, 
    GATEWAY_ID, 
    DEFAULT_REPOSITORY, 
    DEFAULT_SLACK_CHANNEL,
    COGNITO_DOMAIN,
    COGNITO_CLIENT_ID,
    COGNITO_CLIENT_SECRET,
    GATEWAY_M2M_CLIENT_ID,
    GATEWAY_M2M_CLIENT_SECRET
)
import requests
import os

app = BedrockAgentCoreApp()

# Cognito OAuth用のClient Credentials
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", COGNITO_CLIENT_ID)
CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", COGNITO_CLIENT_SECRET) 
TOKEN_URL = f"https://{COGNITO_DOMAIN}/oauth2/token"


def fetch_access_token(client_id: str, client_secret: str, token_url: str) -> str:
    """Cognitoからアクセストークンを取得"""
    # response = requests.post(
    #     token_url,
    #     data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}",
    #     headers={'Content-Type': 'application/x-www-form-urlencoded'}
    # )
    response = requests.post(
        token_url,
        data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}&scope=gateway/access",
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )


    # デバッグ用
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    return response.json()['access_token']


def create_streamable_http_transport(mcp_url: str, access_token: str):
    """MCP用のHTTPトランスポート作成"""
    return streamablehttp_client(
        mcp_url, 
        headers={"Authorization": f"Bearer {access_token}"}
    )


def get_full_tools_list(client):
    """ページネーション対応のツール一覧取得"""
    more_tools = True
    tools = []
    pagination_token = None
    
    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            pagination_token = tmp_tools.pagination_token
            
    return tools


# MCPエンドポイント
gateway_mcp_url = f"{GATEWAY_ENDPOINT}/mcp"


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Agent エントリーポイント"""
    import traceback

    user_message = payload.get("prompt", "")
    print(f"[DEBUG] Received prompt: {user_message}")

    # ★ 追加：Runtime経由のユーザー情報を確認
    print(f"[DEBUG] Full payload: {payload}")
    
    # ★ 追加：環境変数の確認（Runtimeが何を渡しているか）
    print(f"[DEBUG] Environment variables related to auth:")
    for key in os.environ:
        if 'AUTH' in key.upper() or 'TOKEN' in key.upper() or 'USER' in key.upper():
            print(f"  {key}: {os.environ[key][:30] if len(os.environ[key]) > 30 else os.environ[key]}...")

    if not user_message:
        return {"result": "メッセージを入力してください。", "error": "EMPTY_PROMPT"}

    context = payload.get("context", {})
    repository = context.get("repository", DEFAULT_REPOSITORY)
    slack_channel = context.get("slack_channel", DEFAULT_SLACK_CHANNEL)

    try:
        print(f"[DEBUG] Fetching access token...")
        print(f"[DEBUG] TOKEN_URL: {TOKEN_URL}")
        print(f"[DEBUG] CLIENT_ID: {GATEWAY_M2M_CLIENT_ID[:10]}...")

        # アクセストークン取得
        #access_token = fetch_access_token(CLIENT_ID, CLIENT_SECRET, TOKEN_URL)
        access_token = fetch_access_token(GATEWAY_M2M_CLIENT_ID, GATEWAY_M2M_CLIENT_SECRET, TOKEN_URL)
        print(f"[DEBUG] Access token obtained: {access_token[:20]}...")
        
        # MCPクライアントでツールを取得
        print(f"[DEBUG] Gateway MCP URL: {gateway_mcp_url}")
        mcp_client = MCPClient(
            lambda: create_streamable_http_transport(gateway_mcp_url, access_token)
        )
        print(f"[DEBUG] MCP Client created")

        with mcp_client:
            print(f"[DEBUG] Entering MCP client context")
            tools = get_full_tools_list(mcp_client)
            print(f"[DEBUG] Tools retrieved: {len(tools)} tools")
            print(f"利用可能なツール: {[tool.tool_name for tool in tools]}")
            
            # Agentを作成（ツールを渡す）
            agent = Agent(
                name="github_slack_assistant",
                model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
                system_prompt=f"""
あなたは GitHub Issues を管理し、Slack に通知を送る専門アシスタントです。

## 利用可能なツール

{len(tools)}個のツールが利用可能です。

## 動作ルール

1. ユーザーの意図を正確に理解
2. Issue 作成/更新前にユーザー確認
3. Slack 通知は見やすく整形
4. エラー時は具体的な原因と対処法を説明
5. 日本語で分かりやすく整形

## デフォルト値
- リポジトリ: {repository}
- Slack チャンネル: {slack_channel}

## 注意事項
- 大量操作時は進捗報告
- 個人情報を Slack に投稿しない
""",
                tools=tools  # MCPから取得したツールを渡す
            )
            
            # Agent実行
            result = agent(user_message)  

            return {
                "result": result.content if hasattr(result, 'content') else str(result),
                "metadata": {
                    "repository": repository,
                    "slack_channel": slack_channel,
                    "tools_count": len(tools)
                }
            }

    except Exception as e:
        import traceback
        print(f"[ERROR] Exception occurred: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return {
            "result": f"エラー: {str(e)}",
            "error": "AGENT_EXECUTION_ERROR",
            "details": str(e)
        }


if __name__ == "__main__":
    app.run()