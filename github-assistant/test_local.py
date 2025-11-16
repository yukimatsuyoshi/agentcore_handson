"""
エンドユーザー認証（JWT）でAgentをテスト（HTTPS経由）
"""
import requests
import json
from urllib.parse import quote
from config import AWS_REGION

AGENT_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:605664253368:runtime/gitHub_slack_assistant-TUpC4S6NOh"


def invoke_agent_with_jwt(prompt: str):
    """JWTトークンでAgentを呼び出し（HTTPS経由）"""
    
    # トークン読み込み
    with open('user_token.txt', 'r') as f:
        access_token = f.read().strip()
    
    # ARNをURLエンコード
    encoded_arn = quote(AGENT_RUNTIME_ARN, safe='')
    
    # Runtime URL組み立て
    url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    print(f"🔐 トークン: {access_token[:30]}...")
    print(f"📍 URL: {url[:100]}...")
    print()
    
    # HTTPS リクエスト
    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json={"prompt": prompt},
        timeout=60
    )
    
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print()
    
    if response.status_code == 200:
        return response.text
    else:
        print(f"❌ エラーレスポンス: {response.text}")
        response.raise_for_status()


if __name__ == "__main__":
    print("=" * 60)
    print("JWT認証テスト（HTTPS）")
    print("=" * 60)
    print()
    
    try:
        result = invoke_agent_with_jwt("こんにちは！")
        print("✅ 成功\n")
        print(f"応答:\n{result}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()