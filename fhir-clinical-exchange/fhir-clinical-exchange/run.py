import sys
from app import create_app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    db = sys.argv[2] if len(sys.argv) > 2 else ":memory:"
    create_app(db).run(port=port, debug=False)
