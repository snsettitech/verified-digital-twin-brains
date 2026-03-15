import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
GRAPHITI_DIR = ROOT / '.mcp' / 'graphiti' / 'mcp_server'
CONFIG_PATH = GRAPHITI_DIR / 'config' / 'config-local-neo4j-8001.yaml'

# Load project envs without duplicating secrets into Graphiti files.
for env_path in [ROOT / '.env', ROOT / 'backend' / '.env']:
    if env_path.exists():
        load_dotenv(env_path, override=False)

# Graphiti expects NEO4J_USER, while this project uses NEO4J_USERNAME in root .env.
if not os.getenv('NEO4J_USER') and os.getenv('NEO4J_USERNAME'):
    os.environ['NEO4J_USER'] = os.environ['NEO4J_USERNAME']

os.environ['CONFIG_PATH'] = str(CONFIG_PATH)

sys.path.insert(0, str(GRAPHITI_DIR / 'src'))
from graphiti_mcp_server import main

if __name__ == '__main__':
    if '--config' not in sys.argv:
        sys.argv.extend(['--config', str(CONFIG_PATH)])
    main()
