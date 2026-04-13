#!/bin/bash
set -e

echo "🚀 Setting up 0Latency Contribution Reviewer"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying template..."
    cp .env.template .env
    echo "📝 Please edit .env with your credentials before proceeding"
    exit 0
fi

# Source environment variables
set -a
source .env
set +a

# Initialize database
echo "🗄️  Setting up database..."
if command -v psql &> /dev/null; then
    echo "Creating database schema..."
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f schema.sql
    echo "✓ Database initialized"
else
    echo "⚠️  psql not found. Please run schema.sql manually:"
    echo "   psql -h $DB_HOST -U $DB_USER -d $DB_NAME -f schema.sql"
fi

# Create systemd service
echo "🔧 Setting up systemd service..."
SERVICE_FILE="/etc/systemd/system/0latency-reviewer.service"

if [ "$EUID" -eq 0 ]; then
    # Running as root, install service directly
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=0Latency Contribution Reviewer
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
EnvironmentFile=$(pwd)/.env
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable 0latency-reviewer
    echo "✓ Systemd service installed"
    echo "  Start with: sudo systemctl start 0latency-reviewer"
    echo "  Status: sudo systemctl status 0latency-reviewer"
else
    # Not root, provide instructions
    echo "⚠️  Not running as root. To install systemd service, run:"
    echo "   sudo bash setup.sh"
    echo ""
    echo "Or manually copy scripts/0latency-reviewer.service to /etc/systemd/system/"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Configure GitHub webhook:"
echo "   URL: http://your-server:8765/contribution-review"
echo "   Content type: application/json"
echo "   Secret: (value from GITHUB_WEBHOOK_SECRET in .env)"
echo "   Events: Issues, Pull requests"
echo ""
echo "2. Start the service:"
if [ "$EUID" -eq 0 ]; then
    echo "   sudo systemctl start 0latency-reviewer"
else
    echo "   python main.py"
fi
echo ""
echo "3. Test the webhook:"
echo "   curl http://localhost:8765/health"
