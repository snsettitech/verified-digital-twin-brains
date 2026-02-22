#!/usr/bin/env python3
"""Test script for Dumpling AI MCP server."""
import subprocess
import json
import os
import sys

def test_mcp_server():
    """Test the MCP server by listing tools and calling one."""
    
    env = os.environ.copy()
    env["DUMPLING_API_KEY"] = "sk_7ACSMqhaVJNYsDsLQSUfMmjV3xKfc7kZgXiYJQySr8lKc1mR"
    
    print("=" * 70)
    print("Testing Dumpling AI MCP Server")
    print("=" * 70)
    
    # Test 1: List tools
    print("\n1. Listing available tools...")
    list_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    proc = subprocess.Popen(
        ["npx.cmd", "-y", "mcp-server-dumplingai@latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    proc.stdin.write(json.dumps(list_request) + "\n")
    proc.stdin.flush()
    
    # Read response (with timeout)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
    
    stdout, stderr = proc.communicate()
    
    # Parse the response (might have multiple JSON lines)
    tools = []
    for line in stdout.strip().split('\n'):
        if line.startswith('{'):
            try:
                response = json.loads(line)
                if 'result' in response and 'tools' in response['result']:
                    tools = response['result']['tools']
                    break
            except json.JSONDecodeError:
                continue
    
    if tools:
        print(f"[OK] Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description'][:60]}...")
    else:
        print("[FAIL] Failed to list tools")
        print(f"STDERR: {stderr[:500]}")
        return False
    
    # Test 2: Call YouTube transcript tool
    print("\n2. Testing YouTube transcript extraction...")
    print("   Video: https://www.youtube.com/watch?v=6iilze3aDkU")
    
    call_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "get-youtube-transcript",
            "arguments": {
                "videoUrl": "https://www.youtube.com/watch?v=6iilze3aDkU",
                "includeTimestamps": False,
                "preferredLanguage": "en"
            }
        }
    }
    
    proc = subprocess.Popen(
        ["npx.cmd", "-y", "mcp-server-dumplingai@latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    proc.stdin.write(json.dumps(call_request) + "\n")
    proc.stdin.flush()
    
    # Read response (with timeout)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.terminate()
    
    stdout, stderr = proc.communicate()
    
    # Parse response
    transcript = None
    for line in stdout.strip().split('\n'):
        if line.startswith('{'):
            try:
                response = json.loads(line)
                if 'result' in response and 'content' in response['result']:
                    content = response['result']['content']
                    if content and len(content) > 0:
                        transcript = content[0].get('text', '')
                        break
            except json.JSONDecodeError:
                continue
    
    if transcript:
        print(f"[OK] Successfully extracted transcript ({len(transcript)} characters)")
        print(f"   Preview: {transcript[:150]}...")
    else:
        print("[FAIL] Failed to extract transcript")
        print(f"STDERR: {stderr[:500]}")
        return False
    
    # Test 3: Call web scraping tool
    print("\n3. Testing web scraping...")
    print("   URL: https://example.com")
    
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "scrape",
            "arguments": {
                "url": "https://example.com",
                "format": "markdown",
                "cleaned": True
            }
        }
    }
    
    proc = subprocess.Popen(
        ["npx.cmd", "-y", "mcp-server-dumplingai@latest"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    
    proc.stdin.write(json.dumps(call_request) + "\n")
    proc.stdin.flush()
    
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.terminate()
    
    stdout, stderr = proc.communicate()
    
    content = None
    for line in stdout.strip().split('\n'):
        if line.startswith('{'):
            try:
                response = json.loads(line)
                if 'result' in response and 'content' in response['result']:
                    content_items = response['result']['content']
                    if content_items and len(content_items) > 0:
                        content = content_items[0].get('text', '')
                        break
            except json.JSONDecodeError:
                continue
    
    if content:
        print(f"[OK] Successfully scraped webpage ({len(content)} characters)")
        print(f"   Preview: {content[:150]}...")
    else:
        print("[FAIL] Failed to scrape webpage")
        print(f"STDERR: {stderr[:500]}")
        return False
    
    print("\n" + "=" * 70)
    print("All tests passed! [OK]")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)
