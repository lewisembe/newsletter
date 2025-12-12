# Docker Services - Newsletter Utils

This directory contains Docker configuration for the newsletter pipeline infrastructure.

## Services

- **PostgreSQL 16**: Primary database
- **pgAdmin 4**: Web-based database management UI
- **Redis 7**: Caching and session storage

## Quick Start

### Start All Services
```bash
docker-compose up -d
```

### Start Individual Services
```bash
docker-compose up -d postgres      # PostgreSQL only
docker-compose up -d pgadmin       # pgAdmin only
docker-compose up -d redis         # Redis only
```

### Stop Services
```bash
docker-compose down                # Stop (keep data)
docker-compose down -v             # Stop and remove volumes (DELETE ALL DATA)
```

## Access Services

### PostgreSQL
- **Host**: localhost
- **Port**: 5432
- **Database**: newsletter_db
- **User**: newsletter_user
- **Password**: newsletter_pass (from .env)

**CLI Access**:
```bash
docker-compose exec postgres psql -U newsletter_user -d newsletter_db
```

### pgAdmin
- **URL**: http://localhost:5050
- **Email**: admin@example.com (from .env ADMIN_EMAIL)
- **Password**: admin123 (from .env ADMIN_PASSWORD)

**Add PostgreSQL Server in pgAdmin**:
1. Right-click "Servers" → "Register" → "Server"
2. General tab → Name: Newsletter Database
3. Connection tab:
   - Host: postgres (Docker network name)
   - Port: 5432
   - Maintenance database: newsletter_db
   - Username: newsletter_user
   - Password: newsletter_pass
4. Save

### Redis
- **Host**: localhost
- **Port**: 6379

**CLI Access**:
```bash
docker-compose exec redis redis-cli
```

## Database Operations

### Backup Database
```bash
# Full backup
docker-compose exec -T postgres pg_dump -U newsletter_user newsletter_db > backup_$(date +%Y%m%d).sql

# Compressed backup
docker-compose exec -T postgres pg_dump -U newsletter_user newsletter_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Schema only
docker-compose exec -T postgres pg_dump -U newsletter_user --schema-only newsletter_db > schema_backup.sql
```

### Restore Database
```bash
# From SQL file
docker-compose exec -T postgres psql -U newsletter_user newsletter_db < backup.sql

# From compressed file
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U newsletter_user newsletter_db
```

### Query Database
```bash
# Execute SQL query
docker-compose exec postgres psql -U newsletter_user newsletter_db -c "SELECT COUNT(*) FROM urls;"

# Interactive SQL session
docker-compose exec postgres psql -U newsletter_user newsletter_db
```

### View Logs
```bash
# All services
docker-compose logs -f

# PostgreSQL only
docker-compose logs -f postgres

# Last 100 lines
docker-compose logs --tail=100 postgres
```

### Database Maintenance
```bash
# Vacuum and analyze
docker-compose exec postgres psql -U newsletter_user newsletter_db -c "VACUUM ANALYZE;"

# Check database size
docker-compose exec postgres psql -U newsletter_user newsletter_db -c "
SELECT
    pg_size_pretty(pg_database_size('newsletter_db')) as database_size;
"

# Check table sizes
docker-compose exec postgres psql -U newsletter_user newsletter_db -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Health Checks

### Check Service Status
```bash
docker-compose ps
```

### Test Database Connection
```bash
docker-compose exec postgres pg_isready -U newsletter_user -d newsletter_db
```

### Test Redis Connection
```bash
docker-compose exec redis redis-cli ping
```

## Troubleshooting

### PostgreSQL Not Starting
```bash
# Check logs
docker-compose logs postgres

# Reset PostgreSQL (WARNING: DELETES ALL DATA)
docker-compose down -v
docker-compose up -d postgres
```

### Connection Refused
```bash
# Wait for health check to pass
docker-compose ps

# Should show "healthy" status for postgres
# If "starting", wait a few more seconds
```

### Reset pgAdmin
```bash
# Remove pgAdmin data (will need to re-add servers)
docker-compose stop pgadmin
docker volume rm newsletter_utils_pgadmin_data
docker-compose up -d pgadmin
```

### View Container Resources
```bash
docker stats newsletter_postgres newsletter_pgadmin newsletter_redis
```

## Production Deployment

For production, use `docker-compose.prod.yml` (to be created) with:
- External volumes for data persistence
- Secrets management for passwords
- Resource limits
- Automated backups
- Monitoring integration

## Data Persistence

Data is stored in Docker volumes:
- `postgres_data`: PostgreSQL database files
- `pgadmin_data`: pgAdmin configuration
- `redis_data`: Redis persistence

**Location**: `/var/lib/docker/volumes/newsletter_utils_*`

**Backup volumes**:
```bash
docker run --rm -v newsletter_utils_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_data_backup.tar.gz /data
```

## Environment Variables

Configure in `.env` file:
- `POSTGRES_PASSWORD`: PostgreSQL password
- `ADMIN_EMAIL`: pgAdmin login email
- `ADMIN_PASSWORD`: pgAdmin login password

## Useful SQL Queries

### Table Information
```sql
-- List all tables
\dt

-- Describe table structure
\d urls

-- List indexes
\di

-- Show foreign keys
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';
```

### Performance Monitoring
```sql
-- Active connections
SELECT * FROM pg_stat_activity;

-- Slow queries (enable pg_stat_statements extension)
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;

-- Index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

## Support

For issues or questions:
1. Check container logs: `docker-compose logs`
2. Verify health status: `docker-compose ps`
3. Review this README
4. Check main project documentation
