"""
windows_commands.py — Módulo de Inteligencia de Sistema Operativo para DARIUS AI
==================================================================================
Resuelve comandos del sistema Windows que NO son aplicaciones instaladas.

Dos tipos de entradas en el diccionario:

  Tipo A — "abrir panel/ventana":
    cmd   : URI (ms-settings:), ejecutable (.exe), snap-in (.msc), applet (.cpl),
            carpeta especial (shell:), o comando de shell.
    Uso   : wincmd_launch("configuraciones de red")  → abre la ventana

  Tipo B — "ejecutar acción/subproceso":
    action: diccionario con:
              type  → "powershell" | "cmd" | "startfile" | "runas"
              run   → comando exacto a ejecutar
              args  → lista de argumentos (alternativa a run)
    Uso   : wincmd_action("vaciar papelera")  → ejecuta el subproceso y retorna
            un string con el resultado o None si no hay match

Estrategia de resolución (en orden de prioridad):
  1. Coincidencia exacta normalizada
  2. Fuzzy matching (SequenceMatcher) sobre toda la tabla plana de aliases
  3. Búsqueda por subconjunto de palabras clave
  4. Fallback al escáner de apps instaladas de DARIUS (gestionado en main.py)
"""

import os
import re
import subprocess
import logging
import ctypes
from difflib import SequenceMatcher
from typing import Optional

log = logging.getLogger("DARIUS.WinCMD")


# ═════════════════════════════════════════════════════════════════════════════
#  TIPO A — ABRIR VENTANAS / PANELES
# ═════════════════════════════════════════════════════════════════════════════

