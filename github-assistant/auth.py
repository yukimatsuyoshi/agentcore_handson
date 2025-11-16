# get_user_token.py
"""
Cognitoユーザートークン取得
ユーザー名とパスワードを入力して、アクセストークンを取得する
"""
import boto3
import getpass
import hmac
import hashlib
import base64
from config import (
    COGNITO_USER_POOL_ID, 
    COGNITO_CLIENT_ID, 
    COGNITO_CLIENT_SECRET,
    AWS_REGION
)


def calculate_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    """
    Cognito Client Secret Hash計算
    
    Args:
        username: ユーザー名
        client_id: Cognito Client ID
        client_secret: Cognito Client Secret
        
    Returns:
        計算されたSecret Hash
    """
    message = username + client_id
    dig = hmac.new(
        client_secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()


def get_access_token(username: str, password: str) -> str:
    """
    Cognitoからアクセストークンを取得
    
    Args:
        username: Cognitoユーザー名
        password: パスワード
        
    Returns:
        アクセストークン
    """
    client = boto3.client('cognito-idp', region_name=AWS_REGION)
    
    # 認証パラメータ
    auth_params = {
        'USERNAME': username,
        'PASSWORD': password
    }
    
    # Client Secretがある場合、SECRET_HASHを追加
    if COGNITO_CLIENT_SECRET:
        secret_hash = calculate_secret_hash(username, COGNITO_CLIENT_ID, COGNITO_CLIENT_SECRET)
        auth_params['SECRET_HASH'] = secret_hash
    
    response = client.initiate_auth(
        ClientId=COGNITO_CLIENT_ID,
        AuthFlow='USER_PASSWORD_AUTH',
        AuthParameters=auth_params
    )
    
    return response['AuthenticationResult']['AccessToken']


if __name__ == "__main__":
    print("=" * 60)
    print("Cognito ユーザートークン取得")
    print("=" * 60)
    print()
    print(f"User Pool: {COGNITO_USER_POOL_ID}")
    print(f"Client ID: {COGNITO_CLIENT_ID}")
    print(f"Region: {AWS_REGION}")
    print()
    
    # ユーザー名入力
    username = input("ユーザー名: ")
    
    # パスワード入力（非表示）
    password = getpass.getpass("パスワード: ")
    
    print("\n🔐 認証中...")
    
    try:
        # トークン取得
        token = get_access_token(username, password)
        
        print("✅ トークン取得成功\n")
        print(f"Access Token (最初の50文字):")
        print(f"{token[:50]}...\n")
        
        # トークンをファイルに保存
        with open('user_token.txt', 'w') as f:
            f.write(token)
        
        print("💾 user_token.txt に保存しました")
        print("\n次のステップ:")
        print("  python test_with_user_auth.py")
        
    except Exception as e:
        error_code = e.response['Error']['Code'] if hasattr(e, 'response') else 'Unknown'
        
        if error_code == 'NotAuthorizedException':
            print("❌ 認証失敗: ユーザー名またはパスワードが間違っています")
            print("   または USER_PASSWORD_AUTH が有効になっていない可能性があります")
        elif error_code == 'UserNotFoundException':
            print("❌ エラー: ユーザーが見つかりません")
        else:
            print(f"❌ エラー ({error_code}): {e}")
            import traceback
            traceback.print_exc()