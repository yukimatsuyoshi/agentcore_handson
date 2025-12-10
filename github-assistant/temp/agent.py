import os
import logging
from typing import Dict, Any
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GitHubAgentWithIdentity:
    """
    AgentCore IdentityとGatewayを使用してGitHub Issuesを操作するエージェント。
    Strands Agentsを使用した実装。
    """

    def __init__(self):
        """環境変数から設定を読み込み"""
        self.gateway_url = os.environ.get("GATEWAY_URL")
        self.cognito_scope = os.environ.get("COGNITO_SCOPE")
        self.workload_name = os.environ.get("WORKLOAD_NAME", "github-agent")
        
        # 環境変数の検証
        if not self.gateway_url:
            raise ValueError("環境変数 GATEWAY_URL が設定されていません")
        if not self.cognito_scope:
            raise ValueError("環境変数 COGNITO_SCOPE が設定されていません")
        
        logger.info(f"GitHubエージェント初期化完了")
        logger.info(f"Gateway URL: {self.gateway_url}")
        logger.info(f"Cognito Scope: {self.cognito_scope}")

    async def get_access_token(self) -> str:
        """
        AgentCore Identityを使用してアクセストークンを取得。
        
        Runtime環境では、@requires_access_tokenデコレータが以下を自動処理：
        1. Workload Access Token (WAT)の取得
        2. WATを使用してOAuthトークンを取得
        3. access_tokenパラメータとして注入
        
        Returns:
            str: Gatewayへのアクセストークン
        """
        @requires_access_token(
            provider_name="resource-provider-oauth-client-f14bh",
            scopes=[self.cognito_scope],
            auth_flow="M2M",
            force_authentication=False,
        )
        async def _get_token(*, access_token: str) -> str:
            """
            内部関数。デコレータによってaccess_tokenが注入される。
            
            Args:
                access_token: OAuthアクセストークン（デコレータが注入）
            
            Returns:
                str: APIコール用のアクセストークン
            """
            return access_token
        
        logger.info("アクセストークン取得中...")
        token = await _get_token()
        logger.info("アクセストークン取得完了")
        return token

    async def access_github(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        GitHub Issuesにアクセスする完全なフロー。
        
        フロー：
        1. Identityからアクセストークンを取得
        2. トークンを使用してMCPクライアントを作成
        3. Gatewayとの接続を確認（ツール一覧取得）
        4. Strands Agentを作成
        5. ユーザーのリクエストを処理
        
        Args:
            payload: AgentCore Runtimeからのペイロード
                - prompt: ユーザーからの入力メッセージ
        
        Returns:
            エージェントからのレスポンス
        """
        try:
            # ステップ1: アクセストークン取得
            access_token = await self.get_access_token()
            
            # ステップ2: 認証済みMCPクライアント作成
            def create_streamable_http_transport():
                """
                Bearerトークン認証付きHTTPトランスポート作成。
                このトランスポートでGatewayとの認証済み通信を行う。
                """
                transport = streamablehttp_client(
                    self.gateway_url,
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                return transport
            
            def get_full_tools_list(client):
                """
                ページネーション対応のツール一覧取得。
                
                Args:
                    client: MCPクライアントインスタンス
                
                Returns:
                    list: 利用可能な全ツールのリスト
                """
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
            
            # MCPクライアント作成
            mcp_client = MCPClient(create_streamable_http_transport)
            
            # ステップ3: Gatewayとの接続確認
            with mcp_client:
                # 利用可能なツール一覧を取得
                tools = get_full_tools_list(mcp_client)
                
                # ツール名を取得（デバッグ用）
                try:
                    tools_names = [
                        getattr(tool, 'tool_name', getattr(tool, 'name', str(tool))) 
                        for tool in tools
                    ]
                    logger.info(f"利用可能なツール: {', '.join(tools_names)}")
                except Exception as e:
                    logger.warning(f"ツール名の取得に失敗: {e}")
                
                # ステップ4: Strands Agentを作成
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
                
                # ステップ5: ユーザーリクエストの処理
                user_message = payload.get("prompt", "")
                logger.info(f"ユーザーメッセージ: {user_message}")
                
                # エージェントを実行（ストリーミングなし）
                response = agent(user_message)
                
                logger.info("GitHubへのアクセス完了")
                
                return response
                
        except Exception as e:
            error_msg = f"エージェント実行エラー: {str(e)}"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "details": "エージェントの実行中にエラーが発生しました。"
            }


# AgentCoreアプリケーションを初期化
app = BedrockAgentCoreApp()


@app.entrypoint
async def github_agent(payload: Dict[str, Any]):
    """
    GitHub Issuesエージェントのメインエントリーポイント。
    
    このエントリーポイントはAgentCore Runtimeから呼び出される。
    
    Args:
        payload: AgentCore Runtimeから渡されるペイロード
            - prompt: ユーザーからの入力メッセージ
    
    Returns:
        エージェントからのレスポンス
    """
    logger.info("=== GitHubエージェント起動 ===")
    
    # エージェントインスタンスを作成
    agent_with_identity = GitHubAgentWithIdentity()
    
    try:
        # エージェントを実行してレスポンスを取得
        response = await agent_with_identity.access_github(payload)
        
        logger.info("=== GitHubエージェント終了 ===")
        
        return response
                
    except Exception as e:
        error_msg = f"エントリーポイントでエラー発生: {str(e)}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "details": "エージェントの起動に失敗しました。環境変数を確認してください。"
        }


if __name__ == "__main__":
    app.run()