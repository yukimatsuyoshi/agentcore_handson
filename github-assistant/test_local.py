"""
test_local.py
"""
from agent import invoke

def test_simple():
    payload = {"prompt": "こんにちは！"}
    result = invoke(payload)
    print(f"結果: {result['result']}")

if __name__ == "__main__":
    test_simple()