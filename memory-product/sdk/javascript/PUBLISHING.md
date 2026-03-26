# Publishing Guide for @0latency/sdk

## Pre-Publishing Checklist

- [ ] All tests pass: `npm test`
- [ ] Code builds successfully: `npm run build`
- [ ] Live API test passes: `npx ts-node test-live-api.ts`
- [ ] README.md is complete and accurate
- [ ] package.json version is correct
- [ ] LICENSE file is present

## First-Time Setup

### 1. Create npm Account
If you don't have an npm account:
```bash
npm adduser
```

### 2. Create Organization (Optional but Recommended)
To publish under `@0latency` scope:
1. Go to https://www.npmjs.com
2. Create an organization named `0latency`
3. Add your account as a member

### 3. Login to npm
```bash
npm login
```

## Publishing Steps

### 1. Update Version
```bash
# For patch releases (bug fixes)
npm version patch

# For minor releases (new features, backward compatible)
npm version minor

# For major releases (breaking changes)
npm version major
```

### 2. Build and Test
```bash
npm run build
npm test
```

### 3. Test Live API
Set your API key and run the integration test:
```bash
export ZEROLATENCY_API_KEY="your-api-key"
npx ts-node test-live-api.ts
```

### 4. Publish to npm
```bash
# Dry run first to see what will be published
npm publish --dry-run --access public

# Actually publish
npm publish --access public
```

**Note:** The `--access public` flag is required for scoped packages (@0latency/sdk) to be publicly available.

### 5. Verify Publication
```bash
npm info @0latency/sdk
```

Visit: https://www.npmjs.com/package/@0latency/sdk

### 6. Tag the Release (Optional)
```bash
git tag v0.1.0
git push --tags
```

## Post-Publishing

### 1. Update Documentation
Update any references to the package version in:
- README.md
- Site documentation at 0latency.ai
- Example code

### 2. Announce
- Update website with SDK availability
- Tweet/post about the release
- Update Discord/community channels

### 3. Monitor
- Watch for issues on GitHub
- Monitor download stats on npm
- Check for user feedback

## Troubleshooting

### "You must verify your email"
```bash
npm profile set email your-email@example.com
# Check email and click verification link
```

### "You do not have permission to publish"
Make sure you're logged in and have access to the @0latency organization:
```bash
npm whoami
npm org ls 0latency
```

### "Package name too similar to existing package"
If @0latency/sdk is taken, consider alternatives:
- `@0latency/client`
- `@0latency/memory-sdk`
- `zerolatency-sdk`

## Quick Reference

```bash
# Install dependencies
npm install

# Build
npm run build

# Test
npm test

# Live API test (set ZEROLATENCY_API_KEY first)
npx ts-node test-live-api.ts

# Publish
npm publish --access public
```

## Package Files

The following files will be included in the published package (see `package.json` files array):
- `dist/` - Compiled JavaScript and type definitions
- `README.md` - Package documentation
- `LICENSE` - MIT license

Source TypeScript files (`src/`) are NOT included in the published package.
