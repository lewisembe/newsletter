# Remember Me Feature

## Descripción

La funcionalidad "Recordarme" permite a los usuarios mantener su sesión activa por períodos extendidos (30 días) sin necesidad de volver a iniciar sesión cada vez que visitan la aplicación.

## Cómo Funciona

### Backend

El sistema utiliza JWT tokens con diferentes tiempos de expiración:

- **Login normal** (`remember_me: false`): Token válido por 30 minutos
- **Remember Me** (`remember_me: true`): Token válido por 30 días

La cookie HTTP-only se configura con el `max_age` correspondiente, lo que hace que el navegador la mantenga persistente incluso después de cerrar.

### Implementación

#### 1. Backend (Ya implementado ✅)

**Endpoint**: `POST /api/v1/auth/login`

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "password123",
  "remember_me": true  // ← Campo opcional (default: false)
}
```

**Comportamiento**:
- Si `remember_me: true`:
  - JWT expira en 30 días
  - Cookie `max_age = 2592000` segundos (30 días)
  - Cookie persiste después de cerrar navegador

- Si `remember_me: false` o no especificado:
  - JWT expira en 30 minutos
  - Cookie `max_age = 1800` segundos (30 minutos)
  - Cookie se borra al cerrar navegador

#### 2. Frontend (Pendiente de implementación)

**Login Form** (`webapp/frontend/app/(auth)/login/page.tsx`):

```tsx
import { useState } from 'react';

function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const response = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',  // ← Important: include cookies
      body: JSON.stringify({
        email,
        password,
        remember_me: rememberMe  // ← Send remember_me flag
      })
    });

    if (response.ok) {
      // Redirect to dashboard
      window.location.href = '/dashboard';
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
        required
      />

      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Contraseña"
        required
      />

      {/* Remember Me Checkbox */}
      <label className="flex items-center gap-2 mt-4">
        <input
          type="checkbox"
          checked={rememberMe}
          onChange={(e) => setRememberMe(e.target.checked)}
          className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
        />
        <span className="text-sm text-gray-700">
          Recordarme por 30 días
        </span>
      </label>

      <button type="submit">Iniciar Sesión</button>
    </form>
  );
}
```

## Configuración

### Variables de Entorno

Edita `.env` para ajustar los tiempos de expiración:

```bash
# Session durations
ACCESS_TOKEN_EXPIRE_MINUTES=30  # Normal login (30 minutes)
REMEMBER_ME_EXPIRE_DAYS=30      # Remember Me (30 days)
```

**Valores recomendados**:
- `ACCESS_TOKEN_EXPIRE_MINUTES`: 15-60 minutos (balance entre seguridad y UX)
- `REMEMBER_ME_EXPIRE_DAYS`: 7-90 días (común: 7, 14, 30, 90)

### Aplicar Cambios

```bash
# 1. Editar .env con nuevos valores
# 2. Restart backend
docker-compose restart backend

# 3. Verificar que funciona
venv/bin/python scripts/test_remember_me.py
```

## Testing

### Test Automatizado

```bash
venv/bin/python scripts/test_remember_me.py
```

Verifica:
- ✓ Tokens normales expiran en 30 minutos
- ✓ Tokens "Remember Me" expiran en 30 días
- ✓ Ambos tipos validan correctamente
- ✓ Cálculo de `max_age` correcto

### Test Manual (API)

**Login normal**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "remember_me": false
  }' \
  -c cookies.txt -v
```

**Login con Remember Me**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "remember_me": true
  }' \
  -c cookies.txt -v
```

Inspecciona las cookies en `cookies.txt` y verifica el `Max-Age`.

### Test Manual (Browser DevTools)

1. Abre DevTools → Application → Cookies
2. Login con "Remember Me" activado
3. Busca la cookie `token`
4. Verifica:
   - `Expires/Max-Age`: ~30 días desde ahora
   - `HttpOnly`: ✓ (seguridad)
   - `SameSite`: Lax
   - `Secure`: ✓ (solo en HTTPS/producción)

## Seguridad

### ✅ Implementado

- **HTTP-only cookies**: Tokens no accesibles via JavaScript (previene XSS)
- **SameSite=Lax**: Protección contra CSRF
- **Expiración en token**: JWT tiene `exp` claim que no puede ser modificado
- **Validación server-side**: Tokens expirados son rechazados

### ⚠️ Consideraciones

1. **Remember Me = Mayor riesgo de robo de sesión**
   - Si un atacante roba la cookie, tiene 30 días de acceso
   - Mitigation: educar usuarios sobre no activar en computadoras públicas

2. **Revocación de tokens**
   - JWT es stateless, no se puede invalidar sin cambiar secret
   - Para revocación inmediata, considera implementar blacklist en Redis

3. **HTTPS obligatorio en producción**
   - Cambiar `secure=False` a `secure=True` en `auth.py:199`
   - Solo transmitir cookies sobre conexiones cifradas

### Mejoras Futuras (Opcional)

1. **Token Refresh**:
   - Refresh token de larga duración
   - Access token de corta duración (renovado automáticamente)

2. **Token Blacklist** (Redis):
   - Permitir logout/revocación inmediata
   - Almacenar tokens invalidados hasta su expiración

3. **Session Management**:
   - Mostrar sesiones activas al usuario
   - Permitir cerrar sesiones remotas

4. **Device Fingerprinting**:
   - Detectar cambios de dispositivo/IP
   - Solicitar re-autenticación si sospechoso

## Logs y Monitoreo

El backend registra eventos relevantes:

```bash
# Ver logins con "Remember Me"
docker-compose logs backend | grep "Remember Me"

# Output esperado:
# INFO: User logged in with 'Remember Me': user@example.com (expires in 30 days)
```

```bash
# Ver todos los logins
docker-compose logs backend | grep "logged in"

# Output normal:
# INFO: User logged in: user@example.com (expires in 30 minutes)
```

## Troubleshooting

### Cookie no persiste después de cerrar navegador

**Causa**: Navegador configurado para borrar cookies al cerrar.

**Solución**:
- Verifica configuración del navegador (Privacy Settings)
- Asegúrate de que `max_age` está configurado (no solo `expires`)

### Token expira aunque se usó Remember Me

**Causa**:
1. Usuario hizo login sin marcar checkbox
2. Configuración incorrecta en `.env`
3. Backend no recibió `remember_me: true`

**Debug**:
```bash
# Ver logs del backend al hacer login
docker-compose logs -f backend

# Debe mostrar:
# INFO: User logged in with 'Remember Me': ...
```

### Cookie desaparece en producción (HTTPS)

**Causa**: `secure=False` en producción con HTTPS.

**Solución**: Cambiar en `webapp/backend/app/api/v1/auth.py:199`:
```python
secure=True,  # ← Cambiar a True en producción
```

## Archivos Modificados

- `webapp/backend/app/config.py:26` - Añadido `REMEMBER_ME_EXPIRE_DAYS`
- `webapp/backend/app/schemas/auth.py:32` - Campo `remember_me` en `UserLogin`
- `webapp/backend/app/api/v1/auth.py:173-204` - Lógica de expiración dinámica
- `.env:9-10` - Variables de configuración
- `scripts/test_remember_me.py` - Test suite

## Recursos

- [MDN: Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
