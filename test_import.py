try:
    from bedrock_agentcore.identity.auth import requires_oauth
    print("✅ requires_oauth exists!")
except ImportError as e:
    print(f"❌ requires_oauth not found: {e}")