# JWT Secret Key Rotation Guide

## Problema
Cambiar `JWT_SECRET_KEY` invalida todos los tokens existentes, forzando a los usuarios a cerrar sesión y borrar cookies.

## Solución: Rotación de Claves
El sistema ahora soporta **múltiples JWT secrets simultáneamente**, permitiendo rotación gradual sin invalidar sesiones activas.

## Cómo Rotar el JWT Secret

### Paso 1: Añadir el Nuevo Secret (Sin Invalidar Sesiones)

Edita `.env` y **mueve** el JWT_SECRET_KEY actual a JWT_SECRET_KEY_OLD:

```bash
# .env

# ANTES:
JWT_SECRET_KEY=IUli0qAhh5T8JHzVOzSNVvBQEBw3k24xdDGoDQkbEkM

# DESPUÉS:
JWT_SECRET_KEY=TU_NUEVO_SECRET_AQUI_12345678901234567890
JWT_SECRET_KEY_OLD=IUli0qAhh5T8JHzVOzSNVvBQEBw3k24xdDGoDQkbEkM  # ← Secret antiguo
```

### Paso 2: Restart Backend

```bash
docker-compose restart backend
```

**Resultado:**
- ✅ Nuevos logins usan el nuevo secret (`JWT_SECRET_KEY`)
- ✅ Sesiones antiguas siguen funcionando (validadas con `JWT_SECRET_KEY_OLD`)
- ✅ Usuarios NO necesitan volver a loguearse

### Paso 3: Monitorear Logs (Opcional)

Verifica cuántos usuarios siguen usando el secret antiguo:

```bash
docker-compose logs -f backend | grep "old secret key"
```

Verás logs como:
```
INFO: Token validated with old secret key (index 1)
```

### Paso 4: Remover Secret Antiguo (Después de X Días)

Cuando ya no veas usuarios con el secret antiguo (o después del tiempo de expiración de tokens, ej: 30 días), puedes remover la línea:

```bash
# .env
JWT_SECRET_KEY=TU_NUEVO_SECRET_AQUI_12345678901234567890
# JWT_SECRET_KEY_OLD=...  ← Eliminar esta línea
```

```bash
docker-compose restart backend
```

## Generar Nuevos Secrets Seguros

```bash
# Opción 1: Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Opción 2: OpenSSL
openssl rand -base64 32

# Opción 3: Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
```

## Configuración Técnica

### Variables de Entorno

| Variable | Requerido | Descripción |
|----------|-----------|-------------|
| `JWT_SECRET_KEY` | ✅ Sí | Secret activo para firmar nuevos tokens |
| `JWT_SECRET_KEY_OLD` | ❌ No | Secret(s) antiguos para validar tokens existentes |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ No | Tiempo de expiración de tokens (default: 30 min) |

### Comportamiento

1. **Creación de tokens**: Siempre usa `JWT_SECRET_KEY` (el primero)
2. **Validación de tokens**: Intenta en orden:
   - Primero: `JWT_SECRET_KEY`
   - Si falla: `JWT_SECRET_KEY_OLD`
   - Si falla: Token inválido (401)

### Archivos Modificados

- `webapp/backend/app/config.py:23-33` - Configuración de secrets múltiples
- `webapp/backend/app/auth/utils.py:83-134` - Lógica de validación con rotación
- `webapp/backend/app/auth/dependencies.py:69-74` - Uso de lista de secrets

## Ejemplo de Rotación Completa

### Día 1: Rotar Secret
```bash
# .env
JWT_SECRET_KEY=nuevo_secret_12345
JWT_SECRET_KEY_OLD=viejo_secret_67890
```

### Día 2-30: Monitorear
```bash
# Ver cuántos usuarios usan el secret antiguo
docker-compose logs backend | grep "old secret key" | wc -l
```

### Día 31: Limpiar
```bash
# .env
JWT_SECRET_KEY=nuevo_secret_12345
# JWT_SECRET_KEY_OLD removido
```

## Ventajas

✅ **Sin interrupción del servicio**: Usuarios siguen autenticados durante la rotación
✅ **Seguridad mejorada**: Puedes rotar secrets regularmente sin impacto
✅ **Monitoreable**: Logs te permiten saber cuándo completar la rotación
✅ **Flexible**: Soporta rotación gradual o inmediata según necesites

## Notas de Seguridad

⚠️ **NUNCA** commitees `.env` al repositorio
⚠️ Rota secrets regularmente (ej: cada 90 días)
⚠️ Si sospechas que un secret fue comprometido, rota inmediatamente y **NO** uses `JWT_SECRET_KEY_OLD` (fuerza re-login)
