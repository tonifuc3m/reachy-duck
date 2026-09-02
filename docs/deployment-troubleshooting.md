# Si falla el despliegue normal

Si `reachy-mini.local` o una petición HTTP desde el portátil no responde, no inicies otro daemon.

1. En Reachy Mini Control, usa la IP que muestra **Reachy WiFi** en lugar del nombre mDNS.
2. Comprueba SSH y el daemon:

   ```bash
   ssh -o BatchMode=yes pollen@<IP_DE_REACHY> 'hostname; systemctl is-active reachy-mini-daemon.service'
   ```

3. Si SSH funciona pero HTTP desde el portátil se queda esperando, consulta el daemon desde el robot:

   ```bash
   ssh pollen@<IP_DE_REACHY> 'curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/api/daemon/status'
   ```

4. Sincroniza e instala como en el procedimiento normal. Después inicia la app mediante el daemon local:

   ```bash
   ssh pollen@<IP_DE_REACHY> \
     'curl --fail --silent --show-error --max-time 15 -X POST http://127.0.0.1:8000/api/apps/start-app/reachy_duck'
   ssh pollen@<IP_DE_REACHY> \
     'curl --fail --silent --show-error --max-time 15 http://127.0.0.1:8000/api/apps/current-app-status'
   ```

El estado esperado es `"state":"running"`. Para investigar un fallo de inicio, revisa las últimas líneas del journal:

```bash
ssh pollen@<IP_DE_REACHY> 'sudo journalctl -u reachy-mini-daemon.service -n 100 --no-pager'
```