WINDOWS_COMMANDS: dict[str, dict] = {

    # ── CONFIGURACIÓN DE RED ──────────────────────────────────────────────────
    "configuracion de red": {
        "cmd": "ms-settings:network",
        "aliases": [
            "configuraciones de red", "ajustes de red", "red e internet",
            "configurar red", "opciones de red", "conexiones de red",
            "configuracion de internet", "ajustes de internet",
            "internet y red", "red wifi", "configuracion wifi"
        ],
        "desc": "Configuración de Red e Internet"
    },
    "wifi": {
        "cmd": "ms-settings:network-wifi",
        "aliases": ["configuracion wifi", "ajustes wifi", "redes wifi", "conectar wifi"],
        "desc": "Configuración WiFi"
    },
    "vpn": {
        "cmd": "ms-settings:network-vpn",
        "aliases": ["configurar vpn", "ajustes vpn"],
        "desc": "Configuración VPN"
    },
    "ethernet": {
        "cmd": "ms-settings:network-ethernet",
        "aliases": ["conexion ethernet", "cable de red", "red cableada"],
        "desc": "Configuración Ethernet"
    },
    "proxy": {
        "cmd": "ms-settings:network-proxy",
        "aliases": ["configuracion proxy", "ajustes proxy"],
        "desc": "Configuración de Proxy"
    },
    "estado de red": {
        "cmd": "ms-settings:network-status",
        "aliases": ["estado de conexion", "ver estado de red", "diagnostico de red"],
        "desc": "Estado de la red"
    },
    "adaptadores de red": {
        "cmd": "ncpa.cpl",
        "aliases": [
            "ver adaptadores", "conexiones de red clasico",
            "propiedades de red", "adaptador de red"
        ],
        "desc": "Conexiones de red (adaptadores)"
    },

    # ── APLICACIONES ──────────────────────────────────────────────────────────
    "aplicaciones y caracteristicas": {
        "cmd": "ms-settings:appsfeatures",
        "aliases": [
            "aplicaciones y características", "apps y caracteristicas",
            "apps instaladas", "programas instalados", "desinstalar programas",
            "administrar aplicaciones", "gestionar apps", "ver aplicaciones",
            "aplicaciones del sistema", "lista de aplicaciones",
            "aplicaciones y caracteristicas de windows"
        ],
        "desc": "Aplicaciones y características"
    },
    "aplicaciones predeterminadas": {
        "cmd": "ms-settings:defaultapps",
        "aliases": ["apps predeterminadas", "programas predeterminados", "aplicaciones por defecto"],
        "desc": "Aplicaciones predeterminadas"
    },
    "inicio automatico": {
        "cmd": "ms-settings:startupapps",
        "aliases": ["aplicaciones de inicio", "apps al iniciar", "programas de inicio", "inicio de windows"],
        "desc": "Aplicaciones de inicio"
    },
    "caracteristicas opcionales": {
        "cmd": "ms-settings:optionalfeatures",
        "aliases": ["funciones opcionales", "características de windows", "agregar características"],
        "desc": "Características opcionales de Windows"
    },
    "programas y caracteristicas clasico": {
        "cmd": "appwiz.cpl",
        "aliases": [
            "desinstalar programas clasico", "agregar o quitar programas",
            "programas instalados clasico", "appwiz"
        ],
        "desc": "Programas y características (Panel de Control)"
    },

    # ── SISTEMA ───────────────────────────────────────────────────────────────
    "configuracion": {
        "cmd": "ms-settings:",
        "aliases": ["ajustes", "settings", "opciones del sistema", "panel de ajustes"],
        "desc": "Configuración de Windows"
    },
    "pantalla": {
        "cmd": "ms-settings:display",
        "aliases": [
            "configuracion de pantalla", "ajustes de pantalla",
            "resolucion de pantalla", "brillo", "configurar monitor"
        ],
        "desc": "Configuración de pantalla"
    },
    "sonido": {
        "cmd": "ms-settings:sound",
        "aliases": [
            "configuracion de sonido", "ajustes de audio", "volumen del sistema",
            "dispositivos de audio", "salida de audio", "entrada de audio"
        ],
        "desc": "Configuración de sonido"
    },
    "notificaciones": {
        "cmd": "ms-settings:notifications",
        "aliases": [
            "configuracion de notificaciones", "ajustes de notificaciones",
            "alertas del sistema", "centro de notificaciones"
        ],
        "desc": "Notificaciones y acciones"
    },
    "energia": {
        "cmd": "ms-settings:powersleep",
        "aliases": [
            "configuracion de energia", "plan de energia", "ahorro de bateria",
            "suspender", "hibernar", "opciones de energia"
        ],
        "desc": "Energía y suspensión"
    },
    "almacenamiento": {
        "cmd": "ms-settings:storagesense",
        "aliases": [
            "configuracion de almacenamiento", "espacio en disco",
            "sensor de almacenamiento", "liberar espacio", "storage sense"
        ],
        "desc": "Almacenamiento"
    },
    "informacion del sistema": {
        "cmd": "ms-settings:about",
        "aliases": [
            "acerca de este pc", "acerca del equipo", "informacion del equipo",
            "version de windows", "especificaciones del sistema", "sobre este pc"
        ],
        "desc": "Acerca de este equipo"
    },
    "multitarea": {
        "cmd": "ms-settings:multitasking",
        "aliases": ["configuracion de multitarea", "escritorios virtuales", "snap"],
        "desc": "Multitarea"
    },

    # ── PERSONALIZACIÓN ───────────────────────────────────────────────────────
    "personalizacion": {
        "cmd": "ms-settings:personalization",
        "aliases": [
            "personalizar windows", "temas de windows", "aspecto del sistema",
            "fondo de pantalla", "colores del sistema"
        ],
        "desc": "Personalización"
    },
    "fondo de pantalla": {
        "cmd": "ms-settings:personalization-background",
        "aliases": ["cambiar fondo", "wallpaper", "imagen de fondo"],
        "desc": "Fondo de pantalla"
    },
    "colores": {
        "cmd": "ms-settings:colors",
        "aliases": ["colores de windows", "color de acento", "modo oscuro", "tema oscuro", "dark mode"],
        "desc": "Colores y modo oscuro"
    },
    "temas": {
        "cmd": "ms-settings:themes",
        "aliases": ["temas de windows", "cambiar tema"],
        "desc": "Temas"
    },
    "pantalla de bloqueo": {
        "cmd": "ms-settings:lockscreen",
        "aliases": ["configurar pantalla de bloqueo", "lock screen"],
        "desc": "Pantalla de bloqueo"
    },
    "barra de tareas": {
        "cmd": "ms-settings:taskbar",
        "aliases": ["configurar barra de tareas", "taskbar"],
        "desc": "Barra de tareas"
    },

    # ── CUENTAS ───────────────────────────────────────────────────────────────
    "cuentas": {
        "cmd": "ms-settings:accounts",
        "aliases": ["configuracion de cuentas", "mi cuenta", "cuenta de usuario"],
        "desc": "Cuentas"
    },
    "opciones de inicio de sesion": {
        "cmd": "ms-settings:signinoptions",
        "aliases": [
            "contraseña de windows", "pin de windows", "hello windows",
            "huella dactilar", "inicio de sesion", "cambiar contraseña"
        ],
        "desc": "Opciones de inicio de sesión"
    },
    "otros usuarios": {
        "cmd": "ms-settings:otherusers",
        "aliases": ["usuarios del sistema", "agregar usuario", "cuentas de usuario", "administrar usuarios"],
        "desc": "Otros usuarios"
    },

    # ── HORA Y REGIÓN ─────────────────────────────────────────────────────────
    "fecha y hora": {
        "cmd": "ms-settings:dateandtime",
        "aliases": ["configurar fecha", "configurar hora", "zona horaria", "ajustar reloj"],
        "desc": "Fecha y hora"
    },
    "idioma y region": {
        "cmd": "ms-settings:regionlanguage",
        "aliases": ["configurar idioma", "cambiar idioma", "region", "idioma del sistema"],
        "desc": "Idioma y región"
    },

    # ── DISPOSITIVOS ──────────────────────────────────────────────────────────
    "bluetooth": {
        "cmd": "ms-settings:bluetooth",
        "aliases": [
            "configuracion bluetooth", "activar bluetooth",
            "dispositivos bluetooth", "emparejar bluetooth"
        ],
        "desc": "Bluetooth y otros dispositivos"
    },
    "impresoras": {
        "cmd": "ms-settings:printers",
        "aliases": ["agregar impresora", "configurar impresora", "impresoras y escáneres"],
        "desc": "Impresoras y escáneres"
    },
    "mouse": {
        "cmd": "ms-settings:mousetouchpad",
        "aliases": ["configurar mouse", "ajustes del raton", "touchpad", "panel táctil"],
        "desc": "Mouse y panel táctil"
    },
    "teclado": {
        "cmd": "ms-settings:typing",
        "aliases": ["configurar teclado", "ajustes del teclado"],
        "desc": "Escritura y teclado"
    },

    # ── PRIVACIDAD Y SEGURIDAD ────────────────────────────────────────────────
    "privacidad": {
        "cmd": "ms-settings:privacy",
        "aliases": [
            "configuracion de privacidad", "permisos de aplicaciones", "privacidad de windows"
        ],
        "desc": "Privacidad y seguridad"
    },
    "seguridad de windows": {
        "cmd": "windowsdefender:",
        "aliases": ["windows defender", "antivirus", "proteccion contra virus", "defender"],
        "desc": "Seguridad de Windows / Defender"
    },
    "actualizaciones": {
        "cmd": "ms-settings:windowsupdate",
        "aliases": [
            "windows update", "actualizar windows", "buscar actualizaciones",
            "actualizaciones de windows", "instalar actualizaciones"
        ],
        "desc": "Windows Update"
    },

    # ── HERRAMIENTAS CLÁSICAS ─────────────────────────────────────────────────
    "panel de control": {
        "cmd": "control",
        "aliases": ["control panel", "panel del sistema"],
        "desc": "Panel de Control"
    },
    "administrador de dispositivos": {
        "cmd": "devmgmt.msc",
        "aliases": [
            "device manager", "gestor de dispositivos",
            "controladores", "drivers", "hardware del sistema"
        ],
        "desc": "Administrador de dispositivos"
    },
    "administrador de discos": {
        "cmd": "diskmgmt.msc",
        "aliases": ["disk management", "gestionar discos", "particiones"],
        "desc": "Administración de discos"
    },
    "servicios": {
        "cmd": "services.msc",
        "aliases": ["servicios de windows", "gestionar servicios"],
        "desc": "Servicios de Windows"
    },
    "editor del registro": {
        "cmd": "regedit",
        "aliases": ["regedit", "registro de windows", "registro del sistema"],
        "desc": "Editor del Registro"
    },
    "configuracion del sistema": {
        "cmd": "msconfig",
        "aliases": [
            "msconfig", "ms config", "ms confi", "ms confi",
            "configuracion de arranque", "inicio del sistema"
        ],
        "desc": "Configuración del sistema (msconfig)"
    },
    "informacion del sistema detallada": {
        "cmd": "msinfo32",
        "aliases": ["msinfo", "informacion detallada del sistema"],
        "desc": "Información del sistema"
    },
    "administrador de tareas": {
        "cmd": "taskmgr",
        "aliases": ["task manager", "procesos del sistema", "ver procesos", "uso de cpu"],
        "desc": "Administrador de tareas"
    },
    "monitor de rendimiento": {
        "cmd": "perfmon",
        "aliases": ["rendimiento del sistema", "performance monitor"],
        "desc": "Monitor de rendimiento"
    },
    "monitor de recursos": {
        "cmd": "resmon",
        "aliases": ["resource monitor", "uso de recursos"],
        "desc": "Monitor de recursos"
    },
    "visor de eventos": {
        "cmd": "eventvwr",
        "aliases": ["event viewer", "registro de eventos", "logs del sistema"],
        "desc": "Visor de eventos"
    },
    "programador de tareas": {
        "cmd": "taskschd.msc",
        "aliases": ["task scheduler", "tareas programadas"],
        "desc": "Programador de tareas"
    },
    "limpieza de disco": {
        "cmd": "cleanmgr",
        "aliases": ["limpiar disco", "disk cleanup", "liberar espacio en disco"],
        "desc": "Liberador de espacio en disco"
    },
    "desfragmentar": {
        "cmd": "dfrgui",
        "aliases": ["desfragmentar disco", "optimizar unidades", "optimizar disco"],
        "desc": "Desfragmentación y optimización"
    },
    "simbolo del sistema": {
        "cmd": "cmd",
        "aliases": ["cmd", "consola", "terminal de windows", "linea de comandos"],
        "desc": "Símbolo del sistema"
    },
    "powershell": {
        "cmd": "powershell",
        "aliases": ["power shell", "terminal powershell", "consola powershell"],
        "desc": "Windows PowerShell"
    },
    "terminal de windows": {
        "cmd": "wt",
        "aliases": ["windows terminal", "terminal moderna"],
        "desc": "Terminal de Windows"
    },

    # ── CARPETAS ESPECIALES ───────────────────────────────────────────────────
    "explorador de archivos": {
        "cmd": "explorer",
        "aliases": ["explorador", "mis archivos", "explorador de windows", "file explorer"],
        "desc": "Explorador de archivos"
    },
    "descargas": {
        "cmd": "shell:Downloads",
        "aliases": ["carpeta descargas", "mis descargas", "downloads"],
        "desc": "Carpeta Descargas"
    },
    "documentos": {
        "cmd": "shell:Personal",
        "aliases": ["mis documentos", "carpeta documentos"],
        "desc": "Documentos"
    },
    "escritorio": {
        "cmd": "shell:Desktop",
        "aliases": ["abrir escritorio", "mostrar escritorio"],
        "desc": "Escritorio"
    },
    "papelera": {
        "cmd": "shell:RecycleBinFolder",
        "aliases": ["papelera de reciclaje", "recycle bin", "archivos eliminados"],
        "desc": "Papelera de reciclaje"
    },

    # ── NAVEGADORES ───────────────────────────────────────────────────────────
    "brave": {
        "cmd": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "fallback_cmd": "start brave",
        "aliases": ["brave browser", "navegador brave", "brave software", "abrir brave"],
        "desc": "Brave Browser"
    },
    "chrome": {
        "cmd": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "fallback_cmd": "start chrome",
        "aliases": ["google chrome", "navegador chrome"],
        "desc": "Google Chrome"
    },
    "firefox": {
        "cmd": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "fallback_cmd": "start firefox",
        "aliases": ["mozilla firefox", "navegador firefox", "mozilla"],
        "desc": "Mozilla Firefox"
    },
    "edge": {
        "cmd": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "fallback_cmd": "start msedge",
        "aliases": ["microsoft edge", "navegador edge"],
        "desc": "Microsoft Edge"
    },

    # ── APPS MICROSOFT ────────────────────────────────────────────────────────
    "tienda": {
        "cmd": "ms-windows-store:",
        "aliases": ["microsoft store", "tienda de windows", "store"],
        "desc": "Microsoft Store"
    },
    "calculadora": {
        "cmd": "calc",
        "aliases": ["calculator", "abrir calculadora"],
        "desc": "Calculadora"
    },
    "bloc de notas": {
        "cmd": "notepad",
        "aliases": ["notepad", "editor de texto simple", "notas"],
        "desc": "Bloc de notas"
    },
    "paint": {
        "cmd": "mspaint",
        "aliases": ["microsoft paint", "ms paint"],
        "desc": "Paint"
    },
    "recortes": {
        "cmd": "snippingtool",
        "aliases": ["herramienta de recortes", "snipping tool", "captura de pantalla"],
        "desc": "Herramienta Recortes"
    },
    "lupa": {
        "cmd": "magnify",
        "aliases": ["magnificador", "zoom de pantalla"],
        "desc": "Lupa"
    },
    "teclado en pantalla": {
        "cmd": "osk",
        "aliases": ["teclado virtual", "teclado tactil", "on screen keyboard"],
        "desc": "Teclado en pantalla"
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  TIPO B — SUBPROCESOS / ACCIONES DEL SISTEMA
#
#  Cada entrada tiene:
#    action.type  → "powershell" | "cmd" | "startfile"
#    action.run   → comando completo como string
#    action.desc  → descripción amigable para TTS
#    action.confirm → True si DARIUS debe pedir confirmación antes de ejecutar
# ═════════════════════════════════════════════════════════════════════════════

SYSTEM_ACTIONS: dict[str, dict] = {

    # ── RED ───────────────────────────────────────────────────────────────────
    "diagnosticar red": {
        "action": {"type": "cmd", "run": "msdt.exe /id NetworkDiagnosticsNetworkAdapter"},
        "aliases": [
            "reparar red", "solucionar problemas de red", "arreglar internet",
            "diagnostico de conexion", "reparar conexion", "internet no funciona"
        ],
        "desc": "Diagnóstico automático de red"
    },
    "ver ip": {
        "action": {"type": "powershell",
                   "run": "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress"},
        "aliases": ["cual es mi ip", "mi direccion ip", "ver direccion ip", "ip local", "ipconfig"],
        "desc": "Consultar IP local",
        "return_output": True
    },
    "ver ip publica": {
        "action": {"type": "powershell",
                   "run": "(Invoke-WebRequest -Uri 'https://api.ipify.org' -UseBasicParsing).Content"},
        "aliases": ["ip publica", "mi ip externa", "cual es mi ip publica", "ip de internet"],
        "desc": "Consultar IP pública",
        "return_output": True
    },
    "ver dns": {
        "action": {"type": "powershell",
                   "run": "Get-DnsClientServerAddress -AddressFamily IPv4 | Where-Object {$_.ServerAddresses} | Select-Object InterfaceAlias, ServerAddresses | Format-Table -AutoSize | Out-String"},
        "aliases": ["que dns tengo", "ver servidores dns", "mis dns", "dns actual"],
        "desc": "Ver servidores DNS configurados",
        "return_output": True
    },
    "limpiar cache dns": {
        "action": {"type": "cmd", "run": "ipconfig /flushdns"},
        "aliases": ["flush dns", "borrar cache dns", "vaciar dns", "limpiar dns", "resetear dns"],
        "desc": "Limpiar caché DNS"
    },
    "renovar ip": {
        "action": {"type": "cmd", "run": "ipconfig /release && ipconfig /renew"},
        "aliases": ["renovar direccion ip", "refrescar ip", "obtener nueva ip", "ip dhcp"],
        "desc": "Renovar dirección IP (DHCP)"
    },
    "ver conexiones activas": {
        "action": {"type": "cmd", "run": "netstat -ano"},
        "aliases": ["conexiones de red activas", "puertos abiertos", "netstat", "ver puertos"],
        "desc": "Ver conexiones de red activas",
        "return_output": True,
        "open_window": True
    },
    "ping google": {
        "action": {"type": "cmd", "run": "ping google.com -n 4"},
        "aliases": ["hacer ping", "probar internet", "test de conexion", "hay internet", "verificar internet"],
        "desc": "Ping a Google (prueba de conexión)",
        "return_output": True,
        "open_window": True
    },
    "resetear red": {
        "action": {"type": "cmd",
                   "run": "netsh winsock reset && netsh int ip reset && ipconfig /flushdns"},
        "aliases": ["resetear conexion", "reiniciar configuracion de red", "restablecer red",
                    "red no funciona", "reparar tcp ip"],
        "desc": "Restablecer configuración de red (Winsock + TCP/IP + DNS)",
        "confirm": True
    },
    "ver redes wifi": {
        "action": {"type": "cmd", "run": "netsh wlan show networks"},
        "aliases": ["redes disponibles", "ver redes disponibles", "que redes hay", "scan wifi"],
        "desc": "Ver redes WiFi disponibles",
        "return_output": True,
        "open_window": True
    },
    "desconectar wifi": {
        "action": {"type": "cmd", "run": "netsh wlan disconnect"},
        "aliases": ["desconectar de la red", "cortar wifi", "desactivar wifi"],
        "desc": "Desconectar del WiFi",
        "confirm": True
    },

    # ── SISTEMA ───────────────────────────────────────────────────────────────
    "vaciar papelera": {
        "action": {"type": "powershell",
                   "run": "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"},
        "aliases": ["limpiar papelera", "borrar papelera", "vaciar reciclaje"],
        "desc": "Vaciar la papelera de reciclaje",
        "confirm": True
    },
    "ver espacio en disco": {
        "action": {"type": "powershell",
                   "run": "Get-PSDrive -PSProvider FileSystem | Select-Object Name, @{N='Usado(GB)';E={[math]::Round(($_.Used/1GB),1)}}, @{N='Libre(GB)';E={[math]::Round(($_.Free/1GB),1)}}, @{N='Total(GB)';E={[math]::Round((($_.Used+$_.Free)/1GB),1)}} | Format-Table -AutoSize | Out-String"},
        "aliases": [
            "espacio disponible", "cuanto espacio tengo", "espacio libre",
            "ver disco", "estado del disco", "capacidad del disco"
        ],
        "desc": "Ver espacio en disco",
        "return_output": True
    },
    "ver uso de ram": {
        "action": {"type": "powershell",
                   "run": "$os=Get-CimInstance Win32_OperatingSystem; $total=[math]::Round($os.TotalVisibleMemorySize/1MB,1); $libre=[math]::Round($os.FreePhysicalMemory/1MB,1); $usado=[math]::Round($total-$libre,1); \"RAM total: ${total} GB | Usada: ${usado} GB | Libre: ${libre} GB\""},
        "aliases": ["uso de memoria", "cuanta ram tengo", "memoria ram", "ram disponible", "uso de memoria ram"],
        "desc": "Ver uso de memoria RAM",
        "return_output": True
    },
    "ver uso de cpu": {
        "action": {"type": "powershell",
                   "run": "$cpu = (Get-CimInstance Win32_Processor).LoadPercentage; \"Uso de CPU: ${cpu}%\""},
        "aliases": ["uso del procesador", "carga del cpu", "cuanto cpu se usa", "rendimiento cpu"],
        "desc": "Ver uso de CPU",
        "return_output": True
    },
    "ver procesos": {
        "action": {"type": "powershell",
                   "run": "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, @{N='RAM(MB)';E={[math]::Round($_.WorkingSet/1MB,0)}} | Format-Table -AutoSize | Out-String"},
        "aliases": ["top procesos", "procesos que consumen mas", "que esta usando el cpu"],
        "desc": "Top 10 procesos por consumo de CPU",
        "return_output": True
    },
    "ver temperatura": {
        "action": {"type": "powershell",
                   "run": "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' | Select-Object @{N='Zona';E={$_.InstanceName}}, @{N='Temperatura(C)';E={[math]::Round($_.CurrentTemperature/10 - 273.15, 1)}} | Format-Table | Out-String"},
        "aliases": ["temperatura del procesador", "temperatura cpu", "cuanto calor tiene el pc"],
        "desc": "Ver temperatura del sistema",
        "return_output": True
    },
    "tiempo encendido": {
        "action": {"type": "powershell",
                   "run": "$uptime = (Get-Date) - (gcim Win32_OperatingSystem).LastBootUpTime; \"El equipo lleva encendido: $($uptime.Days) días, $($uptime.Hours) horas y $($uptime.Minutes) minutos\""},
        "aliases": ["cuanto lleva encendido el pc", "tiempo de actividad", "uptime", "desde cuando esta encendido"],
        "desc": "Tiempo de actividad del sistema",
        "return_output": True
    },
    "limpiar archivos temporales": {
        "action": {"type": "powershell",
                   "run": "Remove-Item -Path $env:TEMP\\* -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path 'C:\\Windows\\Temp\\*' -Recurse -Force -ErrorAction SilentlyContinue; 'Archivos temporales eliminados.'"},
        "aliases": ["borrar temporales", "limpiar temp", "eliminar archivos temporales", "limpiar cache del sistema"],
        "desc": "Limpiar archivos temporales",
        "confirm": True
    },
    "ver version de windows": {
        "action": {"type": "powershell",
                   "run": "$v = Get-CimInstance Win32_OperatingSystem; \"$($v.Caption) - Build $($v.BuildNumber) - $($v.OSArchitecture)\""},
        "aliases": ["que version de windows tengo", "windows version", "build de windows", "numero de version"],
        "desc": "Ver versión de Windows",
        "return_output": True
    },
    "ver numero de serie": {
        "action": {"type": "powershell",
                   "run": "(Get-CimInstance Win32_BIOS).SerialNumber"},
        "aliases": ["serial del equipo", "numero serial", "serial number", "serial del pc"],
        "desc": "Ver número de serie del equipo",
        "return_output": True
    },
    "ver modelo del equipo": {
        "action": {"type": "powershell",
                   "run": "$c=Get-CimInstance Win32_ComputerSystem; \"$($c.Manufacturer) $($c.Model)\""},
        "aliases": ["modelo del pc", "que pc tengo", "marca del equipo", "fabricante del equipo"],
        "desc": "Ver modelo del equipo",
        "return_output": True
    },
    "ver procesador": {
        "action": {"type": "powershell",
                   "run": "(Get-CimInstance Win32_Processor).Name"},
        "aliases": ["que procesador tengo", "cpu del equipo", "modelo del procesador"],
        "desc": "Ver información del procesador",
        "return_output": True
    },

    # ── ENERGÍA ───────────────────────────────────────────────────────────────
    "hibernar": {
        "action": {"type": "cmd", "run": "shutdown /h"},
        "aliases": ["poner en hibernacion", "modo hibernacion"],
        "desc": "Hibernar el equipo",
        "confirm": True
    },
    "suspender": {
        "action": {"type": "powershell",
                   "run": "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"},
        "aliases": ["modo suspension", "poner en suspension", "sleep", "dormir el equipo"],
        "desc": "Suspender el equipo",
        "confirm": True
    },
    "bloquear pantalla": {
        "action": {"type": "cmd", "run": "rundll32.exe user32.dll,LockWorkStation"},
        "aliases": ["bloquear pc", "bloquear equipo", "bloquear sesion", "lock screen activar"],
        "desc": "Bloquear la pantalla"
    },
    "cerrar sesion": {
        "action": {"type": "cmd", "run": "shutdown /l"},
        "aliases": ["log off", "salir de la sesion", "cerrar cuenta"],
        "desc": "Cerrar sesión",
        "confirm": True
    },

    # ── PANTALLA ──────────────────────────────────────────────────────────────
    "apagar monitor": {
        "action": {"type": "cmd",
                   "run": r'nircmd.exe monitor off'},
        "aliases": ["apagar pantalla", "apagar monitor", "poner monitor en standby"],
        "desc": "Apagar el monitor"
    },
    "girar pantalla": {
        "action": {"type": "powershell",
                   "run": "Add-Type -AssemblyName System.Windows.Forms; $s=[System.Windows.Forms.Screen]::PrimaryScreen; \"Resolución actual: $($s.Bounds.Width)x$($s.Bounds.Height)\""},
        "aliases": ["rotar pantalla", "cambiar orientacion", "pantalla vertical"],
        "desc": "Información de pantalla / rotación"
    },

    # ── SONIDO ────────────────────────────────────────────────────────────────
    "ver dispositivos de audio": {
        "action": {"type": "powershell",
                   "run": "Get-AudioDevice -List | Format-Table Index, Default, Type, Name -AutoSize | Out-String"},
        "aliases": ["que dispositivos de sonido tengo", "salidas de audio disponibles"],
        "desc": "Ver dispositivos de audio"
    },

    # ── SERVICIOS ─────────────────────────────────────────────────────────────
    "ver servicios activos": {
        "action": {"type": "powershell",
                   "run": "Get-Service | Where-Object {$_.Status -eq 'Running'} | Sort-Object DisplayName | Select-Object DisplayName, Status | Format-Table -AutoSize | Out-String"},
        "aliases": ["servicios corriendo", "servicios en ejecucion", "que servicios corren"],
        "desc": "Ver servicios activos del sistema",
        "return_output": True,
        "open_window": True
    },

    # ── WINDOWS UPDATE ────────────────────────────────────────────────────────
    "buscar actualizaciones ahora": {
        "action": {"type": "powershell",
                   "run": "Start-Process ms-settings:windowsupdate-action"},
        "aliases": ["actualizar ahora", "descargar actualizaciones", "instalar actualizaciones ahora"],
        "desc": "Buscar e instalar actualizaciones ahora"
    },

    # ── FIREWALL ──────────────────────────────────────────────────────────────
    "activar firewall": {
        "action": {"type": "cmd",
                   "run": "netsh advfirewall set allprofiles state on"},
        "aliases": ["encender firewall", "habilitar firewall"],
        "desc": "Activar el Firewall de Windows",
        "confirm": True
    },
    "desactivar firewall": {
        "action": {"type": "cmd",
                   "run": "netsh advfirewall set allprofiles state off"},
        "aliases": ["apagar firewall", "deshabilitar firewall"],
        "desc": "Desactivar el Firewall de Windows",
        "confirm": True
    },
    "ver estado del firewall": {
        "action": {"type": "cmd", "run": "netsh advfirewall show allprofiles state"},
        "aliases": ["estado firewall", "esta activo el firewall"],
        "desc": "Ver estado del Firewall",
        "return_output": True,
        "open_window": True
    },

    # ── UTILIDADES DE ARCHIVO ─────────────────────────────────────────────────
    "ver archivos grandes": {
        "action": {"type": "powershell",
                   "run": "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select-Object -First 10 FullName, @{N='Tamaño(MB)';E={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize | Out-String"},
        "aliases": ["archivos que ocupan mas espacio", "top archivos grandes", "buscar archivos pesados"],
        "desc": "Ver los 10 archivos más grandes en C:",
        "return_output": True,
        "open_window": True
    },

    # ── INFORMACIÓN RÁPIDA ────────────────────────────────────────────────────
    "resumen del sistema": {
        "action": {"type": "powershell",
                   "run": """
$cpu    = (Get-CimInstance Win32_Processor).Name
$ram    = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB, 1)
$os     = (Get-CimInstance Win32_OperatingSystem).Caption
$uptime = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
$ip     = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | Select-Object -First 1).IPAddress
"SO: $os`nCPU: $cpu`nRAM: $ram GB`nIP local: $ip`nActivo hace: $($uptime.Hours)h $($uptime.Minutes)m"
"""},
        "aliases": [
            "info del sistema", "resumen tecnico", "como esta el equipo",
            "estado del equipo", "informe del sistema"
        ],
        "desc": "Resumen técnico del sistema",
        "return_output": True
    },
}


# ═════════════════════════════════════════════════════════════════════════════
#  MOTOR DE RESOLUCIÓN  (compartido para ambas tablas)
# ═════════════════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Minúsculas + quitar tildes."""
    for src, dst in zip("áéíóúüñàèìòù", "aeiouunaeio u"):
        text = text.replace(src, dst)
    return text.lower().strip()


def _build_table(source: dict) -> tuple[dict, list]:
    """Tabla plana {alias_normalizado → canonical_key} + lista de claves."""
    table = {}
    for canonical, data in source.items():
        norm = _normalize(canonical)
        table[norm] = canonical
        for alias in data.get("aliases", []):
            table[_normalize(alias)] = canonical
    return table, list(table.keys())


_WIN_TABLE, _WIN_KEYS   = _build_table(WINDOWS_COMMANDS)
_ACT_TABLE, _ACT_KEYS   = _build_table(SYSTEM_ACTIONS)


def _resolve(query: str, table: dict, keys: list, cutoff: float = 0.52) -> Optional[str]:
    """
    Devuelve el canonical_key que mejor coincide con `query`, o None.
    Estrategias: exacta → fuzzy → palabras clave.
    """
    nq = _normalize(query)

    # 1. Exacta
    if nq in table:
        return table[nq]

    # 2. Fuzzy
    best, best_key = 0.0, None
    for k in keys:
        s = SequenceMatcher(None, nq, k).ratio()
        if s > best:
            best, best_key = s, k
    if best >= cutoff and best_key:
        log.debug(f"[WinCMD] Fuzzy ({best:.2f}): '{query}' → '{table[best_key]}'")
        return table[best_key]

    # 3. Palabras clave (todas las palabras del query deben aparecer en la clave)
    words = set(nq.split())
    if len(words) >= 2:
        for k in keys:
            if all(w in k for w in words):
                return table[k]

    return None


# ═════════════════════════════════════════════════════════════════════════════
#  API PÚBLICA
# ═════════════════════════════════════════════════════════════════════════════

def resolve(query: str) -> Optional[tuple[str, str, str]]:
    """
    Resuelve `query` en WINDOWS_COMMANDS.
    Retorna (canonical, cmd, desc) o None.
    """
    canonical = _resolve(query, _WIN_TABLE, _WIN_KEYS)
    if canonical:
        data = WINDOWS_COMMANDS[canonical]
        return canonical, data["cmd"], data["desc"]
    return None


def resolve_and_launch(query: str) -> Optional[str]:
    """
    Resuelve y lanza una ventana/panel.
    Retorna la descripción amigable si tuvo éxito, None en caso contrario.
    """
    result = resolve(query)
    if not result:
        return None
    canonical, cmd, desc = result
    fallback = WINDOWS_COMMANDS[canonical].get("fallback_cmd")
    success  = _launch(cmd, fallback)
    return desc if success else None


def resolve_action(query: str) -> Optional[dict]:
    """
    Resuelve `query` en SYSTEM_ACTIONS.
    Retorna el dict completo de la acción (con 'action', 'desc', 'confirm', etc.) o None.
    """
    canonical = _resolve(query, _ACT_TABLE, _ACT_KEYS)
    if canonical:
        entry = SYSTEM_ACTIONS[canonical].copy()
        entry["canonical"] = canonical
        return entry
    return None


def run_action(action_entry: dict) -> tuple[bool, str]:
    """
    Ejecuta la acción del diccionario retornado por resolve_action().
    Retorna (éxito: bool, output: str).
    `output` es la salida del subproceso si return_output=True, o "" si no.
    """
    action      = action_entry["action"]
    atype       = action["type"]         # "powershell" | "cmd"
    run         = action.get("run", "")
    return_out  = action_entry.get("return_output", False)
    open_window = action_entry.get("open_window", False)

    try:
        if open_window:
            # Abre una ventana cmd/powershell visible para mostrar la salida
            if atype == "powershell":
                subprocess.Popen(
                    ["powershell", "-NoExit", "-Command", run],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    f'cmd /k "{run}"',
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            return True, ""

        elif return_out:
            # Captura la salida para que DARIUS la lea en voz alta
            if atype == "powershell":
                result = subprocess.run(
                    ["powershell", "-NonInteractive", "-Command", run],
                    capture_output=True, text=True, timeout=15, encoding="utf-8",
                    errors="replace"
                )
            else:
                result = subprocess.run(
                    run, shell=True, capture_output=True,
                    text=True, timeout=15, encoding="utf-8", errors="replace"
                )
            output = (result.stdout or result.stderr or "Sin salida").strip()
            # Limitar a 300 caracteres para TTS
            if len(output) > 300:
                output = output[:300] + "…"
            log.debug(f"[WinCMD] Output: {output[:120]}")
            return True, output

        else:
            # Ejecuta en background, sin captura
            if atype == "powershell":
                subprocess.Popen(
                    ["powershell", "-NonInteractive", "-WindowStyle", "Hidden",
                     "-Command", run],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen(
                    run, shell=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            return True, ""

    except subprocess.TimeoutExpired:
        log.error(f"[WinCMD] Timeout ejecutando acción: {run[:60]}")
        return False, "El comando tardó demasiado."
    except Exception as e:
        log.error(f"[WinCMD] Error en run_action: {e}")
        return False, str(e)


# ── Función interna de lanzamiento (para Tipo A) ─────────────────────────────

def _launch(cmd: str, fallback_cmd: Optional[str] = None) -> bool:
    """Lanza un panel/ventana (Tipo A)."""
    import subprocess
    from pathlib import Path
    try:
        if re.match(r"^[a-z\-]+:", cmd) and not cmd.endswith(".exe"):
            os.startfile(cmd); return True
        if cmd.endswith(".msc"):
            subprocess.Popen(["mmc", cmd], shell=False); return True
        if cmd.endswith(".cpl"):
            subprocess.Popen(["control", cmd], shell=False); return True
        if Path(cmd).is_file():
            os.startfile(cmd); return True
        subprocess.Popen(cmd, shell=True); return True
    except FileNotFoundError:
        if fallback_cmd:
            try: subprocess.Popen(fallback_cmd, shell=True); return True
            except Exception: pass
        return False
    except Exception as e:
        log.error(f"[WinCMD] _launch error: {e}"); return False
