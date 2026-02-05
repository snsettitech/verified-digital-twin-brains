import subprocess
import sys
import os

def run_step(name, command):
    print(f"🔍 Running {name}...")
    try:
        cmd_list = command.split()
        # On Windows, 'bash' might not be in PATH but git bash is often available
        # We use shell=True for better command resolution on Windows
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {name} Passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {name} FAILED")
        print(e.stdout)
        print(e.stderr)
        return False

def main():
    print("🚀 AI Stop-Hook: Starting verification pipeline...")
    
    # 1. Quality Gate
    # On Windows, we might need to run individual components if bash is weird
    # But let's try the quality script first
    if not run_step("Quality Gate", "bash scripts/ai-verify-quality.sh"):
        sys.exit(1)
        
    # 2. Governance Gate
    if not run_step("Governance Gate", f"{sys.executable} scripts/ai-verify-governance.py"):
        sys.exit(1)
        
    print("✅ AI Gates Passed! Proceeding with auto-commit...")
    
    # 3. Auto-Commit
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "AI: verified change passing quality + governance checks"], check=True)
        print("🎉 AI change committed successfully!")
    except Exception as e:
        print(f"⚠️ Git commit failed (likely no changes or git not configured): {e}")
        # We don't exit with error here because gates actually passed
        
    print("\n✨ Ready for push.")

if __name__ == "__main__":
    main()
