# NPM Publish Instructions for @0latency/mcp-server

## Prerequisites
- NPM account with publish access to @0latency scope
- Authentication token configured (`npm login` or npm token in ~/.npmrc)
- Clean working directory (all changes committed)

## Pre-Publish Checklist
- [x] Version bumped in package.json (currently: 0.2.2)
- [x] CHANGELOG.md updated with release notes
- [x] Code builds successfully (`npm run build`)
- [x] Tests pass (config merge verified)
- [x] Git branch created: `cp9-1-4-mcp-init`

## Publish Command

```bash
npm publish --access public
```

**Important**: This command is operator-gated. Only run after:
1. Code review and approval
2. Testing in staging environment (if applicable)
3. Branch merged to master

## Post-Publish
- Verify package on npmjs.com: https://www.npmjs.com/package/@0latency/mcp-server
- Test installation: `npx @0latency/mcp-server@0.2.2 init`
- Update documentation/README if needed
- Tag release in git: `git tag v0.2.2 && git push origin v0.2.2`

## Rollback (if needed)
```bash
npm unpublish @0latency/mcp-server@0.2.2
# or
npm deprecate @0latency/mcp-server@0.2.2 "Version deprecated due to [reason]"
```

## Current State
- Branch: `cp9-1-4-mcp-init`
- Version: 0.2.2
- Status: Ready for publish (pending operator approval)
- Builds: ✓ Passing
- Tests: ✓ Config merge verified
