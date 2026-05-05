# Stage 01 Evidence — db_migrate.sh real human gate

**Outcome:** SHIPPED
**Commit:** 433c72b
**Files touched:** scripts/db_migrate.sh

## Verification commands

```bash
$ grep -c sleep scripts/db_migrate.sh
0

$ grep -c /dev/tty scripts/db_migrate.sh
2

$ grep "Type .apply." scripts/db_migrate.sh
    echo "Type apply (lowercase, exact) to confirm prod migration."
    echo "Type apply (lowercase, exact) to confirm prod downgrade."
```

## Last 20 lines of verification output

```
sleep 5 count:
0
/dev/tty count:
2
    echo "Type apply (lowercase, exact) to confirm prod migration."
    echo "Type apply (lowercase, exact) to confirm prod downgrade."
G2-S01 PASS
```

## Outcome category

SHIPPED
