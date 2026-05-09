# Dashboard Files

Static frontend pages for 0Latency platform.

## Deployment

Dashboard files are deployed to the production server at:

```
/var/www/0latency/
```

### Current Pages

- `auth/device.html` - OAuth device code approval page
  - Deploy path: `/var/www/0latency/auth/device.html`
  - URL: `https://0latency.ai/auth/device`
  - Purpose: Device code flow approval UI (user enters code, approves access)

## Development

To update dashboard pages:

1. Edit files in this `dashboard/` directory
2. Test locally if possible
3. Commit changes to git
4. Deploy to server by copying to `/var/www/0latency/`

Example deploy:

```bash
# Copy updated file to production
sudo cp dashboard/auth/device.html /var/www/0latency/auth/device.html
sudo chown www-data:www-data /var/www/0latency/auth/device.html
sudo chmod 644 /var/www/0latency/auth/device.html
```

## Notes

- These are static HTML files served by nginx
- No build step required
- Changes take effect immediately after file copy
- Keep files tracked in git even though they are deployed manually
