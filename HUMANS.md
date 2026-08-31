# Reachy Duck: comandos para humanos

Estos comandos se ejecutan en el portátil, desde cualquier terminal con acceso a la red del robot. Cambia
`reachy-mini.local` por la IP del robot si mDNS no funciona.

## Start Reachy Duck

```bash
ROBOT_HOST=reachy-mini.local

# Detiene la app actual, si la hubiera.
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/stop-current-app" || true

# Inicia Reachy Duck.
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/start-app/reachy_duck"

# Comprueba el estado.
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

Espera a que Reachy salude. Si quieres ver los logs mientras arranca, abre otra terminal:

```bash
ssh "pollen@${ROBOT_HOST}" "sudo journalctl -u reachy-mini-daemon -f"
```

## Apagar Reachy Duck

Esto detiene solamente la aplicación Reachy Duck; no apaga físicamente el robot ni su daemon:

```bash
ROBOT_HOST=reachy-mini.local
curl --fail --silent --show-error -X POST "http://${ROBOT_HOST}:8000/api/apps/stop-current-app"
```

Para comprobar que se detuvo:

```bash
curl --fail --silent --show-error "http://${ROBOT_HOST}:8000/api/apps/current-app-status"
```

## Apagar Reachy Mini Wireless completamente

Primero detén Reachy Duck:

```bash
ROBOT_HOST=reachy-mini.local

curl --fail --silent --show-error -X POST \
  "http://${ROBOT_HOST}:8000/api/apps/stop-current-app"
```

Después apaga Linux de forma segura:

```bash
ssh "pollen@${ROBOT_HOST}" "sudo poweroff"
```

También puedes usar:

```bash
ssh "pollen@${ROBOT_HOST}" "sudo shutdown -h now"
```

Después de esto, espera a que el robot termine de apagarse antes de desconectar alimentación.

No conviene cortar la corriente directamente mientras Linux está funcionando.
