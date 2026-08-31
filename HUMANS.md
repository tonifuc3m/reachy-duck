# Reachy Duck: comandos para humanos

```text
[1. Encender Reachy]
        ↓
[2. Despertar e iniciar Duck]
        ↓
[3. Usar Reachy Duck]
        ↓
[4. Dormir / detener Duck]
        ↓
[5. Apagar Reachy completamente]
```

Uso normal: no necesitas una terminal. La configuración y depuración detalladas están en el
[README](README.md#daily-use-wake-and-sleep).

## 1. Encender Reachy

Pulsa el **botón físico de encendido** de Reachy Mini Wireless y espera a que arranque. Reachy se queda dormido; Duck
no empieza a conversar todavía.

Cuando el daemon responda y no haya una app activa, continúa con **[2. Despertar e iniciar Duck](#2-despertar-e-iniciar-duck)**.

## 2. Despertar e iniciar Duck

Toca/empuja suavemente **una de las dos antenas** y déjala volver a su posición. Reachy despierta e inicia Duck. No
hace falta mantenerla pulsada.

Antes del primer uso debes configurar `reachy_duck` como startup app; sigue
[la configuración del README](README.md#configure-the-wireless-startup-app).
Una vez iniciado, estás en **[3. Usar Reachy Duck](#3-usar-reachy-duck)**.

## 3. Usar Reachy Duck

Habla normalmente con Reachy. Cuando termines, continúa con **[4. Dormir / detener Duck](#4-dormir--detener-duck)**.

## 4. Dormir / detener Duck

Di `Good night`, `Reachy, go to sleep`, `You can sleep now` o `Stop for now`. Reachy duerme y Duck se detiene; Linux y
el daemon siguen funcionando. Más tarde vuelve a **[2. Despertar e iniciar Duck](#2-despertar-e-iniciar-duck)** tocando una antena.

Si el gesto de antena falla, consulta la [depuración manual del README](README.md#manual-app-control-for-debugging).

## 5. Apagar Reachy completamente

Sólo cuando quieras apagarlo de verdad, apaga Linux de forma segura:

```bash
ROBOT_HOST=reachy-mini.local
ssh "pollen@${ROBOT_HOST}" "sudo poweroff"
```

Espera a que Reachy termine de apagarse. Para volver a usarlo, empieza por **[1. Encender Reachy](#1-encender-reachy)**.
No cortes directamente la alimentación mientras Linux está funcionando.
