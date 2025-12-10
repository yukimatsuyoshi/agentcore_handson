import os
from typing import Dict, Any
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


app = BedrockAgentCoreApp()


async def get_access_token(cognito_scope: str) -> str:
    @requires_access_token(
        provider_name="resource-provider-oauth-client-0x105",
        scopes=[cognito_scope],
        auth_flow="M2M",
        force_authentication=False,
    )
    async def _get_token(*, access_token: str) -> str:
        return access_token

    token = await _get_token()
    return token


def get_full_tools_list(client):
    more_tools = True
    tools = []
    pagination_token = None

    while more_tools:
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)

        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True
            pagination_token = tmp_tools.pagination_token

    return tools


async def access_github(payload: Dict[str, Any], gateway_url: str, cognito_scope: str) -> Dict[str, Any]:
    try:
        access_token = await get_access_token(cognito_scope)

        def create_streamable_http_transport():
            transport = streamablehttp_client(
                gateway_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return transport

        mcp_client = MCPClient(create_streamable_http_transport)

        with mcp_client:
            tools = get_full_tools_list(mcp_client)

            agent = Agent(
                name="github_assistant",
                model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
                system_prompt="""
あなたはGitHub Issues管理アシスタントです。

【あなたができること】
- GitHub Issues操作
  - Issueの一覧取得・検索・フィルタリング
  - Issueの作成（タイトル、本文、ラベル、アサイニー設定）
  - Issueの更新（状態変更、コメント追加、ラベル編集）
  - Issueの詳細情報取得
  - コメントの投稿と管理

【ツール選択の方針】
- ユーザーがGitHub Issuesに関する意図を述べたら適切なツールを使う
  - 例：「Issueを作成」「一覧を取得」「コメントを追加」など
- 複合依頼（例：「検索して一覧を表示」）は適切な順序で実行する

【GitHub Issues ツール利用ルール】
- 利用可能なツール名は tool_config の一覧（tools/list）に従う
  - 代表例: `issues___list`, `issues___get`, `issues___create`, `issues___update`, `issues___create_comment` など
- `issues___list`:
  - パラメータ: `owner`, `repo`, `state`（open/closed/all）, `labels`, `sort`, `direction`
  - ページング: `page` と `per_page` パラメータでページングをサポート
- `issues___create`:
  - 必須: `owner`, `repo`, `title`
  - オプション: `body`, `labels`, `assignees`
- `issues___update`:
  - 必須: `owner`, `repo`, `issue_number`
  - オプション: `state`, `title`, `body`, `labels`, `assignees`
- `issues___create_comment`:
  - 必須: `owner`, `repo`, `issue_number`, `body`

【応答ルール】
- Issue情報を提示する際は、以下を明確に表示：
  - Issue番号、タイトル、状態（Open/Closed）
  - 作成者、作成日時
  - ラベル（ある場合）
  - 本文の要約（長い場合）
- 操作結果は明確に報告（成功/失敗、変更内容）
- エラーが発生した場合は、分かりやすく原因と対処法を説明

ユーザーの意図を正しく読み取り、適切なツールを選択し、明確で実用的な結果を返してください。
""",
                tools=tools,
            )

            user_message = payload.get("prompt", "")
            response = agent(user_message)

            return response

    except Exception as e:
        error_msg = f"エージェント実行エラー: {str(e)}"
        return {
            "error": error_msg,
            "details": "エージェントの実行中にエラーが発生しました。"
        }


@app.entrypoint
async def github_agent(payload: Dict[str, Any]):
    gateway_url = os.environ.get("GATEWAY_URL")
    cognito_scope = os.environ.get("COGNITO_SCOPE")

    if not gateway_url:
        raise ValueError("環境変数 GATEWAY_URL が設定されていません")
    if not cognito_scope:
        raise ValueError("環境変数 COGNITO_SCOPE が設定されていません")

    try:
        response = await access_github(payload, gateway_url, cognito_scope)
        return response

    except Exception as e:
        error_msg = f"エントリーポイントでエラー発生: {str(e)}"
        return {
            "error": error_msg,
            "details": "エージェントの起動に失敗しました。環境変数を確認してください。"
        }


if __name__ == "__main__":
    app.run()
