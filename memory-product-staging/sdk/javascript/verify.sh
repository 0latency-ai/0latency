#!/bin/bash
# Verification script for @0latency/sdk
# Run this before publishing to npm

set -e

echo "=== 0Latency SDK Verification ==="
echo

# Check Node.js version
echo "1. Checking Node.js version..."
node_version=$(node -v)
echo "   Node.js: $node_version"
if [[ "$node_version" < "v18" ]]; then
    echo "   ⚠️  Warning: Node.js 18+ recommended for native fetch support"
else
    echo "   ✅ Node.js version OK"
fi
echo

# Check npm
echo "2. Checking npm..."
npm --version
echo "   ✅ npm available"
echo

# Check dependencies
echo "3. Checking dependencies..."
if [ ! -d "node_modules" ]; then
    echo "   Installing dependencies..."
    npm install
else
    echo "   ✅ Dependencies installed"
fi
echo

# Build
echo "4. Building TypeScript..."
npm run build
echo "   ✅ Build successful"
echo

# Run tests
echo "5. Running unit tests..."
npm test
echo "   ✅ Tests passed"
echo

# Check dist output
echo "6. Verifying dist/ output..."
if [ ! -f "dist/index.js" ] || [ ! -f "dist/index.d.ts" ]; then
    echo "   ❌ Missing dist files"
    exit 1
fi
echo "   ✅ Dist files present"
echo

# Check package contents
echo "7. Checking package contents..."
npm pack --dry-run > /tmp/pack-output.txt 2>&1
package_size=$(grep "package size:" /tmp/pack-output.txt | awk '{print $4 $5}')
echo "   Package size: $package_size"
echo "   ✅ Package ready"
echo

# Check for required files
echo "8. Checking required files..."
required_files=("README.md" "LICENSE" "package.json" "dist/index.js" "dist/index.d.ts")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "   ❌ Missing: $file"
        exit 1
    fi
done
echo "   ✅ All required files present"
echo

# Summary
echo "=== Verification Complete ==="
echo
echo "✅ All checks passed!"
echo
echo "Ready to publish:"
echo "  npm login"
echo "  npm publish --access public"
echo
echo "Or test locally:"
echo "  export ZEROLATENCY_API_KEY='your-key'"
echo "  npx ts-node test-live-api.ts"
