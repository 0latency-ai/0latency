# Disaster Recovery Plan - 0Latency API

## Current Architecture
- **Primary DB**: Supabase PostgreSQL (AWS us-east-1)
- **Backups**: Supabase Point-in-Time Recovery (PITR) - 7 days
- **RTO**: 4 hours
- **RPO**: 15 minutes (Supabase backup frequency)

## Backup Strategy

### Automated Backups (Supabase Native)
- **Frequency**: Continuous WAL archiving
- **Retention**: 7 days (Pro plan)
- **Storage**: Supabase S3 buckets (encrypted)
- **Recovery**: Via Supabase dashboard or CLI

### Supplementary Exports

Daily export job (cron):
```bash
0 2 * * * /root/scripts/backup-0latency.sh
```

Script: `scripts/backup-0latency.sh`
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
BACKUP_DIR="/root/backups/0latency"
mkdir -p $BACKUP_DIR

PGPASSWORD=jcYlwEhuHN9VcOuj pg_dump \
  -h aws-1-us-east-1.pooler.supabase.com \
  -U postgres.fuojxlabvhtmysbsixdn \
  -d postgres \
  --schema=memory_service \
  > $BACKUP_DIR/0latency-$DATE.sql

# Compress
gzip $BACKUP_DIR/0latency-$DATE.sql

# Upload to R2/S3 (configure after setup)
# aws s3 cp $BACKUP_DIR/0latency-$DATE.sql.gz s3://0latency-backups/

# Clean old backups (keep 30 days local)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup complete: 0latency-$DATE.sql.gz"
```

### Recovery Procedures

#### Scenario 1: Supabase Total Outage
1. Check status: https://status.supabase.com
2. If prolonged (>2h):
   - Restore latest backup to new Supabase project
   - Update `MEMORY_DB_CONN` environment variable
   - Restart API servers (`systemctl restart memory-api`)
   - Estimated downtime: 2-4 hours

#### Scenario 2: Data Corruption
1. Identify corruption timestamp
2. Request PITR from Supabase support (ticket via dashboard)
3. Restore to specific point-in-time
4. Verify data integrity via test queries
5. Resume operations

#### Scenario 3: Accidental Data Deletion
1. Stop API immediately (`systemctl stop memory-api`)
2. Restore from most recent backup before deletion
3. Compare with production to identify gap
4. Manually reconcile missing data (if any)
5. Restart API

## Testing Schedule

- **Monthly**: Test restore from backup to staging environment
- **Quarterly**: Full DR drill with failover simulation
- **Annually**: Review and update this document

## Emergency Contacts

- **Supabase Support**: support@supabase.com (Pro plan: priority support)
- **Primary Admin**: justin@0latency.ai
- **Hosting**: DigitalOcean (thomas-server, 164.90.156.169)

## Last Updated
2026-03-25 - Initial version
