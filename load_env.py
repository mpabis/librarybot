"""Simple .env file loader for environment variables."""

import os


def load_env_file(filepath=".env"):
    """Load environment variables from a .env file."""
    if not os.path.exists(filepath):
        print(f"❌ {filepath} file not found")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        
        #print(f"✅ Environment variables loaded from {filepath}")
        return True
    except Exception as e:
        print(f"❌ Error loading {filepath}: {e}")
        return False


if __name__ == "__main__":
    # Load .env file when this script is imported or run
    load_env_file()
